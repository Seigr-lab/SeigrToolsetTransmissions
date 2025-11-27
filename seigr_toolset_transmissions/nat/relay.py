"""
Relay NAT Coordinator - route through third-party relay node.

When direct connection is impossible (both peers behind NAT),
route traffic through a relay node with public IP.

This is similar to TURN but simpler - just STT forwarding.
"""

import asyncio
import time
import json
import socket
from typing import Optional, Tuple, Dict, Any, Set
import logging

from .coordinator import NATCoordinator, NATStrategy, NATCoordinationError

logger = logging.getLogger(__name__)


class RelayNATCoordinator(NATCoordinator):
    """
    Relay-based NAT coordination.
    
    Architecture:
    - Relay server has public IP
    - Clients register with relay
    - Relay forwards frames between clients
    - Transparent to STT core
    
    Trade-offs:
    + Always works (no NAT punching needed)
    + Simple protocol
    - Uses relay bandwidth
    - Relay is single point of failure
    - Higher latency (extra hop)
    """
    
    def __init__(
        self,
        local_node_id: bytes,
        relay_host: str,
        relay_port: int,
        fallback_to_direct: bool = True
    ):
        """
        Initialize relay coordinator.
        
        Args:
            local_node_id: This node's identifier
            relay_host: Relay server host
            relay_port: Relay server port
            fallback_to_direct: Try direct connection first, use relay if fails
        """
        super().__init__(local_node_id, NATStrategy.RELAY)
        self.relay_host = relay_host
        self.relay_port = relay_port
        self.fallback_to_direct = fallback_to_direct
        
        # Track which peers require relay
        self.relayed_peers: Set[bytes] = set()
        self.direct_peers: Set[bytes] = set()
        
        # Statistics
        self.relay_attempts = 0
        self.direct_attempts = 0
        self.relay_successes = 0
        self.direct_successes = 0
        
        # Registration state
        self._registered = False
        self._registration_socket: Optional[socket.socket] = None
        self._keep_alive_task: Optional[asyncio.Task] = None
    
    async def get_peer_endpoint(
        self,
        peer_node_id: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, int]:
        """
        Get endpoint for peer - relay or direct.
        
        Strategy:
        1. If fallback_to_direct: Try direct connection first
        2. If direct fails or disabled: Use relay
        3. Cache decision per peer
        
        Args:
            peer_node_id: Peer's node identifier
            metadata: Optional metadata with 'direct_host', 'direct_port'
            
        Returns:
            Tuple of (host, port) - either relay or direct peer address
        """
        # Check if we already know this peer requires relay
        if peer_node_id in self.relayed_peers:
            logger.debug(f"Using relay for {peer_node_id.hex()[:8]} (cached)")
            self.relay_attempts += 1
            return (self.relay_host, self.relay_port)
        
        # If direct address in metadata and fallback enabled, try that
        if self.fallback_to_direct and metadata:
            direct_host = metadata.get('direct_host')
            direct_port = metadata.get('direct_port')
            
            if direct_host and direct_port:
                logger.info(f"Attempting direct to {peer_node_id.hex()[:8]} at {direct_host}:{direct_port}")
                self.direct_attempts += 1
                self.direct_peers.add(peer_node_id)
                return (direct_host, direct_port)
        
        # Query relay for peer address
        if self._registered and self.fallback_to_direct:
            peer_endpoint = await self._lookup_peer(peer_node_id)
            if peer_endpoint:
                logger.info(f"Got peer endpoint from relay: {peer_endpoint}")
                self.direct_attempts += 1
                return peer_endpoint
        
        # Default to relay
        logger.info(f"Using relay for {peer_node_id.hex()[:8]} at {self.relay_host}:{self.relay_port}")
        self.relay_attempts += 1
        self.relayed_peers.add(peer_node_id)
        return (self.relay_host, self.relay_port)
    
    def mark_direct_success(self, peer_node_id: bytes) -> None:
        """
        Mark direct connection as successful.
        
        Called by application after successful direct connect.
        
        Args:
            peer_node_id: Peer that connected directly
        """
        if peer_node_id in self.relayed_peers:
            self.relayed_peers.remove(peer_node_id)
        self.direct_peers.add(peer_node_id)
        self.direct_successes += 1
        logger.info(f"Direct connection to {peer_node_id.hex()[:8]} succeeded")
    
    def mark_relay_required(self, peer_node_id: bytes) -> None:
        """
        Mark peer as requiring relay.
        
        Called by application when direct connection fails.
        
        Args:
            peer_node_id: Peer that requires relay
        """
        if peer_node_id in self.direct_peers:
            self.direct_peers.remove(peer_node_id)
        self.relayed_peers.add(peer_node_id)
        self.relay_successes += 1
        logger.info(f"Peer {peer_node_id.hex()[:8]} requires relay")
    
    async def register_local_endpoint(
        self,
        host: str,
        port: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register with relay server.
        
        Protocol:
        1. Send UDP registration message to relay
        2. Relay responds with acknowledgment
        3. Start keep-alive task (30 second intervals)
        
        Args:
            host: Local bind address
            port: Local bind port
            metadata: Optional metadata (e.g., transport type)
        """
        logger.info(
            f"Registering with relay {self.relay_host}:{self.relay_port} "
            f"(local {host}:{port})"
        )
        
        try:
            # Create UDP socket for relay communication
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5.0)
            
            # Build registration message
            registration_msg = {
                "type": "register",
                "node_id": self.node_id.hex(),
                "host": host,
                "port": port,
                "timestamp": int(time.time()),
                "metadata": metadata or {}
            }
            
            message = json.dumps(registration_msg).encode('utf-8')
            sock.sendto(message, (self.relay_host, self.relay_port))
            
            # Wait for acknowledgment
            try:
                response, _ = sock.recvfrom(4096)
                response_data = json.loads(response.decode('utf-8'))
                
                if response_data.get('type') == 'registered':
                    self._registered = True
                    self._registration_socket = sock
                    logger.info(f"Successfully registered with relay")
                    
                    # Start keep-alive task
                    self._keep_alive_task = asyncio.create_task(
                        self._keep_alive_loop()
                    )
                else:
                    sock.close()
                    raise NATCoordinationError(
                        f"Relay registration failed: {response_data.get('error', 'Unknown')}"
                    )
            except socket.timeout:
                sock.close()
                raise NATCoordinationError(
                    f"Relay registration timeout: {self.relay_host}:{self.relay_port}"
                )
                
        except Exception as e:
            logger.error(f"Failed to register with relay: {e}")
            raise NATCoordinationError(f"Relay registration error: {e}")
    
    async def unregister_endpoint(self) -> None:
        """
        Unregister from relay server.
        
        Called when node shuts down.
        """
        if not self._registered:
            return
            
        logger.info(f"Unregistering from relay {self.relay_host}:{self.relay_port}")
        
        # Cancel keep-alive task
        if self._keep_alive_task:
            self._keep_alive_task.cancel()
            try:
                await self._keep_alive_task
            except asyncio.CancelledError:
                pass
        
        # Send unregister message
        if self._registration_socket:
            try:
                unregister_msg = {
                    "type": "unregister",
                    "node_id": self.node_id.hex(),
                    "timestamp": int(time.time())
                }
                
                message = json.dumps(unregister_msg).encode('utf-8')
                self._registration_socket.sendto(
                    message,
                    (self.relay_host, self.relay_port)
                )
            except Exception as e:
                logger.warning(f"Error sending unregister: {e}")
            finally:
                self._registration_socket.close()
                self._registration_socket = None
        
        self._registered = False
    
    async def _keep_alive_loop(self) -> None:
        """Send periodic keep-alive to relay server."""
        while self._registered:
            try:
                await asyncio.sleep(30)  # Keep-alive every 30 seconds
                
                if self._registration_socket:
                    keep_alive_msg = {
                        "type": "keep_alive",
                        "node_id": self.node_id.hex(),
                        "timestamp": int(time.time())
                    }
                    
                    message = json.dumps(keep_alive_msg).encode('utf-8')
                    self._registration_socket.sendto(
                        message,
                        (self.relay_host, self.relay_port)
                    )
                    logger.debug("Sent keep-alive to relay")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Keep-alive error: {e}")
    
    async def _lookup_peer(self, peer_node_id: bytes) -> Optional[Tuple[str, int]]:
        """
        Query relay server for peer's endpoint.
        
        Returns:
            (host, port) if peer found, None otherwise
        """
        if not self._registration_socket:
            return None
            
        try:
            lookup_msg = {
                "type": "lookup",
                "requestor_id": self.node_id.hex(),
                "peer_id": peer_node_id.hex(),
                "timestamp": int(time.time())
            }
            
            # Create separate socket for lookup (non-blocking)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2.0)
            
            message = json.dumps(lookup_msg).encode('utf-8')
            sock.sendto(message, (self.relay_host, self.relay_port))
            
            try:
                response, _ = sock.recvfrom(4096)
                response_data = json.loads(response.decode('utf-8'))
                
                if response_data.get('type') == 'peer_info':
                    peer_host = response_data.get('host')
                    peer_port = response_data.get('port')
                    
                    if peer_host and peer_port:
                        return (peer_host, peer_port)
            except socket.timeout:
                logger.debug(f"Peer lookup timeout for {peer_node_id.hex()[:8]}")
            finally:
                sock.close()
                
        except Exception as e:
            logger.warning(f"Peer lookup error: {e}")
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get relay coordination statistics."""
        total_attempts = self.relay_attempts + self.direct_attempts
        
        return {
            'strategy': self.strategy.value,
            'relay_endpoint': f"{self.relay_host}:{self.relay_port}",
            'fallback_to_direct': self.fallback_to_direct,
            
            # Peer counts
            'relayed_peers': len(self.relayed_peers),
            'direct_peers': len(self.direct_peers),
            
            # Success rates
            'total_attempts': total_attempts,
            'relay_attempts': self.relay_attempts,
            'direct_attempts': self.direct_attempts,
            'relay_success_rate': (
                self.relay_successes / self.relay_attempts * 100
                if self.relay_attempts > 0 else 0
            ),
            'direct_success_rate': (
                self.direct_successes / self.direct_attempts * 100
                if self.direct_attempts > 0 else 0
            ),
        }
