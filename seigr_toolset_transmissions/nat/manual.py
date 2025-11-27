"""
Manual NAT Coordinator - requires pre-configured endpoints.

This is the current STT behavior: users must manually provide
peer addresses (either public IPs or port-forwarded addresses).
"""

from typing import Optional, Tuple, Dict, Any
import logging

from .coordinator import NATCoordinator, NATStrategy, NATCoordinationError

logger = logging.getLogger(__name__)


class ManualNATCoordinator(NATCoordinator):
    """
    Manual NAT coordination - no automatic discovery.
    
    Users must:
    - Configure port forwarding if behind NAT
    - OR have public IP address
    - Manually exchange (host, port) out-of-band
    
    This is the simplest strategy and current STT default.
    """
    
    def __init__(self, local_node_id: bytes):
        """
        Initialize manual coordinator.
        
        Args:
            local_node_id: This node's identifier
        """
        super().__init__(local_node_id, NATStrategy.MANUAL)
        self.peer_endpoints: Dict[bytes, Tuple[str, int]] = {}
        self.local_endpoint: Optional[Tuple[str, int]] = None
    
    def configure_peer(self, peer_node_id: bytes, host: str, port: int) -> None:
        """
        Manually configure peer endpoint.
        
        Args:
            peer_node_id: Peer's node identifier
            host: Peer's host address
            port: Peer's port
        """
        self.peer_endpoints[peer_node_id] = (host, port)
        logger.info(f"Configured peer {peer_node_id.hex()[:8]} at {host}:{port}")
    
    async def get_peer_endpoint(
        self,
        peer_node_id: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, int]:
        """
        Get manually configured peer endpoint.
        
        Args:
            peer_node_id: Peer's node identifier
            metadata: Optional metadata (can contain 'host' and 'port')
            
        Returns:
            Tuple of (host, port)
            
        Raises:
            NATCoordinationError: If peer not configured
        """
        # Check if endpoint provided in metadata
        if metadata and 'host' in metadata and 'port' in metadata:
            return (metadata['host'], metadata['port'])
        
        # Check pre-configured endpoints
        if peer_node_id in self.peer_endpoints:
            return self.peer_endpoints[peer_node_id]
        
        raise NATCoordinationError(
            f"No endpoint configured for peer {peer_node_id.hex()[:8]}. "
            f"Use configure_peer() or provide host/port in metadata."
        )
    
    async def register_local_endpoint(
        self,
        host: str,
        port: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record local endpoint (no external registration).
        
        Args:
            host: Local bind address
            port: Local bind port
            metadata: Optional metadata (ignored)
        """
        self.local_endpoint = (host, port)
        logger.info(f"Local endpoint: {host}:{port} (manual coordination)")
    
    async def unregister_endpoint(self) -> None:
        """Unregister local endpoint (no-op for manual)."""
        self.local_endpoint = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get manual coordination statistics."""
        return {
            'strategy': self.strategy.value,
            'local_endpoint': self.local_endpoint,
            'configured_peers': len(self.peer_endpoints),
            'peer_list': [
                {
                    'node_id': node_id.hex()[:8],
                    'endpoint': f"{host}:{port}"
                }
                for node_id, (host, port) in self.peer_endpoints.items()
            ]
        }
