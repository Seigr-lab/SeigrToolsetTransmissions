"""
Tests for Content-Affinity Session Pooling

Validates:
- Session pooling by hash prefix
- XOR distance calculations
- Affinity scoring
- Cache-aware routing
- Pool rebalancing
- LRU eviction
"""

import pytest
import time
from unittest.mock import Mock

from seigr_toolset_transmissions.session.affinity_pool import (
    ContentAffinityPool,
    PoolMissError,
    AffinityScore,
    xor_distance,
    hamming_distance
)
from seigr_toolset_transmissions.session.session import STTSession
from seigr_toolset_transmissions.crypto.stc_wrapper import STCWrapper


@pytest.fixture
def mock_stc():
    """Mock STC wrapper."""
    return Mock(spec=STCWrapper)


@pytest.fixture
def mock_dht():
    """Mock DHT."""
    dht = Mock()
    dht.providers = {}
    return dht


@pytest.fixture
def affinity_pool(mock_dht):
    """Create affinity pool."""
    return ContentAffinityPool(dht=mock_dht, max_pool_size=10)


@pytest.fixture
def mock_session(mock_stc):
    """Create mock session."""
    session = STTSession(
        session_id=b'\x01' * 8,
        peer_node_id=b'\x02' * 32,
        stc_wrapper=mock_stc
    )
    return session


def test_xor_distance_identical():
    """Test XOR distance of identical hashes is 0."""
    hash1 = b'\xaa' * 32
    hash2 = b'\xaa' * 32
    
    distance = xor_distance(hash1, hash2)
    assert distance == 0


def test_xor_distance_different():
    """Test XOR distance of different hashes."""
    hash1 = b'\x00' * 32
    hash2 = b'\xff' * 32
    
    distance = xor_distance(hash1, hash2)
    assert distance > 0


def test_xor_distance_symmetric():
    """Test XOR distance is symmetric."""
    hash1 = b'\xaa\xbb' * 16
    hash2 = b'\xcc\xdd' * 16
    
    dist1 = xor_distance(hash1, hash2)
    dist2 = xor_distance(hash2, hash1)
    
    assert dist1 == dist2


def test_xor_distance_different_lengths_error():
    """Test XOR distance fails on different length hashes."""
    hash1 = b'\xaa' * 32
    hash2 = b'\xbb' * 16
    
    with pytest.raises(ValueError, match="same length"):
        xor_distance(hash1, hash2)


def test_hamming_distance():
    """Test Hamming distance calculation."""
    hash1 = b'\x00' * 32  # All zeros
    hash2 = b'\xff' * 32  # All ones
    
    distance = hamming_distance(hash1, hash2)
    assert distance == 256  # 32 bytes * 8 bits = 256 bits


def test_add_session_to_pool(affinity_pool, mock_session):
    """Test adding session to pool."""
    content_hash = b'\xaa\xbb' * 16
    
    affinity_pool.add_session(mock_session, content_hash)
    
    # Session should be in pool
    hash_prefix = content_hash[:4]
    assert hash_prefix in affinity_pool.session_pools
    assert mock_session in affinity_pool.session_pools[hash_prefix]
    
    # Session metadata should be set
    assert 'content_hashes' in mock_session.metadata
    assert content_hash in mock_session.metadata['content_hashes']
    assert mock_session.metadata['hash_prefix'] == hash_prefix


def test_get_session_for_content_hit(affinity_pool, mock_session):
    """Test getting session from pool (cache hit)."""
    content_hash = b'\xaa\xbb' * 16
    
    # Add session to pool
    affinity_pool.add_session(mock_session, content_hash)
    
    # Get session for same hash prefix
    retrieved = affinity_pool.get_session_for_content(content_hash)
    
    assert retrieved == mock_session
    assert affinity_pool.pool_hits == 1


def test_get_session_for_content_miss(affinity_pool):
    """Test getting session from pool (cache miss)."""
    content_hash = b'\xff\xff' * 16
    
    with pytest.raises(PoolMissError):
        affinity_pool.get_session_for_content(content_hash)
    
    assert affinity_pool.pool_misses == 1


def test_calculate_affinity_perfect_match(affinity_pool, mock_session):
    """Test affinity calculation for perfect match."""
    content_hash = b'\xaa\xbb' * 16
    
    # Add content to session history
    mock_session.metadata['content_hashes'] = {content_hash}
    mock_session.metadata['last_access'] = time.time()
    
    score = affinity_pool.calculate_affinity(mock_session, content_hash)
    
    assert isinstance(score, AffinityScore)
    assert score.xor_distance == 0  # Perfect match
    assert score.total > 0.9  # High affinity


def test_calculate_affinity_no_history(affinity_pool, mock_session):
    """Test affinity calculation for session with no history."""
    content_hash = b'\xaa\xbb' * 16
    
    mock_session.metadata['content_hashes'] = set()
    
    score = affinity_pool.calculate_affinity(mock_session, content_hash)
    
    assert score.total == 0.0


def test_calculate_affinity_nearby_content(affinity_pool, mock_session):
    """Test affinity for nearby content (similar hash)."""
    content_hash1 = b'\xaa\xbb\x00\x00' + b'\x00' * 28
    content_hash2 = b'\xaa\xbb\x00\x01' + b'\x00' * 28  # Very similar
    
    mock_session.metadata['content_hashes'] = {content_hash1}
    mock_session.metadata['last_access'] = time.time()
    
    score = affinity_pool.calculate_affinity(mock_session, content_hash2)
    
    # Should have high affinity (similar hashes)
    assert score.total > 0.5


def test_calculate_affinity_recency_bonus(affinity_pool, mock_session):
    """Test recency bonus for recently accessed sessions."""
    content_hash = b'\xaa\xbb' * 16
    
    # Recent access
    mock_session.metadata['content_hashes'] = {content_hash}
    mock_session.metadata['last_access'] = time.time()
    
    score_recent = affinity_pool.calculate_affinity(mock_session, content_hash)
    
    # Old access
    mock_session.metadata['last_access'] = time.time() - 3600
    score_old = affinity_pool.calculate_affinity(mock_session, content_hash)
    
    # Recent should have bonus
    assert score_recent.recency_bonus > score_old.recency_bonus


def test_update_session_affinity(affinity_pool, mock_session):
    """Test updating session affinity."""
    content_hash1 = b'\xaa\xbb' * 16
    content_hash2 = b'\xcc\xdd' * 16
    
    mock_session.metadata['content_hashes'] = {content_hash1}
    mock_session.metadata['hash_prefix'] = content_hash1[:4]
    
    affinity_pool.update_session_affinity(mock_session, content_hash2)
    
    # Should add new hash
    assert content_hash2 in mock_session.metadata['content_hashes']
    assert 'last_access' in mock_session.metadata


def test_update_session_affinity_size_limit(affinity_pool, mock_session):
    """Test hash set size limit enforcement."""
    pool = ContentAffinityPool(max_hashes_per_session=10)
    
    mock_session.metadata['content_hashes'] = set()
    mock_session.metadata['hash_prefix'] = b'\xaa\xbb\xcc\xdd'
    
    # Add 20 hashes (exceeds limit of 10)
    for i in range(20):
        content_hash = bytes([i]) * 32
        pool.update_session_affinity(mock_session, content_hash)
    
    # Should be capped at max
    assert len(mock_session.metadata['content_hashes']) == 10


def test_rebalance_session(affinity_pool, mock_session):
    """Test session rebalancing when traffic pattern changes."""
    old_hash = b'\xaa\xbb' * 16
    new_hash = b'\xff\xee' * 16
    
    # Add to pool with old prefix
    affinity_pool.add_session(mock_session, old_hash)
    old_prefix = old_hash[:4]
    
    # Trigger rebalance with new prefix
    new_prefix = new_hash[:4]
    affinity_pool.rebalance_session(mock_session, new_prefix)
    
    # Should be in new pool
    assert new_prefix in affinity_pool.session_pools
    assert mock_session in affinity_pool.session_pools[new_prefix]
    
    # Should be removed from old pool (if different)
    if old_prefix != new_prefix:
        assert mock_session not in affinity_pool.session_pools.get(old_prefix, [])
    
    assert affinity_pool.rebalance_count == 1


def test_pool_size_limit_eviction(affinity_pool, mock_stc):
    """Test LRU eviction when pool reaches size limit."""
    pool = ContentAffinityPool(max_pool_size=3)
    content_hash = b'\xaa\xbb' * 16
    
    # Add 4 sessions to same pool (exceeds limit of 3)
    sessions = []
    for i in range(4):
        session = STTSession(
            session_id=bytes([i]) * 8,
            peer_node_id=b'\x02' * 32,
            stc_wrapper=mock_stc
        )
        session.metadata['last_access'] = time.time() + i  # Newer sessions have higher timestamp
        pool.add_session(session, content_hash)
        sessions.append(session)
        time.sleep(0.01)
    
    # Pool should be capped at 3
    hash_prefix = content_hash[:4]
    assert len(pool.session_pools[hash_prefix]) == 3
    
    # Oldest session (sessions[0]) should be evicted
    assert sessions[0] not in pool.session_pools[hash_prefix]


def test_remove_session(affinity_pool, mock_session):
    """Test removing session from pool."""
    content_hash = b'\xaa\xbb' * 16
    
    affinity_pool.add_session(mock_session, content_hash)
    affinity_pool.remove_session(mock_session)
    
    # Session should be removed
    hash_prefix = content_hash[:4]
    assert mock_session not in affinity_pool.session_pools.get(hash_prefix, [])


def test_get_pool_stats(affinity_pool, mock_stc):
    """Test getting pool statistics."""
    # Add some sessions
    for i in range(5):
        session = STTSession(
            session_id=bytes([i]) * 8,
            peer_node_id=b'\x02' * 32,
            stc_wrapper=mock_stc
        )
        content_hash = bytes([i, i]) * 16
        affinity_pool.add_session(session, content_hash)
    
    stats = affinity_pool.get_pool_stats()
    
    assert 'total_pools' in stats
    assert 'total_sessions' in stats
    assert 'avg_pool_size' in stats
    assert 'pool_hits' in stats
    assert 'pool_misses' in stats
    assert 'hit_rate' in stats
    assert 'rebalance_count' in stats
    
    assert stats['total_sessions'] == 5


def test_get_pool_distribution(affinity_pool, mock_stc):
    """Test getting pool distribution."""
    # Add sessions to different prefixes
    for i in range(3):
        session = STTSession(
            session_id=bytes([i]) * 8,
            peer_node_id=b'\x02' * 32,
            stc_wrapper=mock_stc
        )
        content_hash = bytes([i, i, i, i]) * 8
        affinity_pool.add_session(session, content_hash)
    
    dist = affinity_pool.get_pool_distribution()
    
    # Should have 3 different prefixes
    assert len(dist) == 3
    
    # Each prefix should have 1 session
    for count in dist.values():
        assert count == 1


def test_cleanup_inactive_sessions(affinity_pool, mock_stc):
    """Test cleanup of inactive sessions."""
    content_hash = b'\xaa\xbb' * 16
    
    # Add sessions with varying last_access times
    old_session = STTSession(
        session_id=b'\x01' * 8,
        peer_node_id=b'\x02' * 32,
        stc_wrapper=mock_stc
    )
    
    new_session = STTSession(
        session_id=b'\x02' * 8,
        peer_node_id=b'\x02' * 32,
        stc_wrapper=mock_stc
    )
    
    # Add to pool (this sets last_access)
    affinity_pool.add_session(old_session, content_hash)
    affinity_pool.add_session(new_session, content_hash)
    
    # Now manually override old session's access time
    old_session.metadata['last_access'] = time.time() - 1000  # Old
    
    # Cleanup with max_idle=500
    removed = affinity_pool.cleanup_inactive_sessions(max_idle=500)
    
    assert removed == 1  # Old session removed
    
    hash_prefix = content_hash[:4]
    assert old_session not in affinity_pool.session_pools[hash_prefix]
    assert new_session in affinity_pool.session_pools[hash_prefix]


def test_hit_rate_tracking(affinity_pool, mock_session):
    """Test pool hit rate tracking."""
    content_hash1 = b'\xaa\xbb' * 16
    content_hash2 = b'\xff\xee' * 16
    
    # Add session for first hash
    affinity_pool.add_session(mock_session, content_hash1)
    
    # Hit: Get session for same hash
    affinity_pool.get_session_for_content(content_hash1)
    
    # Miss: Get session for different hash
    try:
        affinity_pool.get_session_for_content(content_hash2)
    except PoolMissError:
        pass
    
    stats = affinity_pool.get_pool_stats()
    
    assert stats['pool_hits'] == 1
    assert stats['pool_misses'] == 1
    assert stats['hit_rate'] == 0.5


def test_content_clustering_benefit(affinity_pool, mock_stc):
    """Test that related content hits same session pool."""
    # Create sessions for similar content
    base_hash = b'\xaa\xbb\xcc\xdd' + b'\x00' * 28
    
    session = STTSession(
        session_id=b'\x01' * 8,
        peer_node_id=b'\x02' * 32,
        stc_wrapper=mock_stc
    )
    
    affinity_pool.add_session(session, base_hash)
    
    # Request similar content (same prefix)
    similar_hash = b'\xaa\xbb\xcc\xdd' + b'\x11' * 28
    
    retrieved = affinity_pool.get_session_for_content(similar_hash)
    
    # Should get same session (hash prefix match)
    assert retrieved == session
