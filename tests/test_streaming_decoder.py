"""
Tests for streaming decoder.
Tests the ACTUAL async streaming API.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.crypto import STCWrapper
from seigr_toolset_transmissions.streaming.decoder import StreamDecoder
from seigr_toolset_transmissions.streaming.encoder import StreamEncoder
from seigr_toolset_transmissions.utils.exceptions import STTStreamingError


class TestStreamDecoder:
    """Test stream decoder."""
    
    @pytest.fixture
    def stc_wrapper(self):
        """Create STC wrapper for encryption."""
        return STCWrapper(b"decoder_test_seed_32_bytes_min!!")
    
    @pytest.fixture
    def decoder(self, stc_wrapper):
        """Create decoder instance."""
        session_id = b"session1"
        stream_id = 1
        return StreamDecoder(stc_wrapper, session_id, stream_id)
    
    def test_decoder_initial_state(self, decoder):
        """Test decoder initial state."""
        stats = decoder.get_stats()
        assert stats['next_expected'] == 0
        assert stats['bytes_received'] == 0
        assert stats['buffered_segments'] == 0
        assert stats['ended'] is False
    
    def test_decoder_buffered_count(self, decoder):
        """Test getting buffered segment count."""
        count = decoder.get_buffered_count()
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_process_segment_invalid_format(self, decoder):
        """Test processing segment with invalid format."""
        # Too short - will fail decryption
        invalid_segment = b"short"
        
        # Should raise error when trying to decrypt
        with pytest.raises(Exception):  # STC will raise decryption error
            await decoder.process_segment(invalid_segment, 0)
    
    @pytest.mark.asyncio
    async def test_decoder_reset(self, stc_wrapper):
        """Test decoder reset clears state."""
        session_id = b"session2"
        stream_id = 2
        
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id)
        
        # Process some segments
        async for segment in encoder.send(b"test"):
            await decoder.process_segment(segment['data'], segment['sequence'])
        
        # Reset
        decoder.reset()
        
        # State should be cleared
        stats = decoder.get_stats()
        assert stats['next_expected'] == 0
        assert stats['bytes_received'] == 0
        assert stats['buffered_segments'] == 0
    
    def test_decoder_signal_end(self, decoder):
        """Test signaling decoder end."""
        decoder.signal_end()
        
        stats = decoder.get_stats()
        assert stats['ended'] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
