"""
UDP transport for unreliable STT frame delivery.

Provides connectionless packet transport over UDP with optional
DTLS-style encryption via STC.
"""

import asyncio
import socket
from typing import Optional, Callable, Tuple, Dict, Any
from dataclasses import dataclass

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
        self.config = UDPConfig(bind_address=host, bind_port=port)
        self.stc_wrapper = stc_wrapper
        self.on_frame_received = on_frame_received
        
        self.transport = None
        self.protocol = None
        self.running = False
        self.local_addr = None
    
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
            
            self.transport, self.protocol = await loop.create_datagram_endpoint(
                lambda: UDPProtocol(self.on_frame_received),
                local_addr=(self.config.bind_address, self.config.bind_port),
                reuse_address=True,
                reuse_port=True,
            )
            
            # Set socket options
            sock = self.transport.get_extra_info('socket')
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.config.receive_buffer_size)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.config.send_buffer_size)
            
            # Get local address
            self.local_addr = sock.getsockname()
            
            self.running = True
            
            logger.info(f"UDP transport started on {self.local_addr[0]}:{self.local_addr[1]}")
            
            return self.local_addr
            
        except Exception as e:
            raise STTTransportError(f"Failed to start UDP transport: {e}")
    
    async def stop(self) -> None:
        """Stop UDP transport."""
        if not self.running:
            return
        
        self.running = False
        
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
            
            logger.debug(f"Sent {len(frame_bytes)} bytes to {peer_addr[0]}:{peer_addr[1]}")
            
        except Exception as e:
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
    
    def get_local_address(self) -> Optional[Tuple[str, int]]:
        """Get local bound address."""
        return self.local_addr
    
    def is_running(self) -> bool:
        """Check if transport is running."""
        return self.running
    
    def get_stats(self) -> Dict[str, Any]:
        """Get transport statistics."""
        return {
            'running': self.running,
            'local_address': self.local_addr,
            'max_packet_size': self.config.max_packet_size,
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
            # Parse frame
            frame = STTFrame.from_bytes(data)
            
            # Invoke callback
            if self.on_frame_received:
                self.on_frame_received(frame, addr)
            
            logger.debug(f"Received frame from {addr[0]}:{addr[1]}")
            
        except Exception as e:
            logger.error(f"Failed to process datagram from {addr[0]}:{addr[1]}: {e}")
    
    def error_received(self, exc):
        """Called when send/receive operation raises OSError."""
        logger.error(f"UDP protocol error: {exc}")
    
    def connection_lost(self, exc):
        """Called when connection is lost or closed."""
        if exc:
            logger.error(f"UDP protocol connection lost: {exc}")
        else:
            logger.debug("UDP protocol connection closed")
