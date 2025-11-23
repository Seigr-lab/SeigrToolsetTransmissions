"""
Edge case tests for streaming/encoder.py to achieve 100% coverage.

Targets uncovered lines:
- Line 52: Invalid mode validation
- Lines 108-109: Flow control credit exhaustion
- Line 143: end() called on live stream
- Line 146: end() called twice
- Lines 190-192: add_credits() method
"""

import pytest
import asyncio
from seigr_toolset_transmissions.streaming.encoder import BinaryStreamEncoder
from seigr_toolset_transmissions.utils.exceptions import STTStreamingError
from seigr_toolset_transmissions.crypto.stc_wrapper import STCWrapper


@pytest.fixture
def stc_wrapper():
    """Create STC wrapper for testing."""
    return STCWrapper(b'encoder_test_seed_32bytes_min!!')


@pytest.fixture
def session_id():
    """Session ID for encoder."""
    return b'encodeid'


@pytest.fixture
def stream_id():
    """Stream ID for encoder."""
    return 1


class TestEncoderValidation:
    """Test encoder input validation."""
    
    def test_invalid_mode(self, stc_wrapper, session_id, stream_id):
        """Test creating encoder with invalid mode (line 52)."""
        with pytest.raises(STTStreamingError, match="Invalid mode"):
            BinaryStreamEncoder(
                stc_wrapper,
                session_id,
                stream_id,
                mode='invalid_mode'
            )
    
    def test_valid_live_mode(self, stc_wrapper, session_id, stream_id):
        """Test creating encoder with valid 'live' mode."""
        encoder = BinaryStreamEncoder(
            stc_wrapper,
            session_id,
            stream_id,
            mode='live'
        )
        assert encoder.mode == 'live'
    
    def test_valid_bounded_mode(self, stc_wrapper, session_id, stream_id):
        """Test creating encoder with valid 'bounded' mode."""
        encoder = BinaryStreamEncoder(
            stc_wrapper,
            session_id,
            stream_id,
            mode='bounded'
        )
        assert encoder.mode == 'bounded'


class TestEncoderEndMarker:
    """Test end() method edge cases."""
    
    @pytest.mark.asyncio
    async def test_end_on_live_stream(self, stc_wrapper, session_id, stream_id):
        """Test calling end() on live stream (line 143)."""
        encoder = BinaryStreamEncoder(
            stc_wrapper,
            session_id,
            stream_id,
            mode='live'
        )
        
        with pytest.raises(STTStreamingError, match="Cannot end live stream"):
            await encoder.end()
    
    @pytest.mark.asyncio
    async def test_end_called_twice(self, stc_wrapper, session_id, stream_id):
        """Test calling end() twice on bounded stream (line 146)."""
        encoder = BinaryStreamEncoder(
            stc_wrapper,
            session_id,
            stream_id,
            mode='bounded'
        )
        
        # First call should return end marker
        result1 = await encoder.end()
        assert result1 is not None
        assert result1['is_end'] is True
        
        # Second call should return None (line 146)
        result2 = await encoder.end()
        assert result2 is None


class TestEncoderFlowControl:
    """Test flow control credit system."""
    
    @pytest.mark.asyncio
    async def test_credit_exhaustion_and_replenish(self, stc_wrapper, session_id, stream_id):
        """Test flow control when credits exhausted (lines 108-109, 190-192)."""
        encoder = BinaryStreamEncoder(
            stc_wrapper,
            session_id,
            stream_id,
            segment_size=10,  # Small segments
            mode='live'
        )
        
        # Exhaust credits
        encoder._credits = 0
        
        # Try to send data - should block waiting for credits
        send_task = asyncio.create_task(
            self._collect_segments(encoder, b'x' * 20)
        )
        
        # Give it a moment to hit the credit wait
        await asyncio.sleep(0.1)
        
        # Task should be blocked
        assert not send_task.done()
        
        # Add credits (lines 190-192)
        encoder.add_credits(10)
        
        # Now task should complete
        segments = await asyncio.wait_for(send_task, timeout=2.0)
        assert len(segments) == 2  # Two 10-byte segments
    
    async def _collect_segments(self, encoder, data):
        """Helper to collect all segments from send()."""
        segments = []
        async for segment in encoder.send(data):
            segments.append(segment)
        return segments
    
    @pytest.mark.asyncio
    async def test_add_credits_when_already_positive(self, stc_wrapper, session_id, stream_id):
        """Test add_credits() when credits already > 0 (line 191 branch)."""
        encoder = BinaryStreamEncoder(
            stc_wrapper,
            session_id,
            stream_id,
            mode='live'
        )
        
        # Initial credits should be 100
        assert encoder._credits == 100
        
        # Add more credits
        encoder.add_credits(50)
        
        # Should now have 150
        assert encoder._credits == 150


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
