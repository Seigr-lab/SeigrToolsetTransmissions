"""
Relay Server for NAT Traversal.

Lightweight UDP relay server that:
1. Accepts node registrations
2. Maintains registry of node endpoints
3. Answers peer lookup queries
4. Forwards frames between peers (when needed)

Protocol Messages:
- register: Node registers its endpoint
- keep_alive: Node refreshes registration
- unregister: Node removes registration
- lookup: Query for peer's endpoint
- forward: Forward frame to peer
"""

import asyncio
import json
import logging
import time
from typing import Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class RegisteredNode:
    """Information about a registered node."""
    node_id: str
    host: str
    port: int
    registered_at: float
    last_keep_alive: float
    metadata: Dict = field(default_factory=dict)
    
    def is_expired(self, timeout: float = 90.0) -> bool:
        """Check if registration expired (no keep-alive)."""
        return time.time() - self.last_keep_alive > timeout


class RelayServer:
    """
    UDP-based relay server for NAT traversal.
    
    Features:
    - Node registration and discovery
    - Keep-alive tracking
    - Peer endpoint lookup
    - Frame forwarding (optional)
    - Connection statistics
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",  # Default to localhost, use '0.0.0.0' for public relay
        port: int = 9000,
        registration_timeout: float = 90.0,
        enable_forwarding: bool = True
    ):
        """
        Initialize relay server.
        
        Args:
            host: Bind address (0.0.0.0 for all interfaces)
            port: UDP port
            registration_timeout: Node expiration time (seconds)
            enable_forwarding: Enable frame forwarding
        """
        self.host = host
        self.port = port
        self.registration_timeout = registration_timeout
        self.enable_forwarding = enable_forwarding
        
        # Node registry: node_id -> RegisteredNode
        self.nodes: Dict[str, RegisteredNode] = {}
        
        # Statistics
        self.stats = {
            'registrations': 0,
            'unregistrations': 0,
            'keep_alives': 0,
            'lookups': 0,
            'lookup_hits': 0,
            'lookup_misses': 0,
            'forwards': 0,
            'bytes_forwarded': 0,
        }
        
        # Server state
        self._running = False
        self._socket: Optional[asyncio.DatagramTransport] = None
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the relay server."""
        logger.info(f"Starting relay server on {self.host}:{self.port}")
        
        loop = asyncio.get_event_loop()
        
        # Create UDP endpoint
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: RelayProtocol(self),
            local_addr=(self.host, self.port)
        )
        
        self._socket = transport
        self._running = True
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info(f"Relay server listening on {self.host}:{self.port}")
    
    async def stop(self) -> None:
        """Stop the relay server."""
        logger.info("Stopping relay server")
        
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self._socket:
            self._socket.close()
        
        logger.info("Relay server stopped")
    
    async def _cleanup_loop(self) -> None:
        """Periodically remove expired registrations."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Cleanup every 30 seconds
                
                expired = [
                    node_id for node_id, node in self.nodes.items()
                    if node.is_expired(self.registration_timeout)
                ]
                
                for node_id in expired:
                    logger.info(f"Removing expired node: {node_id[:8]}")
                    del self.nodes[node_id]
                
                if expired:
                    logger.info(f"Cleaned up {len(expired)} expired registrations")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    def handle_message(
        self,
        data: bytes,
        addr: Tuple[str, int]
    ) -> Optional[bytes]:
        """
        Handle incoming message.
        
        Args:
            data: Raw message data
            addr: (host, port) of sender
            
        Returns:
            Response bytes to send, or None
        """
        try:
            msg = json.loads(data.decode('utf-8'))
            msg_type = msg.get('type')
            
            if msg_type == 'register':
                return self._handle_register(msg, addr)
            elif msg_type == 'keep_alive':
                return self._handle_keep_alive(msg, addr)
            elif msg_type == 'unregister':
                return self._handle_unregister(msg, addr)
            elif msg_type == 'lookup':
                return self._handle_lookup(msg, addr)
            elif msg_type == 'forward' and self.enable_forwarding:
                return self._handle_forward(msg, data, addr)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
                return self._error_response("Unknown message type")
                
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from {addr}")
            return self._error_response("Invalid JSON")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return self._error_response(str(e))
    
    def _handle_register(
        self,
        msg: Dict,
        addr: Tuple[str, int]
    ) -> bytes:
        """Handle node registration."""
        node_id = msg.get('node_id')
        host = msg.get('host', addr[0])  # Use actual source if not specified
        port = msg.get('port', addr[1])
        metadata = msg.get('metadata', {})
        
        if not node_id:
            return self._error_response("Missing node_id")
        
        # Register node
        now = time.time()
        self.nodes[node_id] = RegisteredNode(
            node_id=node_id,
            host=host,
            port=port,
            registered_at=now,
            last_keep_alive=now,
            metadata=metadata
        )
        
        self.stats['registrations'] += 1
        
        logger.info(
            f"Registered node {node_id[:8]} at {host}:{port} "
            f"(total: {len(self.nodes)})"
        )
        
        return json.dumps({
            'type': 'registered',
            'node_id': node_id,
            'timestamp': now
        }).encode('utf-8')
    
    def _handle_keep_alive(
        self,
        msg: Dict,
        addr: Tuple[str, int]
    ) -> Optional[bytes]:
        """Handle keep-alive message."""
        node_id = msg.get('node_id')
        
        if node_id in self.nodes:
            self.nodes[node_id].last_keep_alive = time.time()
            self.stats['keep_alives'] += 1
            logger.debug(f"Keep-alive from {node_id[:8]}")
            
            return json.dumps({
                'type': 'alive',
                'timestamp': time.time()
            }).encode('utf-8')
        else:
            logger.warning(f"Keep-alive from unregistered node: {node_id[:8]}")
            return self._error_response("Not registered")
    
    def _handle_unregister(
        self,
        msg: Dict,
        addr: Tuple[str, int]
    ) -> Optional[bytes]:
        """Handle unregistration."""
        node_id = msg.get('node_id')
        
        if node_id in self.nodes:
            del self.nodes[node_id]
            self.stats['unregistrations'] += 1
            logger.info(f"Unregistered node {node_id[:8]} (total: {len(self.nodes)})")
        
        return json.dumps({
            'type': 'unregistered',
            'timestamp': time.time()
        }).encode('utf-8')
    
    def _handle_lookup(
        self,
        msg: Dict,
        addr: Tuple[str, int]
    ) -> bytes:
        """Handle peer lookup request."""
        peer_id = msg.get('peer_id')
        
        self.stats['lookups'] += 1
        
        if peer_id in self.nodes:
            peer = self.nodes[peer_id]
            self.stats['lookup_hits'] += 1
            
            logger.debug(f"Lookup hit: {peer_id[:8]} -> {peer.host}:{peer.port}")
            
            return json.dumps({
                'type': 'peer_info',
                'peer_id': peer_id,
                'host': peer.host,
                'port': peer.port,
                'metadata': peer.metadata,
                'timestamp': time.time()
            }).encode('utf-8')
        else:
            self.stats['lookup_misses'] += 1
            
            logger.debug(f"Lookup miss: {peer_id[:8]}")
            
            return json.dumps({
                'type': 'peer_not_found',
                'peer_id': peer_id,
                'timestamp': time.time()
            }).encode('utf-8')
    
    def _handle_forward(
        self,
        msg: Dict,
        data: bytes,
        addr: Tuple[str, int]
    ) -> None:
        """
        Handle frame forwarding request.
        
        Note: This is a simplified version. Real implementation
        would need to handle STT frame forwarding properly.
        """
        target_id = msg.get('target_id')
        
        if target_id in self.nodes:
            target = self.nodes[target_id]
            
            # In real implementation, forward the actual STT frame
            # For now, just count it
            self.stats['forwards'] += 1
            self.stats['bytes_forwarded'] += len(data)
            
            logger.debug(
                f"Forwarding {len(data)} bytes to {target_id[:8]} "
                f"at {target.host}:{target.port}"
            )
        
        return None  # No response needed for forwards
    
    def _error_response(self, error: str) -> bytes:
        """Create error response."""
        return json.dumps({
            'type': 'error',
            'error': error,
            'timestamp': time.time()
        }).encode('utf-8')
    
    def get_status(self) -> Dict:
        """Get server status and statistics."""
        return {
            'running': self._running,
            'listening': f"{self.host}:{self.port}",
            'active_nodes': len(self.nodes),
            'statistics': self.stats.copy(),
            'nodes': [
                {
                    'node_id': node.node_id[:8],
                    'endpoint': f"{node.host}:{node.port}",
                    'age': time.time() - node.registered_at,
                    'last_keep_alive': time.time() - node.last_keep_alive
                }
                for node in self.nodes.values()
            ]
        }


class RelayProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for relay server."""
    
    def __init__(self, server: RelayServer):
        self.server = server
        self.transport: Optional[asyncio.DatagramTransport] = None
    
    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        """Protocol connected."""
        self.transport = transport
    
    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handle incoming datagram."""
        response = self.server.handle_message(data, addr)
        
        if response and self.transport:
            self.transport.sendto(response, addr)
    
    def error_received(self, exc: Exception) -> None:
        """Handle protocol error."""
        logger.error(f"Protocol error: {exc}")


async def run_relay_server(
    host: str = "127.0.0.1",  # Default to localhost for security
    port: int = 9000,
    enable_forwarding: bool = True
) -> None:
    """
    Run relay server (convenience function).
    
    Args:
        host: Bind address
        port: UDP port
        enable_forwarding: Enable frame forwarding
    """
    server = RelayServer(
        host=host,
        port=port,
        enable_forwarding=enable_forwarding
    )
    
    await server.start()
    
    try:
        # Run until interrupted
        while True:
            await asyncio.sleep(60)
            
            # Print status every minute
            status = server.get_status()
            logger.info(
                f"Status: {status['active_nodes']} nodes, "
                f"{status['statistics']['lookups']} lookups "
                f"({status['statistics']['lookup_hits']} hits)"
            )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await server.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(run_relay_server())
