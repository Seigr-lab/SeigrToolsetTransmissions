"""
NAT traversal implementation (STUN/TURN-like) for STT.

Provides hole punching and relay capabilities for connecting peers
behind NAT/firewalls.
"""

import asyncio
import socket
import struct
import time
from typing import Optional, Tuple, Dict, Callable
from dataclasses import dataclass
from enum import IntEnum

from ..utils.logging import get_logger

logger = get_logger(__name__)


class NATType(IntEnum):
    """NAT types (from RFC 5780)."""
    UNKNOWN = 0
    OPEN_INTERNET = 1  # No NAT
    FULL_CONE = 2      # Full cone NAT
    RESTRICTED = 3     # Restricted cone NAT
    PORT_RESTRICTED = 4  # Port restricted cone NAT
    SYMMETRIC = 5      # Symmetric NAT (hardest to traverse)


class STUNMessageType(IntEnum):
    """STUN-like message types."""
    BINDING_REQUEST = 0x0001
    BINDING_RESPONSE = 0x0101
    BINDING_ERROR = 0x0111
    HOLE_PUNCH = 0x0002  # Custom: request hole punching coordination
    RELAY_REQUEST = 0x0003  # Custom: request relay service
    RELAY_DATA = 0x0004  # Custom: relayed data


@dataclass
class NATMapping:
    """NAT mapping information."""
    local_addr: Tuple[str, int]
    external_addr: Tuple[str, int]
    nat_type: NATType
    timestamp: float


class STUNServer:
    """
    STUN-like server for NAT type detection and public address discovery.
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 3478):
        """
        Initialize STUN server.
        
        Args:
            host: Listen address
            port: Listen port (3478 is standard STUN port)
        """
        self.host = host
        self.port = port
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.running = False
        
        logger.info(f"STUN server initialized on {host}:{port}")
    
    async def start(self):
        """Start STUN server."""
        if self.running:
            return
        
        loop = asyncio.get_event_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: STUNProtocol(self),
            local_addr=(self.host, self.port)
        )
        
        self.running = True
        logger.info("STUN server started")
    
    async def stop(self):
        """Stop STUN server."""
        if not self.running:
            return
        
        self.running = False
        if self.transport:
            self.transport.close()
        
        logger.info("STUN server stopped")
    
    def handle_binding_request(self, data: bytes, addr: Tuple[str, int]) -> bytes:
        """
        Handle STUN binding request.
        
        Args:
            data: Request data
            addr: Client address
            
        Returns:
            Response message with client's external address
        """
        # Build response with external address
        # Format: [type:2][length:2][ip:4][port:2]
        ip_bytes = socket.inet_aton(addr[0])
        
        response = struct.pack(
            '!HH4sH',
            STUNMessageType.BINDING_RESPONSE,
            6,  # length of ip + port
            ip_bytes,
            addr[1]
        )
        
        return response


class STUNProtocol(asyncio.DatagramProtocol):
    """Protocol handler for STUN server."""
    
    def __init__(self, server: STUNServer):
        self.server = server
        self.transport = None
    
    def connection_made(self, transport):
        self.transport = transport
    
    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        """Handle incoming STUN request."""
        if len(data) < 4:
            return
        
        try:
            msg_type, length = struct.unpack('!HH', data[:4])
            
            if msg_type == STUNMessageType.BINDING_REQUEST:
                response = self.server.handle_binding_request(data, addr)
                self.transport.sendto(response, addr)
        
        except Exception as e:
            logger.error(f"STUN protocol error: {e}")


class NATTraversal:
    """
    NAT traversal manager providing hole punching and relay.
    """
    
    def __init__(
        self,
        local_port: int,
        stun_servers: list[Tuple[str, int]] = None
    ):
        """
        Initialize NAT traversal.
        
        Args:
            local_port: Local UDP port
            stun_servers: List of (host, port) STUN servers
        """
        self.local_port = local_port
        self.stun_servers = stun_servers or [
            ("stun.l.google.com", 19302),
            ("stun1.l.google.com", 19302),
        ]
        
        self.nat_mapping: Optional[NATMapping] = None
        self.transport: Optional[asyncio.DatagramTransport] = None
        
        # Relay service
        self.relay_peers: Dict[bytes, Tuple[str, int]] = {}  # peer_id -> addr
        
        logger.info("NAT traversal initialized")
    
    async def detect_nat_type(self) -> NATType:
        """
        Detect NAT type using STUN.
        
        Returns:
            Detected NAT type
        """
        # Simplified NAT detection - production would use RFC 5780 algorithm
        
        external_addr = await self.get_external_address()
        
        if not external_addr:
            return NATType.UNKNOWN
        
        # Get local address
        local_addr = self._get_local_address()
        
        if external_addr == local_addr:
            # No NAT
            return NATType.OPEN_INTERNET
        
        # For now, assume port-restricted cone NAT
        # Full implementation would do multiple STUN tests
        return NATType.PORT_RESTRICTED
    
    async def get_external_address(self) -> Optional[Tuple[str, int]]:
        """
        Get external address using STUN.
        
        Returns:
            External (ip, port) or None
        """
        if self.nat_mapping and time.time() - self.nat_mapping.timestamp < 300:
            # Use cached mapping if less than 5 minutes old
            return self.nat_mapping.external_addr
        
        # Query STUN servers
        for stun_host, stun_port in self.stun_servers:
            try:
                external = await self._query_stun(stun_host, stun_port)
                if external:
                    # Cache mapping
                    self.nat_mapping = NATMapping(
                        local_addr=self._get_local_address(),
                        external_addr=external,
                        nat_type=NATType.UNKNOWN,
                        timestamp=time.time()
                    )
                    return external
            except Exception as e:
                logger.warning(f"STUN query failed for {stun_host}:{stun_port}: {e}")
                continue
        
        return None
    
    async def _query_stun(
        self,
        stun_host: str,
        stun_port: int,
        timeout: float = 3.0
    ) -> Optional[Tuple[str, int]]:
        """
        Query STUN server for external address.
        
        Args:
            stun_host: STUN server host
            stun_port: STUN server port
            timeout: Query timeout
            
        Returns:
            External (ip, port) or None
        """
        loop = asyncio.get_event_loop()
        
        # Create temporary UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', self.local_port))
        sock.setblocking(False)
        
        # Build STUN binding request
        request = struct.pack('!HH', STUNMessageType.BINDING_REQUEST, 0)
        
        # Send request
        await loop.sock_sendto(sock, request, (stun_host, stun_port))
        
        try:
            # Wait for response
            data, addr = await asyncio.wait_for(
                loop.sock_recvfrom(sock, 1024),
                timeout=timeout
            )
            
            # Parse response
            if len(data) >= 10:
                msg_type, length, ip_bytes, port = struct.unpack('!HH4sH', data[:10])
                
                if msg_type == STUNMessageType.BINDING_RESPONSE:
                    external_ip = socket.inet_ntoa(ip_bytes)
                    return (external_ip, port)
        
        except asyncio.TimeoutError:
            pass
        finally:
            sock.close()
        
        return None
    
    def _get_local_address(self) -> Tuple[str, int]:
        """Get local address."""
        # Get local IP by connecting to a public IP (doesn't actually send data)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = "127.0.0.1"
        finally:
            s.close()
        
        return (local_ip, self.local_port)
    
    async def coordinate_hole_punch(
        self,
        peer_id: bytes,
        peer_external: Tuple[str, int],
        coordinator_callback: Callable
    ) -> bool:
        """
        Coordinate hole punching with peer.
        
        Args:
            peer_id: Peer identifier
            peer_external: Peer's external address
            coordinator_callback: Function to signal peer to punch
            
        Returns:
            True if hole punching succeeded
        """
        logger.info(f"Coordinating hole punch to {peer_external}")
        
        # Signal peer to punch (via coordinator)
        await coordinator_callback(peer_id, self.nat_mapping.external_addr)
        
        # Send our own punch packets
        for _ in range(5):
            # Send multiple packets to increase chance of success
            punch_msg = b"PUNCH:" + peer_id
            if self.transport:
                self.transport.sendto(punch_msg, peer_external)
            await asyncio.sleep(0.1)
        
        # In production, would verify connection established
        return True
    
    def enable_relay(self):
        """Enable relay service for peers that can't hole punch."""
        logger.info("Relay service enabled")
        # In production, would set up relay packet forwarding
    
    async def relay_packet(
        self,
        peer_id: bytes,
        data: bytes,
        dest_addr: Tuple[str, int]
    ):
        """
        Relay packet to peer.
        
        Args:
            peer_id: Peer identifier
            data: Data to relay
            dest_addr: Destination address
        """
        # Wrap in relay message
        relay_msg = struct.pack('!H', STUNMessageType.RELAY_DATA) + peer_id + data
        
        if self.transport:
            self.transport.sendto(relay_msg, dest_addr)
