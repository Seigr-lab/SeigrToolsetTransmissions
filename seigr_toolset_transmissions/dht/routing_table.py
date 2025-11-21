"""
Kademlia routing table implementation.

Stores peers organized by XOR distance for efficient DHT lookups.
"""

import asyncio
import time
from typing import List, Optional, Set, Tuple
from dataclasses import dataclass, field
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DHTContact:
    """Contact information for a DHT peer."""
    
    node_id: bytes
    host: str
    port: int
    last_seen: float = field(default_factory=time.time)
    
    def __hash__(self):
        return hash(self.node_id)
    
    def __eq__(self, other):
        if isinstance(other, DHTContact):
            return self.node_id == other.node_id
        return False


class KBucket:
    """
    K-bucket for storing contacts at a specific distance range.
    
    Implements Kademlia's bucket replacement policy:
    - LRU eviction when full
    - Prefer stable long-lived nodes
    """
    
    def __init__(self, k: int = 20, max_size: int = 20):
        """
        Initialize k-bucket.
        
        Args:
            k: Replication parameter (typical value: 20)
            max_size: Maximum contacts per bucket
        """
        self.k = k
        self.max_size = max_size
        self.contacts: List[DHTContact] = []
        self._lock = asyncio.Lock()
    
    async def add_contact(self, contact: DHTContact) -> bool:
        """
        Add contact to bucket (LRU policy).
        
        Args:
            contact: Contact to add
            
        Returns:
            True if added, False if bucket full
        """
        async with self._lock:
            # Update if already exists
            for i, c in enumerate(self.contacts):
                if c.node_id == contact.node_id:
                    # Move to end (most recently seen)
                    self.contacts.pop(i)
                    self.contacts.append(contact)
                    return True
            
            # Add if not full
            if len(self.contacts) < self.max_size:
                self.contacts.append(contact)
                return True
            
            # Bucket full - could implement replacement logic here
            # For now, reject new contact (prefer stable nodes)
            logger.debug(f"Bucket full, rejecting contact {contact.node_id.hex()[:8]}")
            return False
    
    async def remove_contact(self, node_id: bytes) -> bool:
        """Remove contact from bucket."""
        async with self._lock:
            for i, c in enumerate(self.contacts):
                if c.node_id == node_id:
                    self.contacts.pop(i)
                    return True
            return False
    
    async def get_contacts(self) -> List[DHTContact]:
        """Get all contacts in bucket."""
        async with self._lock:
            return list(self.contacts)
    
    async def update_last_seen(self, node_id: bytes):
        """Update last seen time for a contact."""
        async with self._lock:
            for contact in self.contacts:
                if contact.node_id == node_id:
                    contact.last_seen = time.time()
                    # Move to end (most recently seen)
                    self.contacts.remove(contact)
                    self.contacts.append(contact)
                    break


class RoutingTable:
    """
    Kademlia routing table.
    
    Organizes peers into buckets based on XOR distance.
    Implements efficient nearest neighbor lookup for DHT operations.
    """
    
    def __init__(self, node_id: bytes, k: int = 20):
        """
        Initialize routing table.
        
        Args:
            node_id: This node's ID (32 bytes)
            k: Replication parameter
        """
        self.node_id = node_id
        self.k = k
        # 256 buckets for 256-bit (32-byte) node IDs
        self.buckets: List[KBucket] = [KBucket(k=k) for _ in range(256)]
        self._lock = asyncio.Lock()
    
    def _bucket_index(self, node_id: bytes) -> int:
        """
        Calculate bucket index based on XOR distance.
        
        Args:
            node_id: Peer node ID
            
        Returns:
            Bucket index (0-255)
        """
        # XOR distance
        distance = int.from_bytes(
            bytes(a ^ b for a, b in zip(self.node_id, node_id)),
            'big'
        )
        
        if distance == 0:
            return 0
        
        # Leading zeros = bucket index
        return distance.bit_length() - 1
    
    async def add_contact(self, contact: DHTContact) -> bool:
        """
        Add contact to routing table.
        
        Args:
            contact: Contact to add
            
        Returns:
            True if added successfully
        """
        if contact.node_id == self.node_id:
            return False  # Don't add self
        
        bucket_idx = self._bucket_index(contact.node_id)
        return await self.buckets[bucket_idx].add_contact(contact)
    
    async def remove_contact(self, node_id: bytes) -> bool:
        """Remove contact from routing table."""
        bucket_idx = self._bucket_index(node_id)
        return await self.buckets[bucket_idx].remove_contact(node_id)
    
    async def find_closest(self, target_id: bytes, count: int = None) -> List[DHTContact]:
        """
        Find closest contacts to target ID.
        
        Args:
            target_id: Target node/content ID
            count: Number of contacts to return (default: k)
            
        Returns:
            List of closest contacts sorted by distance
        """
        if count is None:
            count = self.k
        
        # Collect all contacts
        all_contacts = []
        for bucket in self.buckets:
            all_contacts.extend(await bucket.get_contacts())
        
        # Sort by XOR distance
        def xor_distance(contact: DHTContact) -> int:
            return int.from_bytes(
                bytes(a ^ b for a, b in zip(target_id, contact.node_id)),
                'big'
            )
        
        all_contacts.sort(key=xor_distance)
        return all_contacts[:count]
    
    async def get_all_contacts(self) -> List[DHTContact]:
        """Get all contacts in routing table."""
        all_contacts = []
        for bucket in self.buckets:
            all_contacts.extend(await bucket.get_contacts())
        return all_contacts
    
    async def update_last_seen(self, node_id: bytes):
        """Update last seen time for a contact."""
        bucket_idx = self._bucket_index(node_id)
        await self.buckets[bucket_idx].update_last_seen(node_id)
