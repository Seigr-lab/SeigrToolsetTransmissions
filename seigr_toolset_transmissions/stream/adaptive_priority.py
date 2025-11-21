"""
Adaptive Priority System - Content-Derived Stream Priority

Priority emerges from content properties (NOT manual QoS flags):
- Content uniqueness (STC.hash + DHT replication)
- Temporal urgency (access patterns)
- Network conditions (congestion awareness)
- Hash affinity (Kademlia neighborhood density)
"""

import math
import time
from typing import Optional, Dict, TYPE_CHECKING
from dataclasses import dataclass

from ..utils.logging import get_logger

if TYPE_CHECKING:
    from ..dht.kademlia import KademliaDHT
    from ..session.session import STTSession

logger = get_logger(__name__)


@dataclass
class PriorityScore:
    """Priority calculation breakdown."""
    total: int  # 0-1000
    uniqueness: float  # 0.0-1.0
    temporal: float  # 0.0-1.0
    network: float  # 0.0-1.0
    affinity: float  # 0.0-1.0


class ContentCache:
    """Simple content cache for access pattern tracking."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.access_counts: Dict[bytes, int] = {}
        self.access_times: Dict[bytes, float] = {}
    
    def record_access(self, content_hash: bytes):
        """Record content access."""
        self.access_counts[content_hash] = self.access_counts.get(content_hash, 0) + 1
        self.access_times[content_hash] = time.time()
        
        # Simple LRU eviction if too large
        if len(self.access_counts) > self.max_size:
            oldest = min(self.access_times.items(), key=lambda x: x[1])
            del self.access_counts[oldest[0]]
            del self.access_times[oldest[0]]
    
    def get_access_frequency(self, content_hash: bytes) -> float:
        """Get normalized access frequency (0.0-1.0)."""
        if content_hash not in self.access_counts:
            return 0.0
        
        # Calculate recency-weighted frequency
        count = self.access_counts[content_hash]
        last_access = self.access_times.get(content_hash, 0)
        age = time.time() - last_access
        
        # Decay factor: exponential decay with 5-minute half-life
        decay = math.exp(-age / 300)
        
        # Normalize to 0-1 range (assuming max ~100 accesses)
        frequency = min(count / 100.0, 1.0) * decay
        
        return frequency


class CongestionMonitor:
    """Monitor network congestion per session."""
    
    def __init__(self):
        self.session_metrics: Dict[bytes, Dict] = {}
    
    def update_metrics(self, session_id: bytes, rtt: float, loss_rate: float):
        """Update congestion metrics for session."""
        if session_id not in self.session_metrics:
            self.session_metrics[session_id] = {
                'rtt_samples': [],
                'loss_samples': [],
                'last_update': time.time()
            }
        
        metrics = self.session_metrics[session_id]
        metrics['rtt_samples'].append(rtt)
        metrics['loss_samples'].append(loss_rate)
        metrics['last_update'] = time.time()
        
        # Keep only recent samples (last 100)
        if len(metrics['rtt_samples']) > 100:
            metrics['rtt_samples'] = metrics['rtt_samples'][-100:]
        if len(metrics['loss_samples']) > 100:
            metrics['loss_samples'] = metrics['loss_samples'][-100:]
    
    def get_level(self, session: 'STTSession') -> float:
        """
        Get congestion level for session.
        
        Returns: 0.0 (no congestion) to 1.0 (severe congestion)
        """
        session_id = session.session_id
        
        if session_id not in self.session_metrics:
            return 0.0  # No data = assume no congestion
        
        metrics = self.session_metrics[session_id]
        
        # RTT-based congestion indicator
        rtt_samples = metrics['rtt_samples']
        if rtt_samples:
            avg_rtt = sum(rtt_samples) / len(rtt_samples)
            rtt_variance = sum((r - avg_rtt) ** 2 for r in rtt_samples) / len(rtt_samples)
            rtt_factor = min(avg_rtt / 100, 1.0)  # Normalize to 100ms baseline
            variance_factor = min(math.sqrt(rtt_variance) / 50, 1.0)
        else:
            rtt_factor = 0.0
            variance_factor = 0.0
        
        # Loss-based congestion indicator
        loss_samples = metrics['loss_samples']
        if loss_samples:
            avg_loss = sum(loss_samples) / len(loss_samples)
            loss_factor = min(avg_loss / 0.05, 1.0)  # 5% loss = high congestion
        else:
            loss_factor = 0.0
        
        # Combined congestion level (weighted average)
        congestion = (0.4 * rtt_factor + 0.3 * variance_factor + 0.3 * loss_factor)
        
        return min(max(congestion, 0.0), 1.0)


class AdaptivePriorityManager:
    """
    Adaptive priority calculation from content properties.
    
    BREAKS FROM TRADITION: No manual priority flags, no QoS enums.
    Priority emerges naturally from content characteristics.
    """
    
    def __init__(self, dht: Optional['KademliaDHT'] = None, cache: Optional[ContentCache] = None):
        """
        Initialize adaptive priority manager.
        
        Args:
            dht: Optional DHT for replication queries
            cache: Optional content cache for access patterns
        """
        self.dht = dht
        self.cache = cache if cache is not None else ContentCache()
        self.congestion_monitor = CongestionMonitor()
        
        # Configuration weights
        self.uniqueness_weight = 0.4
        self.temporal_weight = 0.3
        self.network_weight = 0.2
        self.affinity_weight = 0.1
        
        logger.info("AdaptivePriorityManager initialized")
    
    def calculate_priority(self, data: bytes, session: 'STTSession') -> int:
        """
        Calculate priority (0-1000) from content properties.
        
        Args:
            data: Content data
            session: STT session
            
        Returns:
            Priority score (0-1000), higher = more important
        """
        # Hash the content
        content_hash = session.stc_wrapper.hash_data(data)
        
        # Record access
        self.cache.record_access(content_hash)
        
        # Calculate 4 factors
        uniqueness = self._calc_uniqueness(content_hash)
        temporal = self._calc_temporal_urgency(content_hash)
        network = self._calc_network_factor(session)
        affinity = self._calc_hash_affinity(content_hash)
        
        # Weighted combination
        priority = int(
            self.uniqueness_weight * uniqueness +
            self.temporal_weight * temporal +
            self.network_weight * network +
            self.affinity_weight * affinity
        ) * 1000
        
        priority = min(max(priority, 0), 1000)
        
        logger.debug(
            f"Priority calculated: {priority} "
            f"(uniqueness={uniqueness:.2f}, temporal={temporal:.2f}, "
            f"network={network:.2f}, affinity={affinity:.2f})"
        )
        
        return priority
    
    def calculate_priority_detailed(self, data: bytes, session: 'STTSession') -> PriorityScore:
        """
        Calculate priority with detailed breakdown.
        
        Args:
            data: Content data
            session: STT session
            
        Returns:
            PriorityScore with breakdown
        """
        content_hash = session.stc_wrapper.hash_data(data)
        self.cache.record_access(content_hash)
        
        uniqueness = self._calc_uniqueness(content_hash)
        temporal = self._calc_temporal_urgency(content_hash)
        network = self._calc_network_factor(session)
        affinity = self._calc_hash_affinity(content_hash)
        
        total = int(
            self.uniqueness_weight * uniqueness +
            self.temporal_weight * temporal +
            self.network_weight * network +
            self.affinity_weight * affinity
        ) * 1000
        
        total = min(max(total, 0), 1000)
        
        return PriorityScore(
            total=total,
            uniqueness=uniqueness,
            temporal=temporal,
            network=network,
            affinity=affinity
        )
    
    def _calc_uniqueness(self, content_hash: bytes) -> float:
        """
        Calculate uniqueness score from DHT replication.
        
        Rare content = higher score (fewer replicas in DHT)
        
        Returns: 0.0-1.0
        """
        if not self.dht:
            return 0.5  # Default if no DHT
        
        try:
            # Query DHT for provider count
            replication = len(self.dht.providers.get(content_hash, set()))
            
            # Inverse relationship: fewer copies = higher score
            # Using logarithmic scale for smoother distribution
            if replication == 0:
                return 1.0  # Unique content
            elif replication == 1:
                return 0.9
            else:
                # Decay: log(1 + replication) / log(20)
                # At 20 replicas: ~0.33, at 100 replicas: ~0.17
                score = 1.0 - (math.log(1 + replication) / math.log(20))
                return max(score, 0.0)
        except Exception as e:
            logger.warning(f"Error calculating uniqueness: {e}")
            return 0.5
    
    def _calc_temporal_urgency(self, content_hash: bytes) -> float:
        """
        Calculate temporal urgency from access patterns.
        
        Hot content = higher score (frequent recent access)
        
        Returns: 0.0-1.0
        """
        frequency = self.cache.get_access_frequency(content_hash)
        
        # Apply sigmoid activation for smooth scaling
        return sigmoid(frequency * 10 - 5)  # Center around 0.5 frequency
    
    def _calc_network_factor(self, session: 'STTSession') -> float:
        """
        Calculate network factor from congestion.
        
        Back off when congested (lower priority under congestion)
        
        Returns: 0.0-1.0
        """
        congestion = self.congestion_monitor.get_level(session)
        
        # Inverse: high congestion = lower priority boost
        return 1.0 - congestion
    
    def _calc_hash_affinity(self, content_hash: bytes) -> float:
        """
        Calculate hash affinity (neighborhood density).
        
        Content in dense hash neighborhoods = higher score
        (Leverages Kademlia locality)
        
        Returns: 0.0-1.0
        """
        if not self.dht:
            return 0.5  # Default if no DHT
        
        try:
            # Count nearby content (within 4-bit prefix)
            hash_prefix = content_hash[:1]  # First byte
            
            nearby_count = sum(
                1 for stored_hash in self.dht.storage.keys()
                if stored_hash[:1] == hash_prefix
            )
            
            # Normalize to 0-1 (assume max ~50 items per prefix)
            affinity = min(nearby_count / 50.0, 1.0)
            
            return affinity
        except Exception as e:
            logger.warning(f"Error calculating affinity: {e}")
            return 0.5


def sigmoid(x: float) -> float:
    """
    Sigmoid activation function.
    
    Maps (-inf, +inf) to (0, 1) with smooth transition.
    
    Args:
        x: Input value
        
    Returns:
        Sigmoid output (0.0-1.0)
    """
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        # Handle extreme values
        return 0.0 if x < 0 else 1.0
