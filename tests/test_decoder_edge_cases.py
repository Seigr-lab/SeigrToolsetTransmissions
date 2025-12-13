"""
Edge case tests for streaming/decoder.py to achieve 100% coverage.

Targets uncovered lines:
- Line 156: encoded_segment too short validation
- Lines 224-225: asyncio.QueueEmpty exception in reset()
"""

import pytest
from seigr_toolset_transmissions.streaming.decoder import BinaryStreamDecoder
from seigr_toolset_transmissions.utils.exceptions import STTStreamingError
from seigr_toolset_transmissions.crypto.stc_wrapper import STCWrapper


# Segment structure constants for test maintainability
# These values represent the binary protocol structure and should match the implementation.
# If the protocol changes, update these constants accordingly.
SEGMENT_HEADER_SIZE = 16  # bytes, per protocol spec
FLAG_SIZE = 1  # bytes, flags byte at start of segment
MIN_SEGMENT_LEN = FLAG_SIZE + SEGMENT_HEADER_SIZE  # minimum valid segment = 17 bytes


@pytest.fixture
def stc_wrapper():
    """Create STC wrapper for testing."""
    return STCWrapper(b'decoder_test_seed_32bytes_min!!')


@pytest.fixture
def session_id():
    """Session ID for decoder."""
    return b'decodeid'


@pytest.fixture
def stream_id():
    """Stream ID for decoder."""
    return 1


@pytest.fixture
def decoder(session_id, stream_id, stc_wrapper):
    """Create decoder instance."""
    return BinaryStreamDecoder(
        stc_wrapper,
        session_id,
        stream_id
    )


class TestDecoderValidation:
    """Test decoder input validation paths."""
    
    @pytest.mark.asyncio
    async def test_decrypt_segment_not_bytes(self, decoder):
        """Test decryption with non-bytes input (line 155-156)."""
        # Pass a string instead of bytes
        with pytest.raises(STTStreamingError, match="must be bytes"):
            await decoder._decrypt_segment("not bytes")
    
    @pytest.mark.asyncio
    async def test_decrypt_segment_too_short(self, decoder):
        """Test decryption with segment shorter than minimum (line 158-159)."""
        # Minimum valid segment is MIN_SEGMENT_LEN bytes: 1 flag + 16 header
        # Test with 16 bytes (too short)
        short_segment = b'\x00' * SEGMENT_HEADER_SIZE
        
        with pytest.raises(STTStreamingError, match="too short"):
            await decoder._decrypt_segment(short_segment)
    
    @pytest.mark.asyncio
    async def test_decrypt_segment_minimum_length(self, decoder):
        """Test edge case: exactly 17 bytes (minimum valid)."""
        # This should NOT raise the "too short" error
        # 1 byte flag + 16 byte header + 0 bytes encrypted data
        min_segment = b'\x00' * MIN_SEGMENT_LEN
        
        # This will fail at ChunkHeader parsing or decryption,
        # but NOT at the length check on line 158
        try:
            await decoder._decrypt_segment(min_segment)
        except Exception as e:
            # Should NOT be "too short" error
            assert "too short" not in str(e)


class TestDecoderReset:
    """Test decoder reset() method edge cases."""
    
    def test_reset_empty_queue(self, decoder):
        """Test reset() when queue is already empty (lines 224-225)."""
        # Queue should be empty initially
        assert decoder._segment_queue.empty()
        
        # Reset should handle empty queue gracefully (line 224 exception)
        decoder.reset()
        
        # Verify reset occurred
        assert decoder._next_expected_sequence == 0
        assert decoder._ended is False
        assert decoder._total_bytes_received == 0
    
    @pytest.mark.asyncio
    async def test_reset_with_items_in_queue(self, decoder):
        """Test reset() with items in queue."""
        # Add some items to the queue
        await decoder._segment_queue.put(b'data1')
        await decoder._segment_queue.put(b'data2')
        
        assert decoder._segment_queue.qsize() == 2
        
        # Reset should clear the queue
        decoder.reset()
        
        # Queue should now be empty
        assert decoder._segment_queue.empty()
        assert decoder._next_expected_sequence == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
