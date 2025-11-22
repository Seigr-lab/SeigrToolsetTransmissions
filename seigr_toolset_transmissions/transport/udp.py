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
