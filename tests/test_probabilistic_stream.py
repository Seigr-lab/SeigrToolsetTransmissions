"""
Tests for Probabilistic Delivery Streams

Validates:
- Shannon entropy calculation
- Delivery probability based on entropy
- DHT replication awareness
- Adaptive retransmission
- Probabilistic early exit
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from seigr_toolset_transmissions.stream.probabilistic_stream import (
    ProbabilisticStream,
    shannon_entropy,
    calculate_entropy_stats,
    ChunkMetadata
)
from seigr_toolset_transmissions.crypto.stc_wrapper import STCWrapper


@pytest.fixture
def mock_stc():
    """Mock STC wrapper."""
    stc = Mock(spec=STCWrapper)
    stc.hash_data = Mock(return_value=b'\x00' * 32)
    return stc


@pytest.fixture
def mock_dht():
    """Mock DHT."""
    dht = Mock()
    dht.providers = {}
    return dht


@pytest.fixture
def prob_stream(mock_stc, mock_dht):
    """Create probabilistic stream."""
    return ProbabilisticStream(
        session_id=b'\x01' * 8,
        stream_id=1,
        stc_wrapper=mock_stc,
        dht=mock_dht,
        chunk_size=1024
    )


def test_shannon_entropy_zero():
    """Test entropy of uniform data (zero entropy)."""
    data = b'\x00' * 1000
    entropy = shannon_entropy(data)
    assert entropy == 0.0


def test_shannon_entropy_maximum():
    """Test entropy of random data (maximum entropy)."""
    # Uniform distribution across all 256 bytes
    data = bytes(range(256)) * 4  # 1024 bytes
    entropy = shannon_entropy(data)
    assert entropy > 0.95  # Should be close to 1.0


def test_shannon_entropy_moderate():
    """Test entropy of semi-redundant data."""
    # Mix of repeated and varied bytes
    data = b'hello world ' * 100
    entropy = shannon_entropy(data)
    assert 0.3 < entropy < 0.7


def test_shannon_entropy_empty():
    """Test entropy of empty data."""
    entropy = shannon_entropy(b'')
    assert entropy == 0.0


def test_calculate_entropy_stats():
    """Test detailed entropy statistics."""
    data = b'test data with some repetition' * 10
    stats = calculate_entropy_stats(data)
    
    assert 'entropy' in stats
    assert 'entropy_bits' in stats
    assert 'unique_bytes' in stats
    assert 'most_common_byte' in stats
    assert 'most_common_count' in stats
    assert 'most_common_ratio' in stats
    
    assert 0.0 <= stats['entropy'] <= 1.0
    assert stats['unique_bytes'] > 0
    assert stats['most_common_count'] > 0


def test_delivery_probability_high_entropy(prob_stream):
    """Test high entropy data requires high delivery probability."""
    # Random data = high entropy
    high_entropy_chunk = bytes(range(256)) * 4
    
    prob = prob_stream.calculate_delivery_probability(high_entropy_chunk)
    
    assert prob >= 0.95  # High entropy = must deliver


def test_delivery_probability_low_entropy(prob_stream):
    """Test low entropy data allows lower delivery probability."""
    # Uniform data = low entropy
    low_entropy_chunk = b'\x00' * 1000
    
    prob = prob_stream.calculate_delivery_probability(low_entropy_chunk)
    
    assert prob <= 0.80  # Low entropy = can lose


def test_delivery_probability_with_replication(prob_stream, mock_dht):
    """Test delivery probability adjusts for DHT replication."""
    chunk = b'test' * 256
    chunk_hash = b'\xaa' * 32
    
    prob_stream.stc_wrapper.hash_data.return_value = chunk_hash
    
    # No replication
    mock_dht.providers[chunk_hash] = set()
    prob_no_repl = prob_stream.calculate_delivery_probability(chunk)
    
    # High replication (content available elsewhere)
    mock_dht.providers[chunk_hash] = set(range(20))
    prob_high_repl = prob_stream.calculate_delivery_probability(chunk)
    
    # More replication = can tolerate more loss
    assert prob_high_repl <= prob_no_repl


@pytest.mark.asyncio
async def test_send_probabilistic_basic(prob_stream):
    """Test basic probabilistic send."""
    data = b'test data' * 100
    
    # Mock send attempts
    prob_stream._try_send_chunk = AsyncMock(return_value=True)
    
    delivered = await prob_stream.send_probabilistic(data)
    
    assert delivered > 0
    assert prob_stream.total_chunks > 0
    assert prob_stream.bytes_sent == len(data)


@pytest.mark.asyncio
async def test_send_probabilistic_chunks_data(prob_stream):
    """Test data is properly chunked."""
    data = b'x' * 10000  # 10KB
    chunk_size = 1024
    
    chunks = prob_stream._chunk_data(data)
    
    assert len(chunks) == 10  # 10KB / 1KB = 10 chunks
    assert all(len(c) == chunk_size for c in chunks[:-1])


@pytest.mark.asyncio
async def test_send_probabilistic_retry_logic(prob_stream):
    """Test adaptive retry with backoff."""
    data = b'test' * 256
    
    # Track attempts per chunk
    chunk_attempts = {}
    
    async def mock_try_send(chunk, idx):
        if idx not in chunk_attempts:
            chunk_attempts[idx] = 0
        chunk_attempts[idx] += 1
        # Succeed on 3rd attempt for each chunk
        return chunk_attempts[idx] >= 3
    
    prob_stream._try_send_chunk = mock_try_send
    
    # Patch random to prevent early exit (always retry)
    with patch('seigr_toolset_transmissions.stream.probabilistic_stream.random.random', return_value=0.0):
        delivered = await prob_stream.send_probabilistic(data)
    
    # At least one chunk should have made multiple attempts (2 or more)
    assert max(chunk_attempts.values()) >= 2, f"Max attempts: {max(chunk_attempts.values())}"


@pytest.mark.asyncio
async def test_send_probabilistic_early_exit(prob_stream):
    """Test probabilistic early exit on low-priority chunks."""
    # Low entropy data (allows early exit)
    data = b'\x00' * 10000
    
    # Always fail send attempts
    prob_stream._try_send_chunk = AsyncMock(return_value=False)
    
    # Patch random to force early exits
    with patch('seigr_toolset_transmissions.stream.probabilistic_stream.random.random', return_value=0.99):
        delivered = await prob_stream.send_probabilistic(data)
    
    # Should have early exits (not all chunks delivered)
    assert prob_stream.probabilistic_exits > 0


@pytest.mark.asyncio
async def test_send_probabilistic_metadata_tracking(prob_stream):
    """Test chunk metadata is properly tracked."""
    data = b'test' * 1024
    
    prob_stream._try_send_chunk = AsyncMock(return_value=True)
    
    await prob_stream.send_probabilistic(data)
    
    # Should have metadata for each chunk
    assert len(prob_stream.chunk_metadata) > 0
    
    for metadata in prob_stream.chunk_metadata.values():
        assert isinstance(metadata, ChunkMetadata)
        assert metadata.chunk_idx >= 0
        assert 0.0 <= metadata.entropy <= 1.0
        assert 0.0 <= metadata.delivery_prob <= 1.0
        assert metadata.attempts > 0


def test_get_delivery_stats(prob_stream):
    """Test delivery statistics reporting."""
    # Setup some metadata
    prob_stream.total_chunks = 10
    prob_stream.delivered_chunks = {0, 1, 2, 3, 4}
    prob_stream.successful_deliveries = 5
    prob_stream.probabilistic_exits = 2
    
    stats = prob_stream.get_delivery_stats()
    
    assert stats['total_chunks'] == 10
    assert stats['delivered_chunks'] == 5
    assert stats['successful_deliveries'] == 5
    assert stats['probabilistic_exits'] == 2
    assert stats['delivery_rate'] == 0.5


def test_get_chunk_report(prob_stream):
    """Test per-chunk delivery report."""
    # Add some chunk metadata
    prob_stream.chunk_metadata[0] = ChunkMetadata(
        chunk_idx=0,
        entropy=0.8,
        delivery_prob=0.95,
        replication=5,
        attempts=2,
        delivered=True
    )
    prob_stream.chunk_metadata[1] = ChunkMetadata(
        chunk_idx=1,
        entropy=0.3,
        delivery_prob=0.70,
        replication=10,
        attempts=1,
        delivered=False
    )
    
    report = prob_stream.get_chunk_report()
    
    assert len(report) == 2
    assert report[0]['chunk_idx'] == 0
    assert report[0]['delivered'] == True
    assert report[1]['chunk_idx'] == 1
    assert report[1]['delivered'] == False


@pytest.mark.asyncio
async def test_high_entropy_gets_more_attempts(prob_stream):
    """Test high entropy chunks get more retry attempts."""
    # High entropy chunk
    high_entropy = bytes(range(256)) * 4
    
    # Low entropy chunk
    low_entropy = b'\x00' * 1024
    
    # Always fail
    prob_stream._try_send_chunk = AsyncMock(return_value=False)
    
    # Force no early exits
    with patch('seigr_toolset_transmissions.stream.probabilistic_stream.random.random', return_value=0.0):
        await prob_stream.send_probabilistic(high_entropy)
        high_entropy_attempts = sum(m.attempts for m in prob_stream.chunk_metadata.values())
        
        prob_stream.chunk_metadata.clear()
        
        await prob_stream.send_probabilistic(low_entropy)
        low_entropy_attempts = sum(m.attempts for m in prob_stream.chunk_metadata.values())
    
    # High entropy should get more attempts
    assert high_entropy_attempts >= low_entropy_attempts


def test_stream_mode_is_probabilistic(prob_stream):
    """Test stream mode is set correctly."""
    assert prob_stream.mode == 'probabilistic'


def test_inherits_from_stt_stream(prob_stream):
    """Test ProbabilisticStream inherits from STTStream."""
    from seigr_toolset_transmissions.stream.stream import STTStream
    
    assert isinstance(prob_stream, STTStream)
    assert hasattr(prob_stream, 'session_id')
    assert hasattr(prob_stream, 'stream_id')
    assert hasattr(prob_stream, 'stc_wrapper')


def test_entropy_performance():
    """Benchmark: entropy calculation should be <10ms for 64KB."""
    import time
    
    data = b'x' * 65536  # 64KB
    
    # Warmup
    for _ in range(10):
        shannon_entropy(data)
    
    # Measure
    start = time.perf_counter()
    iterations = 100
    for _ in range(iterations):
        result = shannon_entropy(data)
    elapsed = time.perf_counter() - start
    
    avg_time = elapsed / iterations
    assert 0.0 <= result <= 1.0
    # Python implementation is slower than C - 10ms is acceptable
    assert avg_time < 0.01, f"Entropy calculation took {avg_time*1000:.2f}ms (target <10ms)"
