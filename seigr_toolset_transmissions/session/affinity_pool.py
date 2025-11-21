"""
Content-Affinity Session Pooling - Hash-Neighborhood Clustering

Pool sessions by CONTENT SIMILARITY, not (host, port):
- Use STC.hash proximity (Kademlia XOR distance)
- Sessions serving similar content cluster together
- Cache-aware routing
- Self-organizing based on traffic patterns

BREAKS FROM TRADITION: NOT HTTP/2 connection pooling (transport reuse)
BUT content-aware clustering (hash affinity)
"""

import time
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from dataclasses import dataclass

from .session import STTSession
from ..utils.logging import get_logger
from ..utils.exceptions import STTSessionError

if TYPE_CHECKING:
    from ..dht.kademlia import KademliaDHT

logger = get_logger(__name__)


class PoolMissError(STTSessionError):
    """No suitable session found in pool."""
    pass


@dataclass
class AffinityScore:
    """Affinity calculation breakdown."""
    total: float
    xor_distance: int
    min_distance: int
    cache_hit: bool
    recency_bonus: float


class ContentAffinityPool:
    """
    Session pooling based on content hash neighborhoods.
    
    Sessions cluster by STC.hash proximity using Kademlia XOR metric.
    Related content requests hit same session (cache locality).
    """
    
    def __init__(
        self,
        dht: Optional['KademliaDHT'] = None,
        max_pool_size: int = 100,
        max_hashes_per_session: int = 100
    ):
        """
        Initialize content-affinity pool.
        
        Args:
            dht: Optional DHT for replication queries
            max_pool_size: Maximum sessions per hash prefix
            max_hashes_per_session: Maximum content hashes tracked per session
        """
        self.dht = dht
        self.max_pool_size = max_pool_size
        self.max_hashes_per_session = max_hashes_per_session
        
        # Pools indexed by hash prefix (first 4 bytes)
        self.session_pools: Dict[bytes, List[STTSession]] = {}
        
        # Content cache for hit tracking
        self.content_cache: Dict[bytes, bytes] = {}
        self.access_times: Dict[bytes, float] = {}
        
        # Statistics
        self.pool_hits = 0
        self.pool_misses = 0
        self.rebalance_count = 0
        
        logger.info(
            f"ContentAffinityPool initialized "
            f"(max_pool_size={max_pool_size}, max_hashes={max_hashes_per_session})"
        )
    
    def get_session_for_content(self, content_hash: bytes) -> STTSession:
        """
        Get session from pool based on content hash proximity.
        
        Returns session likely to have related content cached.
        
        Args:
            content_hash: Content hash (STC.hash)
            
        Returns:
            Best matching session
            
        Raises:
            PoolMissError: If no suitable session available
        """
        # Extract hash prefix for clustering (first 4 bytes)
        hash_prefix = content_hash[:4]
        
        # Check if pool exists for this hash neighborhood
        if hash_prefix in self.session_pools:
            pool = self.session_pools[hash_prefix]
            
            if pool:
                # Find session with highest content affinity
                best_session = max(
                    pool,
                    key=lambda s: self.calculate_affinity(s, content_hash).total
                )
                
                # Update session's content tracking
                self.update_session_affinity(best_session, content_hash)
                
                self.pool_hits += 1
                
                logger.debug(
                    f"Pool hit: prefix={hash_prefix.hex()}, "
                    f"session={best_session.session_id.hex()[:8]}"
                )
                
                return best_session
        
        # No suitable session
        self.pool_misses += 1
        raise PoolMissError(
            f"No session available for hash prefix {hash_prefix.hex()}"
        )
    
    def add_session(self, session: STTSession, initial_content_hash: bytes):
        """
        Add session to pool, clustered by content hash.
        
        Args:
            session: Session to add
            initial_content_hash: Initial content hash for clustering
        """
        hash_prefix = initial_content_hash[:4]
        
        if hash_prefix not in self.session_pools:
            self.session_pools[hash_prefix] = []
        
        pool = self.session_pools[hash_prefix]
        
        # Check pool size limit
        if len(pool) >= self.max_pool_size:
            # Evict least-recently-used session
            lru_session = min(
                pool,
                key=lambda s: s.metadata.get('last_access', 0)
            )
            pool.remove(lru_session)
            
            logger.debug(
                f"Evicted LRU session {lru_session.session_id.hex()[:8]} "
                f"from prefix {hash_prefix.hex()}"
            )
        
        pool.append(session)
        
        # Initialize session content tracking
        session.metadata['content_hashes'] = {initial_content_hash}
        session.metadata['hash_prefix'] = hash_prefix
        session.metadata['last_access'] = time.time()
        
        logger.info(
            f"Added session {session.session_id.hex()[:8]} to pool "
            f"prefix={hash_prefix.hex()}, pool_size={len(pool)}"
        )
    
    def calculate_affinity(
        self,
        session: STTSession,
        content_hash: bytes
    ) -> AffinityScore:
        """
        Calculate content affinity score for session.
        
        Higher score = session is more likely to have related content.
        Uses Kademlia XOR distance for similarity.
        
        Args:
            session: Session to score
            content_hash: Target content hash
            
        Returns:
            AffinityScore with breakdown
        """
        session_hashes = session.metadata.get('content_hashes', set())
        
        if not session_hashes:
            return AffinityScore(
                total=0.0,
                xor_distance=0,
                min_distance=0,
                cache_hit=False,
                recency_bonus=0.0
            )
        
        # Calculate minimum XOR distance to any content in session history
        min_distance = min(
            xor_distance(content_hash, h) for h in session_hashes
        )
        
        # Affinity inversely proportional to distance
        # XOR distance 0 = perfect match, large distance = unrelated
        # Use logarithmic scale for better distribution
        if min_distance == 0:
            distance_score = 1.0
        else:
            # Normalize using log scale (max distance ~2^256)
            distance_score = 1.0 / (1 + (min_distance.bit_length() / 256.0))
        
        affinity = distance_score
        
        # Bonus for direct cache hit
        cache_hit = content_hash in self.content_cache
        if cache_hit:
            affinity *= 1.5
        
        # Bonus for recent access (temporal locality)
        last_access = session.metadata.get('last_access', 0)
        age = time.time() - last_access
        
        recency_bonus = 0.0
        if age < 60:  # Accessed in last minute
            recency_bonus = 0.2 * (1.0 - age / 60.0)
            affinity += recency_bonus
        
        return AffinityScore(
            total=affinity,
            xor_distance=min_distance,
            min_distance=min_distance,
            cache_hit=cache_hit,
            recency_bonus=recency_bonus
        )
    
    def update_session_affinity(self, session: STTSession, content_hash: bytes):
        """
        Update session's content affinity based on observed traffic.
        
        Args:
            session: Session to update
            content_hash: New content hash
        """
        if 'content_hashes' not in session.metadata:
            session.metadata['content_hashes'] = set()
        
        session.metadata['content_hashes'].add(content_hash)
        session.metadata['last_access'] = time.time()
        
        # Limit hash set size (keep most recent N)
        if len(session.metadata['content_hashes']) > self.max_hashes_per_session:
            # Convert to list, keep last N, convert back to set
            hashes_list = list(session.metadata['content_hashes'])
            session.metadata['content_hashes'] = set(hashes_list[-self.max_hashes_per_session:])
        
        # Check if session should move to different pool
        current_prefix = session.metadata.get('hash_prefix')
        new_prefix = content_hash[:4]
        
        if current_prefix != new_prefix:
            # Traffic pattern changed, rebalance
            self.rebalance_session(session, new_prefix)
    
    def rebalance_session(self, session: STTSession, new_prefix: bytes):
        """
        Move session to different pool if traffic pattern changed.
        
        Args:
            session: Session to rebalance
            new_prefix: New hash prefix
        """
        old_prefix = session.metadata.get('hash_prefix')
        
        # Remove from old pool
        if old_prefix and old_prefix in self.session_pools:
            try:
                self.session_pools[old_prefix].remove(session)
            except ValueError:
                pass  # Session not in pool
        
        # Add to new pool
        if new_prefix not in self.session_pools:
            self.session_pools[new_prefix] = []
        
        pool = self.session_pools[new_prefix]
        
        # Check size limit
        if len(pool) >= self.max_pool_size:
            lru_session = min(
                pool,
                key=lambda s: s.metadata.get('last_access', 0)
            )
            pool.remove(lru_session)
        
        pool.append(session)
        session.metadata['hash_prefix'] = new_prefix
        
        self.rebalance_count += 1
        
        logger.info(
            f"Rebalanced session {session.session_id.hex()[:8]} "
            f"from {old_prefix.hex() if old_prefix else 'none'} "
            f"to {new_prefix.hex()}"
        )
    
    def remove_session(self, session: STTSession):
        """
        Remove session from pool.
        
        Args:
            session: Session to remove
        """
        prefix = session.metadata.get('hash_prefix')
        
        if prefix and prefix in self.session_pools:
            try:
                self.session_pools[prefix].remove(session)
                logger.debug(f"Removed session {session.session_id.hex()[:8]} from pool")
            except ValueError:
                pass  # Session not in pool
    
    def get_pool_stats(self) -> Dict:
        """
        Get statistics about pool usage.
        
        Returns:
            Statistics dictionary
        """
        total_sessions = sum(len(p) for p in self.session_pools.values())
        avg_pool_size = total_sessions / max(len(self.session_pools), 1)
        
        hit_rate = (
            self.pool_hits / max(self.pool_hits + self.pool_misses, 1)
            if (self.pool_hits + self.pool_misses) > 0 else 0.0
        )
        
        return {
            'total_pools': len(self.session_pools),
            'total_sessions': total_sessions,
            'avg_pool_size': avg_pool_size,
            'max_pool_size': self.max_pool_size,
            'cache_size': len(self.content_cache),
            'pool_hits': self.pool_hits,
            'pool_misses': self.pool_misses,
            'hit_rate': hit_rate,
            'rebalance_count': self.rebalance_count,
            'pool_prefixes': [p.hex() for p in sorted(self.session_pools.keys())],
        }
    
    def get_pool_distribution(self) -> Dict[str, int]:
        """
        Get distribution of sessions across pools.
        
        Returns:
            Dict mapping prefix (hex) to session count
        """
        return {
            prefix.hex(): len(sessions)
            for prefix, sessions in self.session_pools.items()
        }
    
    def cleanup_inactive_sessions(self, max_idle: float = 600) -> int:
        """
        Remove inactive sessions from pools.
        
        Args:
            max_idle: Maximum idle time in seconds
            
        Returns:
            Number of sessions removed
        """
        current_time = time.time()
        removed_count = 0
        
        for prefix, pool in list(self.session_pools.items()):
            to_remove = []
            
            for session in pool:
                last_access = session.metadata.get('last_access', 0)
                idle_time = current_time - last_access
                
                if idle_time > max_idle or not session.is_active:
                    to_remove.append(session)
            
            for session in to_remove:
                pool.remove(session)
                removed_count += 1
            
            # Remove empty pools
            if not pool:
                del self.session_pools[prefix]
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} inactive sessions from pools")
        
        return removed_count


def xor_distance(hash1: bytes, hash2: bytes) -> int:
    """
    Calculate XOR distance (Kademlia metric).
    
    XOR distance measures "closeness" in hash space:
    - 0 = identical hashes
    - Small value = similar/nearby hashes
    - Large value = distant/unrelated hashes
    
    Args:
        hash1: First hash
        hash2: Second hash
        
    Returns:
        XOR distance as integer
        
    Raises:
        ValueError: If hashes are different lengths
    """
    if len(hash1) != len(hash2):
        raise ValueError(
            f"Hashes must be same length: {len(hash1)} != {len(hash2)}"
        )
    
    distance = 0
    for b1, b2 in zip(hash1, hash2):
        distance = (distance << 8) | (b1 ^ b2)
    
    return distance


def hamming_distance(hash1: bytes, hash2: bytes) -> int:
    """
    Calculate Hamming distance (number of differing bits).
    
    Args:
        hash1: First hash
        hash2: Second hash
        
    Returns:
        Hamming distance (bit count)
    """
    if len(hash1) != len(hash2):
        raise ValueError(
            f"Hashes must be same length: {len(hash1)} != {len(hash2)}"
        )
    
    distance = 0
    for b1, b2 in zip(hash1, hash2):
        xor = b1 ^ b2
        # Count set bits
        distance += bin(xor).count('1')
    
    return distance
