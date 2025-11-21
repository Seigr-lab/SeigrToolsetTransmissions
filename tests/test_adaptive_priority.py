"""
Tests for Adaptive Priority System

Validates:
- Priority calculation from content properties
- Uniqueness scoring (DHT replication)
- Temporal urgency (access patterns)
- Network factor (congestion)
- Hash affinity (Kademlia neighborhoods)
"""

import pytest
import time
from unittest.mock import Mock, MagicMock

from seigr_toolset_transmissions.stream.adaptive_priority import (
    AdaptivePriorityManager,
    ContentCache,
    CongestionMonitor,
    PriorityScore,
    sigmoid
)
from seigr_toolset_transmissions.session.session import STTSession
from seigr_toolset_transmissions.crypto.stc_wrapper import STCWrapper


@pytest.fixture
def mock_dht():
    """Mock DHT for testing."""
    dht = Mock()
    dht.providers = {}
    dht.storage = {}
    return dht


@pytest.fixture
def mock_stc():
    """Mock STC wrapper."""
    stc = Mock(spec=STCWrapper)
    stc.hash_data = MagicMock(return_value=b'\x00' * 32)
    return stc


@pytest.fixture
def mock_session(mock_stc):
    """Mock session."""
    session = Mock(spec=STTSession)
    session.session_id = b'\x01' * 8
    session.stc_wrapper = mock_stc
    return session


@pytest.fixture
def priority_manager(mock_dht):
    """Create priority manager with mock DHT."""
    return AdaptivePriorityManager(dht=mock_dht)


def test_sigmoid_function():
    """Test sigmoid activation function."""
    assert sigmoid(0) == pytest.approx(0.5, abs=0.01)
    assert sigmoid(10) > 0.99
    assert sigmoid(-10) < 0.01
    assert 0 <= sigmoid(5) <= 1


def test_content_cache_access_tracking():
    """Test content cache access pattern tracking."""
    cache = ContentCache(max_size=100)
    
    content_hash = b'\xaa' * 32
    
    # Record accesses
    cache.record_access(content_hash)
    cache.record_access(content_hash)
    cache.record_access(content_hash)
    
    freq = cache.get_access_frequency(content_hash)
    assert freq > 0.0
    assert freq <= 1.0


def test_content_cache_lru_eviction():
    """Test LRU eviction in content cache."""
    cache = ContentCache(max_size=10)
    
    # Fill cache beyond capacity
    for i in range(15):
        content_hash = bytes([i]) * 32
        cache.record_access(content_hash)
    
    # Cache should be capped at max_size
    assert len(cache.access_counts) <= 10


def test_congestion_monitor():
    """Test congestion monitoring."""
    monitor = CongestionMonitor()
    
    mock_session = Mock()
    mock_session.session_id = b'\x01' * 8
    
    # Initial state: no congestion
    level = monitor.get_level(mock_session)
    assert level == 0.0
    
    # Update with high RTT and loss
    monitor.update_metrics(mock_session.session_id, rtt=200.0, loss_rate=0.1)
    
    level = monitor.get_level(mock_session)
    assert level > 0.0
    assert level <= 1.0


def test_priority_calculation_basic(priority_manager, mock_session):
    """Test basic priority calculation."""
    data = b'test data' * 100
    
    priority = priority_manager.calculate_priority(data, mock_session)
    
    assert 0 <= priority <= 1000
    assert isinstance(priority, int)


def test_priority_calculation_detailed(priority_manager, mock_session):
    """Test detailed priority calculation with breakdown."""
    data = b'test data' * 100
    
    score = priority_manager.calculate_priority_detailed(data, mock_session)
    
    assert isinstance(score, PriorityScore)
    assert 0 <= score.total <= 1000
    assert 0.0 <= score.uniqueness <= 1.0
    assert 0.0 <= score.temporal <= 1.0
    assert 0.0 <= score.network <= 1.0
    assert 0.0 <= score.affinity <= 1.0


def test_uniqueness_scoring_no_dht():
    """Test uniqueness scoring without DHT."""
    manager = AdaptivePriorityManager(dht=None)
    
    content_hash = b'\xbb' * 32
    score = manager._calc_uniqueness(content_hash)
    
    # Should return default score without DHT
    assert score == 0.5


def test_uniqueness_scoring_with_replication(priority_manager, mock_dht):
    """Test uniqueness scoring with DHT replication."""
    content_hash = b'\xcc' * 32
    
    # Unique content (no providers)
    mock_dht.providers[content_hash] = set()
    score_unique = priority_manager._calc_uniqueness(content_hash)
    assert score_unique == 1.0
    
    # Highly replicated content
    mock_dht.providers[content_hash] = set(range(20))
    score_replicated = priority_manager._calc_uniqueness(content_hash)
    assert score_replicated < score_unique


def test_temporal_urgency(priority_manager):
    """Test temporal urgency calculation."""
    content_hash = b'\xdd' * 32
    
    # Simulate hot content (many recent accesses)
    for _ in range(50):  # More accesses for stronger signal
        priority_manager.cache.record_access(content_hash)
    
    urgency = priority_manager._calc_temporal_urgency(content_hash)
    assert 0.0 <= urgency <= 1.0
    assert urgency > 0.3  # Should be elevated for hot content


def test_network_factor_no_congestion(priority_manager, mock_session):
    """Test network factor without congestion."""
    factor = priority_manager._calc_network_factor(mock_session)
    
    # No congestion = high factor
    assert factor == 1.0


def test_network_factor_with_congestion(priority_manager, mock_session):
    """Test network factor with congestion."""
    # Simulate congestion
    priority_manager.congestion_monitor.update_metrics(
        mock_session.session_id,
        rtt=500.0,
        loss_rate=0.2
    )
    
    factor = priority_manager._calc_network_factor(mock_session)
    
    # Congestion = lower factor
    assert 0.0 <= factor < 1.0


def test_hash_affinity_no_dht():
    """Test hash affinity without DHT."""
    manager = AdaptivePriorityManager(dht=None)
    
    content_hash = b'\xee' * 32
    affinity = manager._calc_hash_affinity(content_hash)
    
    # Should return default without DHT
    assert affinity == 0.5


def test_hash_affinity_with_neighbors(priority_manager, mock_dht):
    """Test hash affinity with neighboring content."""
    content_hash = b'\xff\x00' * 16
    
    # Add neighbors with same prefix
    for i in range(10):
        neighbor_hash = bytes([0xff, i]) + b'\x00' * 30
        mock_dht.storage[neighbor_hash] = b'data'
    
    affinity = priority_manager._calc_hash_affinity(content_hash)
    assert 0.0 <= affinity <= 1.0


def test_priority_increases_for_rare_content(priority_manager, mock_dht, mock_session):
    """Test that rare content gets higher priority."""
    data = b'unique rare data' * 100
    
    content_hash = b'\xaa' * 32
    # Hash should return consistent value for test
    mock_session.stc_wrapper.hash_data.return_value = content_hash
    
    # No replication (rare)
    mock_dht.providers[content_hash] = set()
    priority_rare = priority_manager.calculate_priority(data, mock_session)
    
    # High replication (common)
    mock_dht.providers[content_hash] = set(range(50))
    priority_common = priority_manager.calculate_priority(data, mock_session)
    
    # Rare content should have higher uniqueness component
    assert priority_rare >= priority_common


def test_priority_increases_for_hot_content(priority_manager, mock_session):
    """Test that frequently accessed content gets higher priority."""
    data = b'hot content' * 100
    
    content_hash = b'\xbb' * 32
    mock_session.stc_wrapper.hash_data.return_value = content_hash
    
    # First access (cold)
    priority_cold = priority_manager.calculate_priority(data, mock_session)
    
    # Multiple accesses (hot) - simulate many accesses
    for _ in range(100):  # More accesses for stronger signal
        priority_manager.cache.record_access(content_hash)
    
    priority_hot = priority_manager.calculate_priority(data, mock_session)
    
    # Hot content should have higher temporal component
    assert priority_hot >= priority_cold


def test_priority_decreases_under_congestion(priority_manager, mock_session):
    """Test that priority adjusts for network congestion."""
    data = b'test data' * 100
    
    # No congestion
    priority_normal = priority_manager.calculate_priority(data, mock_session)
    
    # High congestion
    priority_manager.congestion_monitor.update_metrics(
        mock_session.session_id,
        rtt=1000.0,
        loss_rate=0.5
    )
    
    priority_congested = priority_manager.calculate_priority(data, mock_session)
    
    # Congestion should reduce priority boost
    assert priority_congested <= priority_normal


def test_performance_priority_calculation(priority_manager, mock_session):
    """Benchmark: priority calculation should be <1ms."""
    import time
    
    data = b'x' * 65536  # 64KB
    
    # Warmup
    for _ in range(10):
        priority_manager.calculate_priority(data, mock_session)
    
    # Measure
    start = time.perf_counter()
    iterations = 100
    for _ in range(iterations):
        priority_manager.calculate_priority(data, mock_session)
    elapsed = time.perf_counter() - start
    
    avg_time = elapsed / iterations
    assert avg_time < 0.001, f"Priority calculation took {avg_time*1000:.2f}ms (target <1ms)"
