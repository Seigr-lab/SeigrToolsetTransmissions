"""
Tests for streaming decoder.
"""

import pytest
from seigr_toolset_transmissions.crypto import STCWrapper
from seigr_toolset_transmissions.streaming.decoder import StreamDecoder
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
        session_id = b"session123"
        stream_id = 1
        return StreamDecoder(stc_wrapper, session_id, stream_id)
    
    def test_decoder_empty_buffer(self, decoder):
        """Test getting ordered chunks when buffer is empty."""
        chunks = decoder.get_ordered_chunks()
        assert chunks == []
    
    def test_decoder_invalid_chunk_format(self, decoder):
        """Test decoding chunk with invalid format raises error."""
        # Chunk too short (missing sequence number)
        invalid_chunk = b"short"
        
        with pytest.raises(STTStreamingError, match="Decryption failed"):
            decoder.decode_chunk(invalid_chunk)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
