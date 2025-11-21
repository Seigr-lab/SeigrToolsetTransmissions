"""
UDP transport for unreliable STT frame delivery.

Provides connectionless packet transport over UDP with optional
DTLS-style encryption via STC.
"""

import asyncio
import socket
import struct
import time
from typing import Optional, Callable, Tuple, Dict, Any, Set, List
from dataclasses import dataclass
from enum import IntEnum

from ..frame import STTFrame
from ..utils.exceptions import STTTransportError
from ..utils.logging import get_logger


logger = get_logger(__name__)


class DiscoveryMessageType(IntEnum):
    """Discovery message types."""
    ANNOUNCE = 0x01  # Node announcing its presence
    REQUEST = 0x02   # Request for peer announcements
    RESPONSE = 0x03  # Response to discovery request


@dataclass
class UDPConfig:
    """UDP transport configuration."""
    
    bind_address: str = "0.0.0.0"
    bind_port: int = 0  # 0 = random port
    max_packet_size: int = 1472  # Safe MTU for IPv4 (1500 - 20 IP - 8 UDP)
    receive_buffer_size: int = 65536
    send_buffer_size: int = 65536


class UDPTransport:
    """
    UDP transport for STT frames.
    
    Provides unreliable datagram delivery suitable for:
    - NAT traversal with hole punching
    - Low-latency streaming
    - Broadcast/multicast discovery
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 0,
        stc_wrapper: Optional['STCWrapper'] = None,
        on_frame_received: Optional[Callable[[STTFrame, Tuple[str, int]], None]] = None
    ):
        """
        Initialize UDP transport.
        
        Args:
            host: Bind address
            port: Bind port (0 = random)
            stc_wrapper: STC wrapper for encryption
            on_frame_received: Callback for received frames (frame, peer_addr)
        """
        self.host = host
        self.port = port
        self.config = UDPConfig(bind_address=host, bind_port=port)
        self.stc_wrapper = stc_wrapper
        self.on_frame_received = on_frame_received
        
        self.transport = None
        self.protocol = None
        self.running = False
        self.local_addr = None
        
        # Statistics
        self.started_at = None
        self.bytes_sent = 0
        self.bytes_received = 0
        self.packets_sent = 0
        self.packets_received = 0
        self.packets_dropped = 0
        self.errors_send = 0
        self.errors_receive = 0
        
        # Peer discovery
        self.discovered_peers: Set[Tuple[str, int]] = set()
        self.discovery_enabled = False
        self._discovery_task: Optional[asyncio.Task] = None
        self.on_peer_discovered: Optional[Callable[[str, int, bytes], None]] = None
    
    async def start(self) -> Tuple[str, int]:
        """
        Start UDP transport.
        
        Returns:
            Tuple of (local_ip, local_port)
            
        Raises:
            STTTransportError: If start fails
        """
        if self.running:
            raise STTTransportError("Transport already running")
        
        try:
            # Create datagram endpoint
            loop = asyncio.get_event_loop()
            
            # Platform-specific options (reuse_port not supported on Windows)
            endpoint_kwargs = {
                'local_addr': (self.config.bind_address, self.config.bind_port)
            }
            
            # Only use reuse_port on platforms that support it
            import sys
            if sys.platform != 'win32':
                endpoint_kwargs['reuse_port'] = True
            
            self.transport, self.protocol = await loop.create_datagram_endpoint(
                lambda: UDPProtocol(self.on_frame_received),
                **endpoint_kwargs
            )
            
            # Link protocol to parent for stats tracking
            self.protocol.parent_transport = self
            
            # Set socket options
            sock = self.transport.get_extra_info('socket')
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.config.receive_buffer_size)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.config.send_buffer_size)
            
            # Enable broadcast
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # Get local address
            self.local_addr = sock.getsockname()
            
            self.running = True
            self.started_at = time.time()
            
            logger.info(f"UDP transport started on {self.local_addr[0]}:{self.local_addr[1]}")
            
            return self.local_addr
            
        except Exception as e:
            raise STTTransportError(f"Failed to start UDP transport: {e}")
    
    async def stop(self) -> None:
        """Stop UDP transport."""
        if not self.running:
            return
        
        self.running = False
        
        # Stop discovery
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
            self._discovery_task = None
        
        if self.transport:
            self.transport.close()
            self.transport = None
        
        self.protocol = None
        self.local_addr = None
        
        logger.info("UDP transport stopped")
    
    async def send_frame(
        self,
        frame: STTFrame,
        peer_addr: Tuple[str, int]
    ) -> None:
        """
        Send frame to peer via UDP.
        
        Args:
            frame: Frame to send
            peer_addr: Peer address (ip, port)
            
        Raises:
            STTTransportError: If send fails
        """
        if not self.running:
            raise STTTransportError("Transport not running")
        
        try:
            # Serialize frame
            frame_bytes = frame.to_bytes()
            
            # Check packet size
            if len(frame_bytes) > self.config.max_packet_size:
                logger.warning(
                    f"Frame size {len(frame_bytes)} exceeds max packet size "
                    f"{self.config.max_packet_size}, may fragment"
                )
            
            # Send datagram
            self.transport.sendto(frame_bytes, peer_addr)
            
            # Update statistics
            self.bytes_sent += len(frame_bytes)
            self.packets_sent += 1
            
            logger.debug(f"Sent {len(frame_bytes)} bytes to {peer_addr[0]}:{peer_addr[1]}")
            
        except Exception as e:
            self.errors_send += 1
            raise STTTransportError(f"Failed to send frame: {e}")
    
    async def send_raw(
        self,
        data: bytes,
        peer_addr: Tuple[str, int]
    ) -> None:
        """
        Send raw bytes to peer.
        
        Args:
            data: Raw data to send
            peer_addr: Peer address (ip, port)
        """
        if not self.running:
            raise STTTransportError("Transport not running")
        
        self.transport.sendto(data, peer_addr)
        self.bytes_sent += len(data)
        self.packets_sent += 1
    
    def get_local_address(self) -> Optional[Tuple[str, int]]:
        """Get local bound address."""
        return self.local_addr
    
    def get_address(self) -> Optional[Tuple[str, int]]:
        """Get local bound address (alias for backward compatibility)."""
        return self.local_addr
    
    def set_receive_handler(self, handler: Callable[[bytes, Tuple[str, int]], None]) -> None:
        """Set handler for received data.
        
        Args:
            handler: Callback function(data, peer_addr)
        """
        self.on_frame_received = handler
        if self.protocol:
            self.protocol.on_frame_received = handler
    
    async def send(self, data: bytes, peer_addr: Tuple[str, int]) -> None:
        """Send raw bytes to peer.
        
        Args:
            data: Raw data to send
            peer_addr: Peer address (ip, port)
        """
        if not self.running:
            raise STTTransportError("Transport not running")
        
        self.transport.sendto(data, peer_addr)
        self.bytes_sent += len(data)
        self.packets_sent += 1
    
    @property
    def is_running(self) -> bool:
        """Check if transport is running."""
        return self.running
    
    # Peer Discovery Methods
    
    async def enable_discovery(
        self,
        node_id: bytes,
        announce_interval: float = 5.0,
        on_peer_discovered: Optional[Callable[[str, int, bytes], None]] = None
    ):
        """
        Enable local network peer discovery via broadcast.
        
        Args:
            node_id: This node's identifier
            announce_interval: Seconds between announcements
            on_peer_discovered: Callback(peer_ip, peer_port, peer_node_id)
        """
        if not self.running:
            raise STTTransportError("Transport not running")
        
        if self.discovery_enabled:
            return
        
        self.discovery_enabled = True
        self.on_peer_discovered = on_peer_discovered
        
        # Start periodic announcements
        self._discovery_task = asyncio.create_task(
            self._announce_loop(node_id, announce_interval)
        )
        
        logger.info("Peer discovery enabled")
    
    async def disable_discovery(self):
        """Disable peer discovery."""
        if not self.discovery_enabled:
            return
        
        self.discovery_enabled = False
        
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
            self._discovery_task = None
        
        logger.info("Peer discovery disabled")
    
    async def broadcast_announce(self, node_id: bytes, port: int = None):
        """
        Broadcast node announcement on local network.
        
        Args:
            node_id: This node's 32-byte identifier
            port: Port this node is listening on (default: local_addr port)
        """
        if not self.running:
            raise STTTransportError("Transport not running")
        
        if port is None and self.local_addr:
            port = self.local_addr[1]
        
        if port is None:
            raise STTTransportError("No port specified for announcement")
        
        # Build announcement message
        # Format: [type:1][node_id:32][port:2]
        msg = struct.pack(
            '!B32sH',
            DiscoveryMessageType.ANNOUNCE,
            node_id,
            port
        )
        
        # Broadcast to LAN
        broadcast_addr = ('255.255.255.255', 9337)  # STT discovery port
        
        try:
            self.transport.sendto(msg, broadcast_addr)
            logger.debug(f"Broadcast announcement: node_id={node_id.hex()[:16]}... port={port}")
        except Exception as e:
            logger.warning(f"Broadcast failed: {e}")
    
    async def discover_peers(self, timeout: float = 2.0) -> List[Tuple[str, int, bytes]]:
        """
        Discover peers on local network.
        
        Args:
            timeout: Seconds to wait for responses
            
        Returns:
            List of (ip, port, node_id) tuples
        """
        if not self.running:
            raise STTTransportError("Transport not running")
        
        # Send discovery request
        msg = struct.pack('!B', DiscoveryMessageType.REQUEST)
        broadcast_addr = ('255.255.255.255', 9337)
        
        # Clear discovered peers
        discovered = []
        
        # Save original handler
        original_handler = self.on_frame_received
        
        # Set temporary handler to collect responses
        def discovery_handler(data: bytes, addr: Tuple[str, int]):
            try:
                if len(data) >= 35:  # type(1) + node_id(32) + port(2)
                    msg_type = data[0]
                    if msg_type in (DiscoveryMessageType.ANNOUNCE, DiscoveryMessageType.RESPONSE):
                        node_id = data[1:33]
                        port = struct.unpack('!H', data[33:35])[0]
                        discovered.append((addr[0], port, node_id))
                        logger.debug(f"Discovered peer: {addr[0]}:{port} node_id={node_id.hex()[:16]}...")
            except Exception as e:
                logger.debug(f"Failed to parse discovery response: {e}")
        
        self.set_receive_handler(discovery_handler)
        
        try:
            # Broadcast request
            self.transport.sendto(msg, broadcast_addr)
            
            # Wait for responses
            await asyncio.sleep(timeout)
            
            return discovered
        finally:
            # Restore original handler
            self.set_receive_handler(original_handler)
    
    async def _announce_loop(self, node_id: bytes, interval: float):
        """Periodic announcement loop."""
        try:
            while self.discovery_enabled:
                await self.broadcast_announce(node_id)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
    
    def _handle_discovery_packet(self, data: bytes, addr: Tuple[str, int]):
        """
        Handle discovery-related packet.
        
        Args:
            data: Packet data
            addr: Sender address
            
        Returns:
            True if handled as discovery packet
        """
        if len(data) < 1:
            return False
        
        try:
            msg_type = data[0]
            
            if msg_type == DiscoveryMessageType.ANNOUNCE:
                # Peer announced itself
                if len(data) >= 35:
                    node_id = data[1:33]
                    port = struct.unpack('!H', data[33:35])[0]
                    
                    peer_addr = (addr[0], port)
                    if peer_addr not in self.discovered_peers:
                        self.discovered_peers.add(peer_addr)
                        logger.info(f"Discovered peer: {addr[0]}:{port} node_id={node_id.hex()[:16]}...")
                        
                        if self.on_peer_discovered:
                            self.on_peer_discovered(addr[0], port, node_id)
                
                return True
            
            elif msg_type == DiscoveryMessageType.REQUEST:
                # Someone is looking for peers - respond if discovery enabled
                if self.discovery_enabled and self.local_addr:
                    # Send our info
                    # Need to get our node_id - for now just respond to sender
                    logger.debug(f"Discovery request from {addr[0]}:{addr[1]}")
                
                return True
        
        except Exception as e:
            logger.debug(f"Failed to handle discovery packet: {e}")
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get transport statistics."""
        uptime = None
        if self.started_at:
            uptime = time.time() - self.started_at
        
        return {
            'running': self.running,
            'local_address': self.local_addr,
            'max_packet_size': self.config.max_packet_size,
            'started_at': self.started_at,
            'uptime': uptime,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'packets_sent': self.packets_sent,
            'packets_received': self.packets_received,
            'packets_dropped': self.packets_dropped,
            'errors_send': self.errors_send,
            'errors_receive': self.errors_receive,
            'send_rate_bps': self.bytes_sent / uptime if uptime and uptime > 0 else 0,
            'receive_rate_bps': self.bytes_received / uptime if uptime and uptime > 0 else 0,
        }


class UDPProtocol(asyncio.DatagramProtocol):
    """
    Asyncio datagram protocol for receiving UDP packets.
    """
    
    def __init__(
        self,
        on_frame_received: Optional[Callable[[STTFrame, Tuple[str, int]], None]] = None
    ):
        """
        Initialize protocol.
        
        Args:
            on_frame_received: Callback for received frames
        """
        self.on_frame_received = on_frame_received
        self.transport = None
        self.parent_transport = None  # Reference to UDPTransport for stats
    
    def connection_made(self, transport):
        """Called when connection is established."""
        self.transport = transport
        logger.debug("UDP protocol connection established")
    
    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        """
        Called when datagram is received.
        
        Args:
            data: Received data
            addr: Sender address (ip, port)
        """
        try:
            # Update statistics in parent
            if self.parent_transport:
                self.parent_transport.bytes_received += len(data)
                self.parent_transport.packets_received += 1
                
                # Check if this is a discovery packet
                if self.parent_transport._handle_discovery_packet(data, addr):
                    return  # Discovery packet handled, don't forward to app
            
            # Invoke callback with raw data
            if self.on_frame_received:
                # Schedule async callback if coroutine
                if asyncio.iscoroutinefunction(self.on_frame_received):
                    asyncio.create_task(self.on_frame_received(data, addr))
                else:
                    self.on_frame_received(data, addr)
            
            logger.debug(f"Received {len(data)} bytes from {addr[0]}:{addr[1]}")
            
        except Exception as e:
            if self.parent_transport:
                self.parent_transport.errors_receive += 1
            logger.error(f"Failed to process datagram from {addr[0]}:{addr[1]}: {e}")
    
    def error_received(self, exc):
        """Called when send/receive operation raises OSError."""
        if self.parent_transport:
            self.parent_transport.errors_receive += 1
        logger.error(f"UDP protocol error: {exc}")
    
    def connection_lost(self, exc):
        """Called when connection is lost or closed."""
        if exc:
            logger.error(f"UDP protocol connection lost: {exc}")
        else:
            logger.debug("UDP protocol connection closed")
