"""
Tests for STC streaming encoder and decoder.
"""

import pytest
from seigr_toolset_transmissions.streaming import StreamEncoder, StreamDecoder
from seigr_toolset_transmissions.crypto import STCWrapper
from seigr_toolset_transmissions.utils.exceptions import STTStreamingError


class TestStreamEncoder:
    """Test STC streaming encoder."""
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper for streaming."""
        return STCWrapper(b"streaming_seed_32_bytes_minimum")
    
    @pytest.fixture
    def session_id(self):
        """Session ID for encoder."""
        return b'\x01' * 8
    
    @pytest.fixture
    def stream_id(self):
        """Stream ID for encoder."""
        return 1
    
    @pytest.fixture
    def encoder(self, stc_wrapper, session_id, stream_id):
        """Create stream encoder."""
        return StreamEncoder(
            stc_wrapper=stc_wrapper,
            session_id=session_id,
            stream_id=stream_id,
        )
    
    def test_create_encoder(self, encoder):
        """Test creating stream encoder."""
        assert encoder is not None
    
    def test_encode_chunk(self, encoder):
        """Test encoding a data chunk."""
        data = b"chunk data"
        
        encoded = encoder.encode_chunk(data)
        
        assert isinstance(encoded, bytes)
        assert len(encoded) > 0
    
    def test_encode_multiple_chunks(self, encoder):
        """Test encoding multiple chunks."""
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        
        encoded_chunks = [encoder.encode_chunk(chunk) for chunk in chunks]
        
        assert len(encoded_chunks) == 3
        assert all(isinstance(e, bytes) for e in encoded_chunks)
    
    def test_encode_empty_chunk(self, encoder):
        """Test encoding empty chunk."""
        encoded = encoder.encode_chunk(b"")
        
        assert isinstance(encoded, bytes)
    
    def test_encode_large_chunk(self, encoder):
        """Test encoding large chunk."""
        large_chunk = b"x" * 10000  # 10KB - reduced from 100KB for performance
        
        encoded = encoder.encode_chunk(large_chunk)
        
        assert isinstance(encoded, bytes)
    
    def test_encoder_maintains_sequence(self, encoder):
        """Test that encoder maintains sequence numbers."""
        encoder.encode_chunk(b"first")
        encoder.encode_chunk(b"second")
        encoder.encode_chunk(b"third")
        
        # Sequence should increment
        assert encoder.get_sequence() == 3
    
    def test_reset_encoder(self, encoder):
        """Test resetting encoder."""
        encoder.encode_chunk(b"data")
        encoder.encode_chunk(b"more")
        
        encoder.reset()
        
        assert encoder.get_sequence() == 0


class TestStreamDecoder:
    """Test STC streaming decoder."""
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper for streaming."""
        return STCWrapper(b"streaming_seed_32_bytes_minimum")
    
    @pytest.fixture
    def session_id(self):
        """Session ID for decoder."""
        return b'\x01' * 8
    
    @pytest.fixture
    def stream_id(self):
        """Stream ID for decoder."""
        return 1
    
    @pytest.fixture
    def decoder(self, stc_wrapper, session_id, stream_id):
        """Create stream decoder."""
        return StreamDecoder(
            stc_wrapper=stc_wrapper,
            session_id=session_id,
            stream_id=stream_id,
        )
    
    def test_create_decoder(self, decoder):
        """Test creating stream decoder."""
        assert decoder is not None
    
    def test_decode_chunk(self, stc_wrapper, session_id, stream_id):
        """Test decoding a chunk."""
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id)
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        original = b"test data"
        encoded = encoder.encode_chunk(original)
        decoded = decoder.decode_chunk(encoded)
        
        assert decoded == original
    
    def test_encode_decode_roundtrip(self, stc_wrapper, session_id, stream_id):
        """Test full encode/decode roundtrip."""
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id)
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        original_chunks = [b"first", b"second", b"third"]
        
        # Encode
        encoded_chunks = [encoder.encode_chunk(c) for c in original_chunks]
        
        # Decode
        decoded_chunks = [decoder.decode_chunk(e) for e in encoded_chunks]
        
        assert decoded_chunks == original_chunks
    
    def test_decode_out_of_order(self, stc_wrapper, session_id, stream_id):
        """Test decoding out-of-order chunks."""
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id)
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        chunks = [b"chunk0", b"chunk1", b"chunk2"]
        encoded = [encoder.encode_chunk(c) for c in chunks]
        
        # Decode in different order
        decoded2 = decoder.decode_chunk(encoded[2], sequence=2)
        decoded0 = decoder.decode_chunk(encoded[0], sequence=0)
        decoded1 = decoder.decode_chunk(encoded[1], sequence=1)
        
        # Should reorder correctly
        ordered = decoder.get_ordered_chunks()
        assert ordered == chunks
    
    def test_decode_empty_chunk(self, stc_wrapper, session_id, stream_id):
        """Test decoding empty chunk."""
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id)
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        encoded = encoder.encode_chunk(b"")
        decoded = decoder.decode_chunk(encoded)
        
        assert decoded == b""
    
    def test_decode_large_chunk(self, stc_wrapper, session_id, stream_id):
        """Test decoding large chunk."""
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id)
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        large_data = b"y" * 10000  # 10KB - reduced from 100KB for performance
        encoded = encoder.encode_chunk(large_data)
        decoded = decoder.decode_chunk(encoded)
        
        assert decoded == large_data
    
    def test_decode_corrupted_data(self, decoder):
        """Test decoding corrupted data fails."""
        corrupted = b'\xff\xfe\xfd\xfc'
        
        with pytest.raises(STTStreamingError):
            decoder.decode_chunk(corrupted)
    
    def test_different_stream_contexts(self, stc_wrapper, session_id):
        """Test that different streams have isolated contexts."""
        encoder1 = StreamEncoder(stc_wrapper, session_id, stream_id=1)
        encoder2 = StreamEncoder(stc_wrapper, session_id, stream_id=2)
        
        data = b"same data"
        
        encoded1 = encoder1.encode_chunk(data)
        encoded2 = encoder2.encode_chunk(data)
        
        # Different stream IDs should produce different encodings
        assert encoded1 != encoded2
    
    def test_cross_stream_decode_fails(self, stc_wrapper, session_id):
        """Test that decoder cannot decode from different stream."""
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id=1)
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id=2)
        
        data = b"stream data"
        encoded = encoder.encode_chunk(data)
        
        # Should fail to decode
        with pytest.raises(STTStreamingError):
            decoder.decode_chunk(encoded)


class TestStreamingIntegration:
    """Integration tests for streaming."""
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper for tests."""
        return STCWrapper(b"integration_seed_32_bytes_min!")
    
    def test_stream_large_file(self, stc_wrapper):
        """Test streaming large file in chunks."""
        session_id = b'\x01' * 8
        stream_id = 1
        
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id)
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        # Simulate large file - reduced from 1MB to 40KB for performance
        chunk_size = 4096
        total_size = 40 * 1024  # 40KB (10 chunks)
        
        original_data = b""
        decoded_data = b""
        
        # Encode in chunks
        for i in range(0, total_size, chunk_size):
            chunk = b"x" * min(chunk_size, total_size - i)
            original_data += chunk
            
            encoded = encoder.encode_chunk(chunk)
            decoded = decoder.decode_chunk(encoded)
            decoded_data += decoded
        
        assert decoded_data == original_data
        assert len(decoded_data) == total_size
    
    def test_concurrent_streams(self, stc_wrapper):
        """Test multiple concurrent streams."""
        session_id = b'\x02' * 8
        
        # Create 3 streams
        streams = []
        for stream_id in range(1, 4):
            encoder = StreamEncoder(stc_wrapper, session_id, stream_id)
            decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
            streams.append((encoder, decoder))
        
        # Send data on each stream
        for i, (encoder, decoder) in enumerate(streams):
            data = f"stream_{i}".encode()
            encoded = encoder.encode_chunk(data)
            decoded = decoder.decode_chunk(encoded)
            
            assert decoded == data
    
    def test_stream_with_packet_loss(self, stc_wrapper):
        """Test stream handling with simulated packet loss."""
        session_id = b'\x03' * 8
        stream_id = 3
        
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id)
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        # Encode 10 chunks
        chunks = [f"chunk_{i}".encode() for i in range(10)]
        encoded_chunks = [encoder.encode_chunk(c) for c in chunks]
        
        # Decode with some "lost" packets (skip indices 2, 5, 7)
        received_indices = [0, 1, 3, 4, 6, 8, 9]
        
        for idx in received_indices:
            decoder.decode_chunk(encoded_chunks[idx], sequence=idx)
        
        # Should still decode received chunks
        received = decoder.get_received_chunks()
        assert len(received) == len(received_indices)
    
    def test_bidirectional_streaming(self, stc_wrapper):
        """Test bidirectional streaming."""
        session_id = b'\x04' * 8
        stream_id = 4
        
        # Create encoders/decoders for both directions
        alice_encoder = StreamEncoder(stc_wrapper, session_id, stream_id)
        alice_decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        bob_encoder = StreamEncoder(stc_wrapper, session_id, stream_id)
        bob_decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        # Alice sends to Bob
        alice_message = b"Hello Bob"
        encoded = alice_encoder.encode_chunk(alice_message)
        decoded = bob_decoder.decode_chunk(encoded)
        assert decoded == alice_message
        
        # Bob sends to Alice
        bob_message = b"Hello Alice"
        encoded = bob_encoder.encode_chunk(bob_message)
        decoded = alice_decoder.decode_chunk(encoded)
        assert decoded == bob_message
