"""
Kademlia DHT implementation for STT.

Provides peer discovery and content-based routing for the Seigr ecosystem.
"""

import asyncio
import struct
import time
from typing import Dict, List, Optional, Set, Tuple, Callable
from dataclasses import dataclass
from enum import IntEnum

from .routing_table import RoutingTable, DHTContact
from ..utils.logging import get_logger
from ..crypto.node_identity import generate_node_id

logger = get_logger(__name__)


class DHTMessageType(IntEnum):
    """DHT RPC message types."""
    PING = 0x01
    PONG = 0x02
    FIND_NODE = 0x03
    FOUND_NODE = 0x04
    STORE = 0x05
    STORE_ACK = 0x06
    FIND_VALUE = 0x07
    FOUND_VALUE = 0x08


@dataclass
class DHTNode:
    """DHT node information."""
    node_id: bytes
    host: str
    port: int


class KademliaDHT:
    """
    Kademlia DHT for peer discovery and content routing.
    
    Implements standard Kademlia RPCs:
    - PING/PONG: Liveness check
    - FIND_NODE: Locate peers near target ID
    - STORE/FIND_VALUE: Content storage and retrieval
    """
    
    def __init__(
        self,
        node_id: bytes,
        host: str = "0.0.0.0",
        port: int = 0,
        k: int = 20,
        alpha: int = 3
    ):
        """
        Initialize Kademlia DHT.
        
        Args:
            node_id: This node's 32-byte ID
            host: Listen address
            port: Listen port (0 = auto-assign)
            k: Replication parameter (bucket size)
            alpha: Concurrency parameter for lookups
        """
        self.node_id = node_id
        self.host = host
        self.port = port
        self.k = k
        self.alpha = alpha
        
        self.routing_table = RoutingTable(node_id, k)
        self.storage: Dict[bytes, bytes] = {}  # content_id -> data
        self.providers: Dict[bytes, Set[DHTContact]] = {}  # content_id -> peers
        
        self._transport: Optional[asyncio.DatagramProtocol] = None
        self._running = False
        self._pending_responses: Dict[bytes, asyncio.Future] = {}
        
        logger.info(f"DHT initialized with node_id={node_id.hex()[:16]}...")
    
    async def start(self):
        """Start DHT server."""
        if self._running:
            return
        
        loop = asyncio.get_event_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: DHTProtocol(self),
            local_addr=(self.host, self.port)
        )
        
        if self.port == 0:
            # Get assigned port
            sock = self._transport.get_extra_info('socket')
            self.port = sock.getsockname()[1]
        
        self._running = True
        logger.info(f"DHT listening on {self.host}:{self.port}")
    
    async def stop(self):
        """Stop DHT server."""
        if not self._running:
            return
        
        self._running = False
        if self._transport:
            self._transport.close()
        
        # Cancel pending requests
        for future in self._pending_responses.values():
            if not future.done():
                future.cancel()
        self._pending_responses.clear()
        
        logger.info("DHT stopped")
    
    async def bootstrap(self, bootstrap_nodes: List[DHTNode]):
        """
        Bootstrap DHT by connecting to known peers.
        
        Args:
            bootstrap_nodes: List of known DHT nodes to connect to
        """
        logger.info(f"Bootstrapping with {len(bootstrap_nodes)} nodes")
        
        # Add bootstrap nodes to routing table
        for node in bootstrap_nodes:
            contact = DHTContact(node.node_id, node.host, node.port)
            await self.routing_table.add_contact(contact)
        
        # Perform self-lookup to populate routing table
        await self.find_node(self.node_id)
    
    async def ping(self, contact: DHTContact) -> bool:
        """
        Send PING to peer.
        
        Args:
            contact: Peer to ping
            
        Returns:
            True if peer responded
        """
        msg = self._encode_message(DHTMessageType.PING, {
            'node_id': self.node_id
        })
        
        try:
            response = await self._send_request(contact, msg, timeout=5.0)
            if response and response.get('type') == DHTMessageType.PONG:
                await self.routing_table.update_last_seen(contact.node_id)
                return True
        except asyncio.TimeoutError:
            logger.debug(f"Ping timeout: {contact.node_id.hex()[:8]}")
        
        return False
    
    async def find_node(self, target_id: bytes) -> List[DHTContact]:
        """
        Find k closest nodes to target ID.
        
        Args:
            target_id: Target node/content ID
            
        Returns:
            List of closest contacts
        """
        # Start with closest known contacts
        closest = await self.routing_table.find_closest(target_id, self.k)
        
        if not closest:
            return []
        
        queried: Set[bytes] = set()
        shortlist = set(closest)
        
        # Iterative lookup
        while True:
            # Find unqueried nodes from shortlist
            unqueried = [c for c in shortlist if c.node_id not in queried]
            
            if not unqueried:
                break
            
            # Query alpha closest unqueried nodes
            to_query = sorted(
                unqueried,
                key=lambda c: self._xor_distance(target_id, c.node_id)
            )[:self.alpha]
            
            # Send FIND_NODE requests
            tasks = []
            for contact in to_query:
                queried.add(contact.node_id)
                tasks.append(self._find_node_rpc(contact, target_id))
            
            # Gather responses
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Add new contacts to shortlist
            for result in results:
                if isinstance(result, list):
                    for contact in result:
                        shortlist.add(contact)
                        await self.routing_table.add_contact(contact)
            
            # Keep only k closest
            shortlist = set(sorted(
                shortlist,
                key=lambda c: self._xor_distance(target_id, c.node_id)
            )[:self.k])
        
        return sorted(
            shortlist,
            key=lambda c: self._xor_distance(target_id, c.node_id)
        )[:self.k]
    
    async def store(self, content_id: bytes, data: bytes) -> int:
        """
        Store data in DHT.
        
        Args:
            content_id: Content identifier (hash)
            data: Data to store
            
        Returns:
            Number of peers that stored the data
        """
        # Find k closest nodes to content_id
        closest = await self.find_node(content_id)
        
        # Store on local node
        self.storage[content_id] = data
        
        # Store on remote peers
        tasks = []
        for contact in closest[:self.k]:
            tasks.append(self._store_rpc(contact, content_id, data))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        stored_count = 1  # Local storage
        for result in results:
            if result is True:
                stored_count += 1
        
        logger.info(f"Stored content {content_id.hex()[:16]} on {stored_count} nodes")
        return stored_count
    
    async def find_value(self, content_id: bytes) -> Optional[bytes]:
        """
        Find value in DHT.
        
        Args:
            content_id: Content identifier
            
        Returns:
            Data if found, None otherwise
        """
        # Check local storage first
        if content_id in self.storage:
            return self.storage[content_id]
        
        # Iterative lookup similar to find_node, but looking for value
        closest = await self.routing_table.find_closest(content_id, self.k)
        
        if not closest:
            return None
        
        queried: Set[bytes] = set()
        shortlist = set(closest)
        
        while True:
            unqueried = [c for c in shortlist if c.node_id not in queried]
            
            if not unqueried:
                break
            
            to_query = sorted(
                unqueried,
                key=lambda c: self._xor_distance(content_id, c.node_id)
            )[:self.alpha]
            
            tasks = []
            for contact in to_query:
                queried.add(contact.node_id)
                tasks.append(self._find_value_rpc(contact, content_id))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check if any returned the value
            for result in results:
                if isinstance(result, bytes):
                    # Found the value!
                    self.storage[content_id] = result  # Cache locally
                    return result
                elif isinstance(result, list):
                    # Got more contacts
                    for contact in result:
                        shortlist.add(contact)
                        await self.routing_table.add_contact(contact)
            
            shortlist = set(sorted(
                shortlist,
                key=lambda c: self._xor_distance(content_id, c.node_id)
            )[:self.k])
        
        return None
    
    async def announce_provider(self, content_id: bytes):
        """
        Announce this node as a provider for content.
        
        Args:
            content_id: Content this node can provide
        """
        # Find closest nodes to content_id
        closest = await self.find_node(content_id)
        
        # Store provider info on closest nodes
        my_contact = DHTContact(self.node_id, self.host, self.port)
        
        for contact in closest[:self.k]:
            msg = self._encode_message(DHTMessageType.STORE, {
                'node_id': self.node_id,
                'content_id': content_id,
                'provider': {
                    'node_id': my_contact.node_id,
                    'host': my_contact.host,
                    'port': my_contact.port
                }
            })
            try:
                await self._send_request(contact, msg, timeout=5.0)
            except asyncio.TimeoutError:
                continue
    
    async def find_providers(self, content_id: bytes) -> List[DHTContact]:
        """
        Find providers for content.
        
        Args:
            content_id: Content to find providers for
            
        Returns:
            List of contacts that can provide the content
        """
        # Check local providers
        if content_id in self.providers:
            return list(self.providers[content_id])
        
        # Query DHT
        closest = await self.find_node(content_id)
        
        all_providers = set()
        for contact in closest:
            msg = self._encode_message(DHTMessageType.FIND_VALUE, {
                'node_id': self.node_id,
                'content_id': content_id
            })
            try:
                response = await self._send_request(contact, msg, timeout=5.0)
                if response and 'providers' in response:
                    for prov in response['providers']:
                        provider_contact = DHTContact(
                            prov['node_id'],
                            prov['host'],
                            prov['port']
                        )
                        all_providers.add(provider_contact)
            except asyncio.TimeoutError:
                continue
        
        return list(all_providers)
    
    # Internal RPC methods
    
    async def _find_node_rpc(self, contact: DHTContact, target_id: bytes) -> List[DHTContact]:
        """Send FIND_NODE RPC."""
        msg = self._encode_message(DHTMessageType.FIND_NODE, {
            'node_id': self.node_id,
            'target_id': target_id
        })
        
        try:
            response = await self._send_request(contact, msg, timeout=5.0)
            if response and 'contacts' in response:
                return [
                    DHTContact(c['node_id'], c['host'], c['port'])
                    for c in response['contacts']
                ]
        except asyncio.TimeoutError:
            pass
        
        return []
    
    async def _store_rpc(self, contact: DHTContact, content_id: bytes, data: bytes) -> bool:
        """Send STORE RPC."""
        msg = self._encode_message(DHTMessageType.STORE, {
            'node_id': self.node_id,
            'content_id': content_id,
            'data': data
        })
        
        try:
            response = await self._send_request(contact, msg, timeout=5.0)
            return response and response.get('type') == DHTMessageType.STORE_ACK
        except asyncio.TimeoutError:
            return False
    
    async def _find_value_rpc(self, contact: DHTContact, content_id: bytes):
        """Send FIND_VALUE RPC. Returns bytes if found, list of contacts otherwise."""
        msg = self._encode_message(DHTMessageType.FIND_VALUE, {
            'node_id': self.node_id,
            'content_id': content_id
        })
        
        try:
            response = await self._send_request(contact, msg, timeout=5.0)
            if response:
                if 'data' in response:
                    return response['data']
                elif 'contacts' in response:
                    return [
                        DHTContact(c['node_id'], c['host'], c['port'])
                        for c in response['contacts']
                    ]
        except asyncio.TimeoutError:
            pass
        
        return []
    
    async def _send_request(self, contact: DHTContact, msg: bytes, timeout: float = 5.0):
        """Send request and wait for response."""
        if not self._transport:
            raise RuntimeError("DHT not started")
        
        # Generate request ID
        req_id = struct.pack('!Q', int(time.time() * 1000000) & 0xFFFFFFFFFFFFFFFF)
        
        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self._pending_responses[req_id] = future
        
        # Send request
        full_msg = req_id + msg
        self._transport.sendto(full_msg, (contact.host, contact.port))
        
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending_responses.pop(req_id, None)
    
    def _encode_message(self, msg_type: DHTMessageType, data: dict) -> bytes:
        """Encode DHT message (simplified - use proper serialization in production)."""
        import pickle
        payload = pickle.dumps({'type': msg_type, **data})
        return struct.pack('!B', msg_type) + payload
    
    def _decode_message(self, data: bytes) -> Optional[dict]:
        """Decode DHT message."""
        if len(data) < 1:
            return None
        
        try:
            import pickle
            msg_type = data[0]
            payload = pickle.loads(data[1:])
            return payload
        except Exception as e:
            logger.error(f"Failed to decode message: {e}")
            return None
    
    def _xor_distance(self, a: bytes, b: bytes) -> int:
        """Calculate XOR distance between two IDs."""
        return int.from_bytes(
            bytes(x ^ y for x, y in zip(a, b)),
            'big'
        )
    
    def _handle_ping(self, sender: DHTContact, msg: dict) -> bytes:
        """Handle PING request."""
        return self._encode_message(DHTMessageType.PONG, {
            'node_id': self.node_id
        })
    
    def _handle_find_node(self, sender: DHTContact, msg: dict) -> bytes:
        """Handle FIND_NODE request."""
        target_id = msg['target_id']
        closest = asyncio.create_task(
            self.routing_table.find_closest(target_id, self.k)
        )
        # Note: This is blocking - in production, use proper async handling
        contacts = asyncio.get_event_loop().run_until_complete(closest)
        
        return self._encode_message(DHTMessageType.FOUND_NODE, {
            'node_id': self.node_id,
            'contacts': [
                {'node_id': c.node_id, 'host': c.host, 'port': c.port}
                for c in contacts
            ]
        })
    
    def _handle_store(self, sender: DHTContact, msg: dict) -> bytes:
        """Handle STORE request."""
        content_id = msg['content_id']
        
        if 'data' in msg:
            # Store data
            self.storage[content_id] = msg['data']
        elif 'provider' in msg:
            # Store provider info
            provider = msg['provider']
            provider_contact = DHTContact(
                provider['node_id'],
                provider['host'],
                provider['port']
            )
            if content_id not in self.providers:
                self.providers[content_id] = set()
            self.providers[content_id].add(provider_contact)
        
        return self._encode_message(DHTMessageType.STORE_ACK, {
            'node_id': self.node_id
        })
    
    def _handle_find_value(self, sender: DHTContact, msg: dict) -> bytes:
        """Handle FIND_VALUE request."""
        content_id = msg['content_id']
        
        # Check local storage
        if content_id in self.storage:
            return self._encode_message(DHTMessageType.FOUND_VALUE, {
                'node_id': self.node_id,
                'data': self.storage[content_id]
            })
        
        # Check providers
        if content_id in self.providers:
            return self._encode_message(DHTMessageType.FOUND_VALUE, {
                'node_id': self.node_id,
                'providers': [
                    {'node_id': p.node_id, 'host': p.host, 'port': p.port}
                    for p in self.providers[content_id]
                ]
            })
        
        # Return closest nodes
        closest = asyncio.create_task(
            self.routing_table.find_closest(content_id, self.k)
        )
        contacts = asyncio.get_event_loop().run_until_complete(closest)
        
        return self._encode_message(DHTMessageType.FOUND_VALUE, {
            'node_id': self.node_id,
            'contacts': [
                {'node_id': c.node_id, 'host': c.host, 'port': c.port}
                for c in contacts
            ]
        })


class DHTProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for DHT."""
    
    def __init__(self, dht: KademliaDHT):
        self.dht = dht
    
    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        """Handle incoming DHT message."""
        if len(data) < 9:  # req_id (8 bytes) + type (1 byte)
            return
        
        req_id = data[:8]
        msg_data = data[8:]
        
        msg = self.dht._decode_message(msg_data)
        if not msg:
            return
        
        msg_type = msg.get('type')
        sender_id = msg.get('node_id')
        
        if not sender_id:
            return
        
        sender = DHTContact(sender_id, addr[0], addr[1])
        
        # Update routing table
        asyncio.create_task(self.dht.routing_table.add_contact(sender))
        
        # Handle request or response
        if req_id in self.dht._pending_responses:
            # This is a response to our request
            future = self.dht._pending_responses[req_id]
            if not future.done():
                future.set_result(msg)
        else:
            # This is a new request
            response = None
            
            if msg_type == DHTMessageType.PING:
                response = self.dht._handle_ping(sender, msg)
            elif msg_type == DHTMessageType.FIND_NODE:
                response = self.dht._handle_find_node(sender, msg)
            elif msg_type == DHTMessageType.STORE:
                response = self.dht._handle_store(sender, msg)
            elif msg_type == DHTMessageType.FIND_VALUE:
                response = self.dht._handle_find_value(sender, msg)
            
            if response:
                # Send response with same req_id
                self.transport.sendto(req_id + response, addr)
