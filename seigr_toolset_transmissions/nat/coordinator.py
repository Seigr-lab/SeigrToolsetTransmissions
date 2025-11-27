"""
NAT Coordinator interface - pluggable NAT traversal strategies.

STT core doesn't care HOW connections are established - only that it
receives (host, port) tuples to connect to. NAT coordinators implement
the strategy for discovering peer addresses.
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any
from enum import Enum


class NATStrategy(Enum):
    """NAT traversal strategies."""
    MANUAL = "manual"  # Requires port forwarding or public IP
    RELAY = "relay"  # Route through third-party relay node
    STUN = "stun"  # Hole punching via STUN server
    TURN = "turn"  # Full relay via TURN server
    CUSTOM = "custom"  # Application-specific logic


class NATCoordinator(ABC):
    """
    Abstract interface for NAT coordination.
    
    Implementations decide HOW to discover peer addresses.
    STT just uses the resulting (host, port) to connect.
    """
    
    def __init__(self, local_node_id: bytes, strategy: NATStrategy):
        """
        Initialize NAT coordinator.
        
        Args:
            local_node_id: This node's identifier
            strategy: NAT strategy being used
        """
        self.local_node_id = local_node_id
        self.strategy = strategy
    
    @abstractmethod
    async def get_peer_endpoint(
        self, 
        peer_node_id: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, int]:
        """
        Get endpoint (host, port) for connecting to peer.
        
        This is where NAT magic happens. Different implementations:
        - Manual: Return pre-configured address
        - Relay: Return relay server address
        - STUN: Perform hole punching, return peer's public endpoint
        - TURN: Return TURN server address
        - Custom: Application-specific discovery logic
        
        Args:
            peer_node_id: Peer's node identifier
            metadata: Optional metadata (e.g., relay hints, STUN servers)
            
        Returns:
            Tuple of (host, port) to connect to
            
        Raises:
            NATCoordinationError: If endpoint cannot be determined
        """
        pass
    
    @abstractmethod
    async def register_local_endpoint(
        self,
        host: str,
        port: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register this node's endpoint for others to discover.
        
        Different implementations:
        - Manual: No-op (assumes manual coordination)
        - Relay: Register with relay server
        - STUN: Discover public IP and register
        - TURN: Register with TURN server
        - Custom: Application-specific registration
        
        Args:
            host: Local bind address
            port: Local bind port
            metadata: Optional metadata (e.g., transport type)
        """
        pass
    
    @abstractmethod
    async def unregister_endpoint(self) -> None:
        """
        Unregister this node's endpoint.
        
        Called when node shuts down or changes address.
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Get NAT coordination statistics.
        
        Returns:
            Dictionary with strategy-specific stats
        """
        pass


class NATCoordinationError(Exception):
    """Raised when NAT coordination fails."""
    pass
