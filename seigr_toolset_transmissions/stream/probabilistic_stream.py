"""
Probabilistic Delivery Streams - Entropy-Aware Loss Tolerance

Delivery guarantee tied to content properties:
- Shannon entropy (information density)
- DHT replication (availability)
- Application hints (optional override)

NOT "unreliable" but "probabilistically reliable"
"""

import asyncio
import math
import random
import time
from typing import Optional, List, TYPE_CHECKING
from dataclasses import dataclass

from .stream import STTStream
from ..utils.logging import get_logger
from ..utils.exceptions import STTStreamError

if TYPE_CHECKING:
    from ..dht.kademlia import KademliaDHT
    from ..crypto.stc_wrapper import STCWrapper

logger = get_logger(__name__)


@dataclass
class ChunkMetadata:
    """Metadata for probabilistic chunk delivery."""
    chunk_idx: int
    entropy: float
    delivery_prob: float
    replication: int
    attempts: int
    delivered: bool


class ProbabilisticStream(STTStream):
    """
    Stream with entropy-aware loss tolerance.
    
    BREAKS FROM TRADITION: Delivery guarantee NOT binary (reliable/unreliable).
    Adapts based on information content - high entropy requires reliable delivery.
    """
    
    def __init__(
        self,
        session_id: bytes,
        stream_id: int,
        stc_wrapper: 'STCWrapper',
        dht: Optional['KademliaDHT'] = None,
        chunk_size: int = 16384
    ):
        """
        Initialize probabilistic stream.
        
        Args:
            session_id: Parent session ID
            stream_id: Stream ID
            stc_wrapper: STC wrapper for crypto
            dht: Optional DHT for replication queries
            chunk_size: Chunk size for entropy calculation (16KB default)
        """
        super().__init__(session_id, stream_id, stc_wrapper)
        
        self.dht = dht
        self.chunk_size = chunk_size
        self.mode = 'probabilistic'
        
        # Delivery tracking
        self.delivered_chunks: set = set()
        self.chunk_metadata: dict[int, ChunkMetadata] = {}
        
        # Statistics
        self.total_chunks = 0
        self.successful_deliveries = 0
        self.probabilistic_exits = 0
        
        logger.info(
            f"ProbabilisticStream created: session={session_id.hex()[:8]}, "
            f"stream={stream_id}, chunk_size={chunk_size}"
        )
    
    def calculate_delivery_probability(self, chunk: bytes) -> float:
        """
        Calculate required delivery probability (0.0-1.0).
        
        High entropy = must deliver (0.99+)
        Low entropy = can lose (0.70)
        
        Args:
            chunk: Data chunk
            
        Returns:
            Target delivery probability
        """
        # Calculate Shannon entropy
        entropy = shannon_entropy(chunk)
        
        # Base probability from entropy
        if entropy > 0.9:  # High information density
            base_prob = 0.99
        elif entropy > 0.75:
            base_prob = 0.95
        elif entropy > 0.6:
            base_prob = 0.90
        elif entropy > 0.3:
            base_prob = 0.80
        else:  # Low entropy (redundant data)
            base_prob = 0.70
        
        # Adjust for DHT replication (if available)
        if self.dht:
            chunk_hash = self.stc_wrapper.hash_data(chunk)
            replication = len(self.dht.providers.get(chunk_hash, set()))
            
            # More copies = lower delivery requirement
            if replication > 10:
                base_prob *= 0.85
            elif replication > 5:
                base_prob *= 0.90
            elif replication > 2:
                base_prob *= 0.95
            # else: no adjustment for low replication
        
        return min(max(base_prob, 0.0), 1.0)
    
    async def send_probabilistic(self, data: bytes) -> int:
        """
        Send data with entropy-aware retransmission.
        
        Args:
            data: Data to send
            
        Returns:
            Number of chunks successfully delivered
        """
        if not self.is_active:
            raise STTStreamError("Stream is closed")
        
        # Split into chunks
        chunks = self._chunk_data(data)
        self.total_chunks += len(chunks)
        
        delivered_count = 0
        
        for chunk_idx, chunk in enumerate(chunks):
            # Calculate delivery parameters
            entropy = shannon_entropy(chunk)
            delivery_prob = self.calculate_delivery_probability(chunk)
            
            # Get replication count
            chunk_hash = self.stc_wrapper.hash_data(chunk)
            replication = len(self.dht.providers.get(chunk_hash, set())) if self.dht else 0
            
            # Calculate max attempts based on probability
            # P(delivered after N attempts) = 1 - (1-p)^N
            # Solve for N to achieve target probability
            # Assume per-attempt success rate of 0.5 (50% packet loss scenario)
            max_attempts = int(math.ceil(
                math.log(1 - delivery_prob) / math.log(0.5)
            ))
            max_attempts = min(max(max_attempts, 1), 10)  # Clamp to [1, 10]
            
            # Initialize metadata
            metadata = ChunkMetadata(
                chunk_idx=chunk_idx,
                entropy=entropy,
                delivery_prob=delivery_prob,
                replication=replication,
                attempts=0,
                delivered=False
            )
            self.chunk_metadata[chunk_idx] = metadata
            
            # Attempt delivery with adaptive retry
            for attempt in range(max_attempts):
                metadata.attempts += 1
                
                success = await self._try_send_chunk(chunk, chunk_idx)
                
                if success:
                    self.delivered_chunks.add(chunk_idx)
                    metadata.delivered = True
                    delivered_count += 1
                    self.successful_deliveries += 1
                    break
                
                # Probabilistic early exit (acceptable loss)
                # Random decision: continue retrying or accept loss
                if random.random() > delivery_prob:
                    logger.debug(
                        f"Probabilistic exit: chunk {chunk_idx}, "
                        f"entropy={entropy:.3f}, prob={delivery_prob:.3f}, "
                        f"replication={replication}, attempts={attempt + 1}"
                    )
                    self.probabilistic_exits += 1
                    break
                
                # Exponential backoff (1ms, 2ms, 4ms, ...)
                await asyncio.sleep(0.001 * (2 ** attempt))
        
        # Update statistics
        self.bytes_sent += len(data)
        self.messages_sent += 1
        self.sequence += 1
        self.last_activity = time.time()
        
        logger.info(
            f"Probabilistic send complete: {delivered_count}/{len(chunks)} chunks, "
            f"{len(data)} bytes"
        )
        
        return delivered_count
    
    async def _try_send_chunk(self, chunk: bytes, chunk_idx: int) -> bool:
        """
        Attempt to send chunk (stub for integration).
        
        In real implementation, this would send through transport layer.
        
        Args:
            chunk: Chunk data
            chunk_idx: Chunk index
            
        Returns:
            True if send succeeded
        """
        # Stub: simulate random success/failure
        # Real implementation would use actual transport
        await asyncio.sleep(0.001)  # Simulate network delay
        
        # Simulate 50% packet loss for testing
        return random.random() > 0.5
    
    def _chunk_data(self, data: bytes) -> List[bytes]:
        """
        Split data into chunks.
        
        Args:
            data: Data to chunk
            
        Returns:
            List of chunks
        """
        chunks = []
        offset = 0
        
        while offset < len(data):
            chunk = data[offset:offset + self.chunk_size]
            chunks.append(chunk)
            offset += self.chunk_size
        
        return chunks
    
    def get_delivery_stats(self) -> dict:
        """
        Get delivery statistics.
        
        Returns:
            Statistics dictionary
        """
        total_attempts = sum(m.attempts for m in self.chunk_metadata.values())
        
        return {
            'total_chunks': self.total_chunks,
            'delivered_chunks': len(self.delivered_chunks),
            'successful_deliveries': self.successful_deliveries,
            'probabilistic_exits': self.probabilistic_exits,
            'delivery_rate': len(self.delivered_chunks) / max(self.total_chunks, 1),
            'total_attempts': total_attempts,
            'avg_attempts_per_chunk': total_attempts / max(self.total_chunks, 1),
        }
    
    def get_chunk_report(self) -> List[dict]:
        """
        Get per-chunk delivery report.
        
        Returns:
            List of chunk metadata dictionaries
        """
        return [
            {
                'chunk_idx': m.chunk_idx,
                'entropy': m.entropy,
                'delivery_prob': m.delivery_prob,
                'replication': m.replication,
                'attempts': m.attempts,
                'delivered': m.delivered,
            }
            for m in sorted(self.chunk_metadata.values(), key=lambda x: x.chunk_idx)
        ]


def shannon_entropy(data: bytes) -> float:
    """
    Calculate Shannon entropy H(X) = -Σ p(x) log₂ p(x)
    
    Measures information density:
    - 0.0 = no information (all same byte)
    - 1.0 = maximum entropy (uniform distribution)
    
    Args:
        data: Input bytes
        
    Returns:
        Normalized entropy (0.0-1.0)
    """
    if not data:
        return 0.0
    
    # Count byte frequencies
    freq: dict[int, int] = {}
    for byte in data:
        freq[byte] = freq.get(byte, 0) + 1
    
    # Calculate entropy
    length = len(data)
    entropy = 0.0
    
    for count in freq.values():
        if count > 0:
            p = count / length
            entropy -= p * math.log2(p)
    
    # Normalize to 0-1 range
    # Maximum entropy for 256 symbols = log₂(256) = 8 bits
    max_entropy = 8.0
    
    return min(entropy / max_entropy, 1.0)


def calculate_entropy_stats(data: bytes) -> dict:
    """
    Calculate detailed entropy statistics.
    
    Args:
        data: Input bytes
        
    Returns:
        Statistics dictionary
    """
    if not data:
        return {
            'entropy': 0.0,
            'unique_bytes': 0,
            'most_common_byte': None,
            'most_common_count': 0,
        }
    
    # Count frequencies
    freq: dict[int, int] = {}
    for byte in data:
        freq[byte] = freq.get(byte, 0) + 1
    
    # Find most common
    most_common_byte, most_common_count = max(freq.items(), key=lambda x: x[1])
    
    # Calculate entropy
    length = len(data)
    entropy = 0.0
    
    for count in freq.values():
        if count > 0:
            p = count / length
            entropy -= p * math.log2(p)
    
    return {
        'entropy': min(entropy / 8.0, 1.0),
        'entropy_bits': entropy,
        'unique_bytes': len(freq),
        'most_common_byte': most_common_byte,
        'most_common_count': most_common_count,
        'most_common_ratio': most_common_count / length,
    }
