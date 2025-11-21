"""
Content distribution system using DHT for the Seigr ecosystem.

Enables publishing, discovering, and retrieving binary content across
multiple peers using content-addressed storage.
"""

import asyncio
import struct
from typing import List, Optional, Callable, Dict, Set
from dataclasses import dataclass
from pathlib import Path

from ..dht import KademliaDHT, DHTNode
from ..utils.logging import get_logger
from ..crypto import context as stc_context

logger = get_logger(__name__)


@dataclass
class ContentChunk:
    """A chunk of content."""
    content_id: bytes  # Hash of complete content
    chunk_index: int   # Index of this chunk
    total_chunks: int  # Total number of chunks
    data: bytes        # Chunk data


class ContentDistribution:
    """
    Content distribution system using DHT.
    
    Provides:
    - Content publishing (announce to DHT)
    - Content discovery (find providers)
    - Parallel chunk retrieval from multiple peers
    - Pub/sub for content updates
    """
    
    def __init__(
        self,
        dht: KademliaDHT,
        node_id: bytes,
        chunk_size: int = 256 * 1024  # 256KB chunks
    ):
        """
        Initialize content distribution.
        
        Args:
            dht: Kademlia DHT instance
            node_id: This node's ID
            chunk_size: Size of content chunks
        """
        self.dht = dht
        self.node_id = node_id
        self.chunk_size = chunk_size
        
        # Local content storage
        self.content_store: Dict[bytes, bytes] = {}  # content_id -> full_data
        self.chunk_store: Dict[tuple, bytes] = {}  # (content_id, chunk_idx) -> chunk_data
        
        # Subscriptions
        self.subscriptions: Dict[bytes, List[Callable]] = {}  # content_id -> callbacks
        
        logger.info("Content distribution initialized")
    
    def compute_content_id(self, data: bytes) -> bytes:
        """
        Compute content ID (hash).
        
        Args:
            data: Content data
            
        Returns:
            32-byte content ID
        """
        ctx = stc_context.get_context()
        return ctx.hash(data)
    
    def split_into_chunks(self, data: bytes) -> List[ContentChunk]:
        """
        Split content into chunks.
        
        Args:
            data: Content data
            
        Returns:
            List of content chunks
        """
        content_id = self.compute_content_id(data)
        
        chunks = []
        total_chunks = (len(data) + self.chunk_size - 1) // self.chunk_size
        
        for i in range(total_chunks):
            start = i * self.chunk_size
            end = min(start + self.chunk_size, len(data))
            chunk_data = data[start:end]
            
            chunks.append(ContentChunk(
                content_id=content_id,
                chunk_index=i,
                total_chunks=total_chunks,
                data=chunk_data
            ))
        
        return chunks
    
    async def publish_content(self, data: bytes, persist: bool = True) -> bytes:
        """
        Publish content to DHT.
        
        Args:
            data: Content to publish
            persist: If True, store locally and announce as provider
            
        Returns:
            Content ID
        """
        content_id = self.compute_content_id(data)
        
        if persist:
            # Store locally
            self.content_store[content_id] = data
            
            # Split into chunks and store
            chunks = self.split_into_chunks(data)
            for chunk in chunks:
                chunk_key = (content_id, chunk.chunk_index)
                self.chunk_store[chunk_key] = chunk.data
            
            # Announce as provider in DHT
            await self.dht.announce_provider(content_id)
            
            logger.info(
                f"Published content: id={content_id.hex()[:16]}... "
                f"size={len(data)} chunks={len(chunks)}"
            )
        else:
            # Just store in DHT (distributed)
            await self.dht.store(content_id, data)
            
            logger.info(f"Stored content in DHT: id={content_id.hex()[:16]}...")
        
        return content_id
    
    async def retrieve_content(
        self,
        content_id: bytes,
        parallel_sources: int = 3
    ) -> Optional[bytes]:
        """
        Retrieve content from DHT with parallel chunk fetching.
        
        Args:
            content_id: Content identifier
            parallel_sources: Number of parallel sources to fetch from
            
        Returns:
            Content data if found
        """
        # Check local storage first
        if content_id in self.content_store:
            logger.debug(f"Content found locally: {content_id.hex()[:16]}...")
            return self.content_store[content_id]
        
        # Try DHT value lookup (small content may be stored directly)
        data = await self.dht.find_value(content_id)
        if data:
            logger.info(f"Content found in DHT: {content_id.hex()[:16]}...")
            return data
        
        # Find providers
        providers = await self.dht.find_providers(content_id)
        
        if not providers:
            logger.warning(f"No providers found for content: {content_id.hex()[:16]}...")
            return None
        
        logger.info(f"Found {len(providers)} providers for content {content_id.hex()[:16]}...")
        
        # Fetch chunks in parallel from multiple providers
        # This is a simplified implementation - production would need:
        # 1. Actual chunk transfer protocol
        # 2. Verification of chunk hashes
        # 3. Retry logic for failed chunks
        # 4. Bandwidth management
        
        # For now, just try providers sequentially
        for provider in providers[:parallel_sources]:
            # In real implementation, would connect to provider and request chunks
            # For now, simulate by checking if we're the provider
            if provider.node_id == self.node_id and content_id in self.content_store:
                return self.content_store[content_id]
        
        logger.warning(f"Failed to retrieve content from providers")
        return None
    
    async def subscribe(self, content_id: bytes, callback: Callable[[bytes], None]):
        """
        Subscribe to content updates.
        
        Args:
            content_id: Content to subscribe to
            callback: Function to call when content is updated
        """
        if content_id not in self.subscriptions:
            self.subscriptions[content_id] = []
        
        self.subscriptions[content_id].append(callback)
        
        # Find current providers and monitor
        providers = await self.dht.find_providers(content_id)
        
        logger.info(
            f"Subscribed to content: {content_id.hex()[:16]}... "
            f"(providers={len(providers)})"
        )
    
    async def unsubscribe(self, content_id: bytes, callback: Callable[[bytes], None]):
        """
        Unsubscribe from content updates.
        
        Args:
            content_id: Content ID
            callback: Callback to remove
        """
        if content_id in self.subscriptions:
            self.subscriptions[content_id].remove(callback)
            
            if not self.subscriptions[content_id]:
                del self.subscriptions[content_id]
    
    async def notify_subscribers(self, content_id: bytes, new_data: bytes):
        """
        Notify subscribers of content update.
        
        Args:
            content_id: Updated content ID
            new_data: New content data
        """
        if content_id in self.subscriptions:
            for callback in self.subscriptions[content_id]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(new_data)
                    else:
                        callback(new_data)
                except Exception as e:
                    logger.error(f"Subscriber callback error: {e}")
    
    def get_chunk(self, content_id: bytes, chunk_index: int) -> Optional[bytes]:
        """
        Get a specific chunk from local storage.
        
        Args:
            content_id: Content ID
            chunk_index: Chunk index
            
        Returns:
            Chunk data if available
        """
        chunk_key = (content_id, chunk_index)
        return self.chunk_store.get(chunk_key)
    
    def get_stats(self) -> dict:
        """Get content distribution statistics."""
        total_content_size = sum(len(data) for data in self.content_store.values())
        total_chunks = len(self.chunk_store)
        
        return {
            'content_items': len(self.content_store),
            'total_content_bytes': total_content_size,
            'chunks_stored': total_chunks,
            'subscriptions': len(self.subscriptions),
            'chunk_size': self.chunk_size,
        }


class PubSubManager:
    """
    Publish-Subscribe manager using DHT.
    
    Enables topic-based pub/sub for Seigr ecosystem.
    """
    
    def __init__(self, dht: KademliaDHT, content_dist: ContentDistribution):
        """
        Initialize pub/sub manager.
        
        Args:
            dht: DHT instance
            content_dist: Content distribution instance
        """
        self.dht = dht
        self.content_dist = content_dist
        
        # Topic subscriptions
        self.topics: Dict[str, Set[Callable]] = {}
        
        logger.info("Pub/sub manager initialized")
    
    def topic_to_id(self, topic: str) -> bytes:
        """Convert topic name to content ID."""
        ctx = stc_context.get_context()
        return ctx.hash(topic.encode('utf-8'))
    
    async def publish(self, topic: str, data: bytes):
        """
        Publish data to topic.
        
        Args:
            topic: Topic name
            data: Data to publish
        """
        topic_id = self.topic_to_id(topic)
        
        # Publish as content
        await self.content_dist.publish_content(data, persist=False)
        
        # Announce to DHT
        await self.dht.announce_provider(topic_id)
        
        logger.info(f"Published to topic '{topic}': {len(data)} bytes")
    
    async def subscribe(self, topic: str, callback: Callable[[bytes], None]):
        """
        Subscribe to topic.
        
        Args:
            topic: Topic name
            callback: Function to call with published data
        """
        if topic not in self.topics:
            self.topics[topic] = set()
        
        self.topics[topic].add(callback)
        
        # Subscribe via content distribution
        topic_id = self.topic_to_id(topic)
        await self.content_dist.subscribe(topic_id, callback)
        
        logger.info(f"Subscribed to topic '{topic}'")
    
    async def unsubscribe(self, topic: str, callback: Callable[[bytes], None]):
        """
        Unsubscribe from topic.
        
        Args:
            topic: Topic name
            callback: Callback to remove
        """
        if topic in self.topics:
            self.topics[topic].discard(callback)
            
            if not self.topics[topic]:
                del self.topics[topic]
        
        topic_id = self.topic_to_id(topic)
        await self.content_dist.unsubscribe(topic_id, callback)
    
    def get_stats(self) -> dict:
        """Get pub/sub statistics."""
        return {
            'topics': len(self.topics),
            'total_subscribers': sum(len(subs) for subs in self.topics.values()),
        }
