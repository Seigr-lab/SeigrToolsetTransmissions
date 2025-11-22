"""
Agnostic endpoint management - NO assumptions about peer semantics.

Manages connections to multiple endpoints.
User defines what endpoints mean (peers? nodes? servers? user decides).
"""

import asyncio
from typing import Dict, List, Tuple, Optional, Set, Union
import time

from ..utils.exceptions import STTEndpointError


class EndpointManager:
    """
    Manage multiple binary transport endpoints.
    
    NO assumptions about:
    - What endpoints represent (peers? servers? nodes? user decides)
    - Network topology (user defines)
    - Routing logic (user implements)
    
    Provides:
    - Endpoint lifecycle (connect/disconnect)
    - Multi-endpoint send (one-to-one, one-to-many)
    - Receive routing (from any, from specific)
    """
    
    def __init__(self, transport_send_callback=None):
        """
        Initialize endpoint manager.
        
        Args:
            transport_send_callback: Optional callback for actual transport send
                                    Signature: async def(endpoint_id: bytes, data: bytes) -> None
        """
        # Endpoint registry (endpoint_id -> metadata)
        self._endpoints: Dict[bytes, dict] = {}
        
        # Receive queues (endpoint_id -> asyncio.Queue)
        self._receive_queues: Dict[bytes, asyncio.Queue] = {}
        
        # Global receive queue (for receive_any())
        self._global_queue: asyncio.Queue = asyncio.Queue()
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Transport layer callback
        self._transport_send = transport_send_callback
    
    async def add_endpoint(
        self,
        endpoint_id: bytes,
        address: Union[Tuple[str, int], str],
        metadata: Optional[dict] = None
    ) -> None:
        """
        Add endpoint to manager.
        
        Args:
            endpoint_id: Unique identifier (user defines - could be node_id, session_id, etc.)
            address: Network address (ip, port) tuple or string
            metadata: Optional user-defined metadata (user decides structure)
        
        Example:
            await endpoints.add_endpoint(
                endpoint_id=node_id,
                address=("192.168.1.100", 9000),
                metadata={"type": "relay", "trust": 0.95}  # User defines
            )
        """
        async with self._lock:
            if endpoint_id in self._endpoints:
                raise STTEndpointError(f"Endpoint already exists: {endpoint_id.hex()[:16]}...")
            
            self._endpoints[endpoint_id] = {
                'address': address,
                'metadata': metadata or {},
                'connected_at': time.time(),
                'bytes_sent': 0,
                'bytes_received': 0,
                'last_activity': time.time()
            }
            
            # Create receive queue for this endpoint
            self._receive_queues[endpoint_id] = asyncio.Queue()
    
    async def remove_endpoint(self, endpoint_id: bytes) -> None:
        """
        Remove endpoint from manager.
        
        Args:
            endpoint_id: Endpoint to remove
        """
        async with self._lock:
            if endpoint_id not in self._endpoints:
                raise STTEndpointError(f"Endpoint not found: {endpoint_id.hex()[:16]}...")
            
            del self._endpoints[endpoint_id]
            
            # Clear receive queue
            if endpoint_id in self._receive_queues:
                del self._receive_queues[endpoint_id]
    
    async def send_to(self, endpoint_id: bytes, data: bytes) -> None:
        """
        Send opaque bytes to specific endpoint.
        
        Args:
            endpoint_id: Target endpoint
            data: Arbitrary bytes (user defines meaning)
        
        Raises:
            STTEndpointError: If endpoint not found
        
        Example:
            await endpoints.send_to(peer_id, b"binary data")
        """
        async with self._lock:
            if endpoint_id not in self._endpoints:
                raise STTEndpointError(f"Endpoint not found: {endpoint_id.hex()[:16]}...")
            
            # Send via transport layer callback if available
            if self._transport_send:
                await self._transport_send(endpoint_id, data)
            
            # Update stats
            self._endpoints[endpoint_id]['bytes_sent'] += len(data)
            self._endpoints[endpoint_id]['last_activity'] = time.time()
    
    async def send_to_many(
        self,
        endpoint_ids: List[bytes],
        data: bytes
    ) -> Dict[bytes, bool]:
        """
        Send opaque bytes to multiple endpoints (multicast).
        
        Args:
            endpoint_ids: List of target endpoints
            data: Arbitrary bytes (same bytes to all endpoints)
        
        Returns:
            dict mapping endpoint_id -> success (True/False)
        
        Example:
            results = await endpoints.send_to_many(
                [peer1_id, peer2_id, peer3_id],
                b"broadcast message"
            )
        """
        results = {}
        
        for endpoint_id in endpoint_ids:
            try:
                await self.send_to(endpoint_id, data)
                results[endpoint_id] = True
            except STTEndpointError:
                results[endpoint_id] = False
        
        return results
    
    async def receive_from(
        self,
        endpoint_id: bytes,
        timeout: Optional[float] = None
    ) -> bytes:
        """
        Receive bytes from specific endpoint.
        
        Args:
            endpoint_id: Endpoint to receive from
            timeout: Optional timeout in seconds
        
        Returns:
            bytes: Received data (opaque - user interprets)
        
        Raises:
            STTEndpointError: If endpoint not found or timeout
        
        Example:
            data = await endpoints.receive_from(peer_id, timeout=5.0)
            # User interprets data
        """
        if endpoint_id not in self._receive_queues:
            raise STTEndpointError(f"Endpoint not found: {endpoint_id.hex()[:16]}...")
        
        queue = self._receive_queues[endpoint_id]
        
        try:
            if timeout is not None:
                data = await asyncio.wait_for(queue.get(), timeout=timeout)
            else:
                data = await queue.get()
            
            # Update stats
            async with self._lock:
                if endpoint_id in self._endpoints:
                    self._endpoints[endpoint_id]['bytes_received'] += len(data)
                    self._endpoints[endpoint_id]['last_activity'] = time.time()
            
            return data
        
        except asyncio.TimeoutError:
            raise STTEndpointError(f"Receive timeout from {endpoint_id.hex()[:16]}...")
    
    async def receive_any(
        self,
        timeout: Optional[float] = None
    ) -> Tuple[bytes, bytes]:
        """
        Receive bytes from any endpoint.
        
        Args:
            timeout: Optional timeout in seconds
        
        Returns:
            (data, endpoint_id): Received bytes and source endpoint
        
        Example:
            data, source_id = await endpoints.receive_any()
            # User interprets data and decides what to do based on source
        """
        try:
            if timeout is not None:
                item = await asyncio.wait_for(self._global_queue.get(), timeout=timeout)
            else:
                item = await self._global_queue.get()
            
            data, endpoint_id = item
            
            # Update stats
            async with self._lock:
                if endpoint_id in self._endpoints:
                    self._endpoints[endpoint_id]['bytes_received'] += len(data)
                    self._endpoints[endpoint_id]['last_activity'] = time.time()
            
            return data, endpoint_id
        
        except asyncio.TimeoutError:
            raise STTEndpointError("Receive timeout from any endpoint")
    
    async def _enqueue_received(self, endpoint_id: bytes, data: bytes) -> None:
        """
        Internal: enqueue received data.
        
        Called by transport layer when data arrives.
        """
        # Add to endpoint-specific queue
        if endpoint_id in self._receive_queues:
            await self._receive_queues[endpoint_id].put(data)
        
        # Add to global queue
        await self._global_queue.put((data, endpoint_id))
    
    def get_endpoints(self) -> List[bytes]:
        """
        Get list of all endpoint IDs.
        
        Returns:
            List of endpoint identifiers
        """
        return list(self._endpoints.keys())
    
    def get_endpoint_info(self, endpoint_id: bytes) -> Optional[dict]:
        """
        Get metadata for specific endpoint.
        
        Args:
            endpoint_id: Endpoint to query
        
        Returns:
            dict with address, metadata, stats, or None if not found
        """
        return self._endpoints.get(endpoint_id)
    
    def get_stats(self) -> dict:
        """
        Get manager statistics.
        
        Returns:
            dict with total_endpoints, active_endpoints, total traffic
        """
        total_sent = sum(ep['bytes_sent'] for ep in self._endpoints.values())
        total_received = sum(ep['bytes_received'] for ep in self._endpoints.values())
        
        return {
            'total_endpoints': len(self._endpoints),
            'total_bytes_sent': total_sent,
            'total_bytes_received': total_received
        }
