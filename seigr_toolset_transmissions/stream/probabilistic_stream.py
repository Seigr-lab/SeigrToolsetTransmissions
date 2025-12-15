"""
Probabilistic Delivery Streams - Entropy-Aware Loss Tolerance

Delivery guarantee tied to content properties:
- Shannon entropy (information density)

NOT "unreliable" but "probabilistically reliable"
Based purely on local content analysis, no external dependencies.
"""

import asyncio
import math
import secrets  # Use secrets instead of random for better randomness
import time
from typing import List, TYPE_CHECKING
from dataclasses import dataclass

from .stream import STTStream
from ..utils.logging import get_logger
from ..utils.exceptions import STTStreamError

if TYPE_CHECKING:
    from ..crypto.stc_wrapper import STCWrapper

logger = get_logger(__name__)


@dataclass
class SegmentMetadata:
    """Metadata for probabilistic segment delivery (agnostic binary data)."""
    segment_idx: int
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
        segment_size: int = 16384
    ):
        """
        Initialize probabilistic stream.
        
        Args:
            session_id: Parent session ID
            stream_id: Stream ID
            stc_wrapper: STC wrapper for crypto
            segment_size: Segment size for entropy calculation (16KB default)
        """
        super().__init__(session_id, stream_id, stc_wrapper)
        
        self.segment_size = segment_size
        self.mode = 'probabilistic'
        
        # Delivery tracking
        self.delivered_segments: set = set()
        self.segment_metadata: dict[int, SegmentMetadata] = {}
        
        # Statistics
        self.total_segments = 0
        self.successful_deliveries = 0
        self.probabilistic_exits = 0
        
        logger.info(
            f"ProbabilisticStream created: session={session_id.hex()[:8]}, "
            f"stream={stream_id}, segment_size={segment_size}"
        )
    
    def calculate_delivery_probability(self, chunk: bytes) -> float:
        """
        Calculate required delivery probability (0.0-1.0).
        
        High entropy = must deliver (0.99+)
        Low entropy = can lose (0.70)
        
        Args:
            chunk: Data segment to analyze
            
        Returns:
            Target delivery probability
        """
        # Calculate Shannon entropy
        entropy = shannon_entropy(chunk)
        
        # Base probability from entropy ONLY (no external dependencies)
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
        
        # Split into segments
        segments = self._segment_data(data)
        self.total_segments += len(segments)
        
        delivered_count = 0
        
        for segment_idx, segment in enumerate(segments):
            # Calculate delivery parameters (entropy-based only)
            entropy = shannon_entropy(segment)
            delivery_prob = self.calculate_delivery_probability(segment)
            
            # Calculate max attempts based on probability
            # P(delivered after N attempts) = 1 - (1-p)^N
            # Solve for N to achieve target probability
            # Assume per-attempt success rate of 0.5 (50% packet loss scenario)
            max_attempts = int(math.ceil(
                math.log(1 - delivery_prob) / math.log(0.5)
            ))
            max_attempts = min(max(max_attempts, 1), 10)  # Clamp to [1, 10]
            
            # Initialize metadata
            metadata = SegmentMetadata(
                segment_idx=segment_idx,
                entropy=entropy,
                delivery_prob=delivery_prob,
                replication=0,  # Not tracked (no external dependencies)
                attempts=0,
                delivered=False
            )
            self.segment_metadata[segment_idx] = metadata
            
            # Attempt delivery with adaptive retry
            for attempt in range(max_attempts):
                metadata.attempts += 1
                
                success = await self._try_send_segment(segment, segment_idx)
                
                if success:
                    self.delivered_segments.add(segment_idx)
                    metadata.delivered = True
                    delivered_count += 1
                    self.successful_deliveries += 1
                    break
                
                # Probabilistic early exit (acceptable loss)
                # Random decision: continue retrying or accept loss
                if (secrets.randbelow(1000000) / 1000000.0) > delivery_prob:
                    logger.debug(
                        f"Probabilistic exit: segment {segment_idx}, "
                        f"entropy={entropy:.3f}, prob={delivery_prob:.3f}, "
                        f"attempts={attempt + 1}"
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
            f"Probabilistic send complete: {delivered_count}/{len(segments)} chunks, "
            f"{len(data)} bytes"
        )
        
        return delivered_count
    
    async def _try_send_segment(self, segment: bytes, segment_idx: int) -> bool:
        """
        Attempt to send segment (stub for integration).
        
        In real implementation, this would send through transport layer.
        
        Args:
            segment: Segment data
            segment_idx: Segment index
            
        Returns:
            True if send succeeded
        """
        # Stub: simulate random success/failure
        # Real implementation would use actual transport
        await asyncio.sleep(0.001)  # Simulate network delay
        
        # Simulate 50% packet loss for testing
        return (secrets.randbelow(1000000) / 1000000.0) > 0.5
    
    def _segment_data(self, data: bytes) -> List[bytes]:
        """
        Split data into segments.
        
        Args:
            data: Data to segment
            
        Returns:
            List of segments
        """
        segments = []
        offset = 0
        
        while offset < len(data):
            segment = data[offset:offset + self.segment_size]
            segments.append(segment)
            offset += self.segment_size
        
        return segments
    
    def get_delivery_stats(self) -> dict:
        """
        Get delivery statistics.
        
        Returns:
            Statistics dictionary
        """
        total_attempts = sum(m.attempts for m in self.segment_metadata.values())
        
        return {
            'total_segments': self.total_segments,
            'delivered_segments': len(self.delivered_segments),
            'successful_deliveries': self.successful_deliveries,
            'probabilistic_exits': self.probabilistic_exits,
            'delivery_rate': len(self.delivered_segments) / max(self.total_segments, 1),
            'total_attempts': total_attempts,
            'avg_attempts_per_segment': total_attempts / max(self.total_segments, 1),
        }
    
    def get_segment_report(self) -> List[dict]:
        """
        Get per-segment delivery report.
        
        Returns:
            List of segment metadata dictionaries
        """
        return [
            {
                'segment_idx': m.segment_idx,
                'entropy': m.entropy,
                'delivery_prob': m.delivery_prob,
                'replication': m.replication,
                'attempts': m.attempts,
                'delivered': m.delivered,
            }
            for m in sorted(self.segment_metadata.values(), key=lambda x: x.segment_idx)
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
