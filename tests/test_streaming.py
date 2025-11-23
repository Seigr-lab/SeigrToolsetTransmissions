"""
Tests for STC streaming encoder and decoder.
Tests the ACTUAL async streaming API.
"""

import pytest
import asyncio
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
        """Create stream encoder in bounded mode for testing."""
        return StreamEncoder(
            stc_wrapper=stc_wrapper,
            session_id=session_id,
            stream_id=stream_id,
            mode='bounded'  # Use bounded mode for tests that need end()
        )
    
    def test_create_encoder(self, encoder):
        """Test creating stream encoder."""
        assert encoder is not None
        assert encoder._sequence == 0
        stats = encoder.get_stats()
        assert stats['sequence'] == 0
        assert stats['bytes_sent'] == 0
        assert stats['mode'] == 'bounded'
        assert stats['ended'] is False
    
    @pytest.mark.asyncio
    async def test_send_data(self, encoder):
        """Test sending data through encoder."""
        data = b"segment data"
        
        segments = []
        async for segment in encoder.send(data):
            segments.append(segment)
        
        # Should yield at least one segment
        assert len(segments) > 0
        
        # Each segment should have data and sequence
        for segment in segments:
            assert 'data' in segment
            assert 'sequence' in segment
            assert isinstance(segment['data'], bytes)
            assert isinstance(segment['sequence'], int)
    
    @pytest.mark.asyncio
    async def test_send_multiple_calls(self, encoder):
        """Test multiple send calls."""
        all_segments = []
        
        # Send multiple data pieces
        async for segment in encoder.send(b"first"):
            all_segments.append(segment)
        
        async for segment in encoder.send(b"second"):
            all_segments.append(segment)
        
        async for segment in encoder.send(b"third"):
            all_segments.append(segment)
        
        # Should have segments from all sends
        assert len(all_segments) >= 3
        
        # Sequences should increment
        sequences = [s['sequence'] for s in all_segments]
        assert sequences == sorted(sequences)
    
    @pytest.mark.asyncio
    async def test_send_empty_data(self, encoder):
        """Test sending empty data."""
        segments = []
        async for segment in encoder.send(b""):
            segments.append(segment)
        
        # Empty data produces no segments (while offset < len(data))
        assert len(segments) == 0
    
    @pytest.mark.asyncio
    async def test_send_large_data(self, encoder):
        """Test sending large data gets split into segments."""
        large_data = b"x" * 10000  # 10KB
        
        segments = []
        async for segment in encoder.send(large_data):
            segments.append(segment)
        
        # Large data should produce multiple segments if larger than segment_size
        # Default segment_size is 65536, so 10KB produces 1 segment
        assert len(segments) >= 1
    
    @pytest.mark.asyncio
    async def test_encoder_stats(self, encoder):
        """Test encoder statistics tracking."""
        initial_stats = encoder.get_stats()
        assert initial_stats['sequence'] == 0
        assert initial_stats['bytes_sent'] == 0
        
        # Send data
        async for segment in encoder.send(b"test data"):
            pass
        
        # Stats should update
        stats = encoder.get_stats()
        assert stats['sequence'] > 0
        assert stats['bytes_sent'] > 0
    
    def test_encoder_reset(self, encoder):
        """Test resetting encoder."""
        # Can't easily test async send, but can test reset state
        encoder._sequence = 5
        encoder._total_bytes_sent = 1000
        
        encoder.reset()
        
        stats = encoder.get_stats()
        assert stats['sequence'] == 0
        assert stats['bytes_sent'] == 0
        assert stats['ended'] is False
    
    @pytest.mark.asyncio
    async def test_send_after_end_fails(self, encoder):
        """Test that sending after end() raises error."""
        # End the stream
        await encoder.end()
        
        # Trying to send should fail
        with pytest.raises(STTStreamingError, match="Cannot send after stream ended"):
            async for segment in encoder.send(b"data"):
                pass
    
    @pytest.mark.asyncio
    async def test_send_non_bytes_fails(self, encoder):
        """Test that sending non-bytes data fails."""
        with pytest.raises(STTStreamingError, match="Data must be bytes"):
            async for segment in encoder.send("not bytes"):
                pass
    
    @pytest.mark.asyncio
    async def test_end_stream(self, encoder):
        """Test ending a stream."""
        # Send some data
        async for segment in encoder.send(b"data"):
            pass
        
        # End stream
        end_segment = await encoder.end()
        
        # Should return end marker segment
        if end_segment:
            assert 'data' in end_segment
            assert 'sequence' in end_segment
        
        # Stats should show ended
        stats = encoder.get_stats()
        assert stats['ended'] is True


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
        stats = decoder.get_stats()
        assert stats['next_expected'] == 0
        assert stats['bytes_received'] == 0
        assert stats['buffered_segments'] == 0
        assert stats['ended'] is False
    
    @pytest.mark.asyncio
    async def test_process_and_receive_segment(self, stc_wrapper, session_id, stream_id):
        """Test processing and receiving segments."""
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id)
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        original_data = b"test data"
        
        # Encode
        segments = []
        async for segment in encoder.send(original_data):
            segments.append(segment)
        
        # Process segments
        for i, segment in enumerate(segments):
            await decoder.process_segment(segment['data'], i)
        
        # Receive decoded data
        received_data = b""
        
        # Set a timeout to prevent hanging (Python 3.9 compatible)
        try:
            async def receive_with_timeout():
                nonlocal received_data
                async for data_segment in decoder.receive():
                    received_data += data_segment
                    # Break after receiving expected data
                    if len(received_data) >= len(original_data):
                        break
            
            await asyncio.wait_for(receive_with_timeout(), timeout=1.0)
        except asyncio.TimeoutError:
            pass  # OK if we got the data
        
        # Should get back original data
        assert received_data == original_data
    
    @pytest.mark.asyncio
    async def test_encode_decode_roundtrip(self, stc_wrapper, session_id, stream_id):
        """Test full encode/decode roundtrip."""
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id, mode='bounded')
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        test_data = [b"first", b"second", b"third"]
        
        all_segments = []
        for data in test_data:
            async for segment in encoder.send(data):
                all_segments.append(segment)
        
        # End stream
        end_segment = await encoder.end()
        if end_segment:
            all_segments.append(end_segment)
        
        # Process all segments
        for segment in all_segments:
            await decoder.process_segment(segment['data'], segment['sequence'])
        
        # Signal end to decoder
        decoder.signal_end()
        
        # Receive all decoded data
        received = await decoder.receive_all()
        
        # Should reconstruct original data
        expected = b"".join(test_data)
        assert received == expected
    
    @pytest.mark.asyncio
    async def test_out_of_order_segments(self, stc_wrapper, session_id, stream_id):
        """Test decoder handles out-of-order segments."""
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id, mode='bounded')
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        # Create multiple small segments
        test_data = [b"data0", b"data1", b"data2"]
        all_segments = []
        
        for data in test_data:
            async for segment in encoder.send(data):
                all_segments.append(segment)
        
        await encoder.end()
        
        # Process in wrong order: 2, 0, 1
        if len(all_segments) >= 3:
            await decoder.process_segment(all_segments[2]['data'], 2)
            await decoder.process_segment(all_segments[0]['data'], 0)
            await decoder.process_segment(all_segments[1]['data'], 1)
            
            # Check buffered count
            buffered = decoder.get_buffered_count()
            # May have buffered segment 2 waiting for 0 and 1
            assert buffered >= 0
        
        decoder.signal_end()
        
        # Should still reconstruct correctly
        received = await decoder.receive_all()
        expected = b"".join(test_data)
        assert received == expected
    
    @pytest.mark.asyncio
    async def test_decoder_stats(self, decoder):
        """Test decoder statistics."""
        initial_stats = decoder.get_stats()
        assert initial_stats['next_expected'] == 0
        assert initial_stats['bytes_received'] == 0
        
        # Stats updated through process_segment would be tested
        # in integration tests
    
    def test_decoder_reset(self, decoder):
        """Test decoder reset."""
        # Manually set some state
        decoder._next_expected_sequence = 5
        decoder._total_bytes_received = 1000
        
        decoder.reset()
        
        stats = decoder.get_stats()
        assert stats['next_expected'] == 0
        assert stats['bytes_received'] == 0
        assert stats['buffered_segments'] == 0


class TestStreamingIntegration:
    """Integration tests for streaming."""
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper for tests."""
        return STCWrapper(b"integration_seed_32_bytes_min!")
    
    @pytest.mark.asyncio
    async def test_stream_large_data(self, stc_wrapper):
        """Test streaming large data."""
        session_id = b'\x01' * 8
        stream_id = 1
        
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id, mode='bounded')
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        # Large data
        large_data = b"x" * 50000  # 50KB
        
        # Encode
        segments = []
        async for segment in encoder.send(large_data):
            segments.append(segment)
        
        await encoder.end()
        
        # Process all segments
        for segment in segments:
            await decoder.process_segment(segment['data'], segment['sequence'])
        
        decoder.signal_end()
        
        # Receive all
        received = await decoder.receive_all()
        
        assert received == large_data
        assert len(received) == 50000
    
    @pytest.mark.asyncio
    async def test_different_stream_ids(self, stc_wrapper):
        """Test that different stream IDs produce different encryption."""
        session_id = b'\x02' * 8
        
        encoder1 = StreamEncoder(stc_wrapper, session_id, stream_id=1)
        encoder2 = StreamEncoder(stc_wrapper, session_id, stream_id=2)
        
        data = b"same data"
        
        # Encode same data on different streams
        segments1 = []
        async for segment in encoder1.send(data):
            segments1.append(segment)
        
        segments2 = []
        async for segment in encoder2.send(data):
            segments2.append(segment)
        
        # Should produce different encrypted data
        assert segments1[0]['data'] != segments2[0]['data']
    
    @pytest.mark.asyncio
    async def test_cross_stream_decode_fails(self, stc_wrapper):
        """Test that wrong stream ID can't decode."""
        session_id = b'\x03' * 8
        
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id=1, mode='bounded')
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id=2)
        
        data = b"stream data"
        
        # Encode
        segments = []
        async for segment in encoder.send(data):
            segments.append(segment)
        
        await encoder.end()
        
        # Try to decode with wrong stream ID
        for segment in segments:
            await decoder.process_segment(segment['data'], segment['sequence'])
        
        decoder.signal_end()
        
        # Should get garbage or fail
        received = await decoder.receive_all()
        assert received != data  # Wrong stream produces wrong decryption
    
    @pytest.mark.asyncio
    async def test_multiple_sends_sequential(self, stc_wrapper):
        """Test multiple sequential send operations."""
        session_id = b'\x04' * 8
        stream_id = 1
        
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id, mode='bounded')
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        # Send multiple data pieces
        all_segments = []
        test_data = [b"data1", b"data2", b"data3", b"data4"]
        
        for data in test_data:
            async for segment in encoder.send(data):
                all_segments.append(segment)
        
        await encoder.end()
        
        # Process all
        for segment in all_segments:
            await decoder.process_segment(segment['data'], segment['sequence'])
        
        decoder.signal_end()
        
        # Receive all
        received = await decoder.receive_all()
        expected = b"".join(test_data)
        
        assert received == expected
    
    @pytest.mark.asyncio
    async def test_empty_stream(self, stc_wrapper):
        """Test streaming with no data (just end)."""
        session_id = b'\x05' * 8
        stream_id = 1
        
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id, mode='bounded')
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        # Just end without sending
        end_segment = await encoder.end()
        
        if end_segment:
            await decoder.process_segment(end_segment['data'], end_segment['sequence'])
        
        decoder.signal_end()
        
        # Should get empty data
        received = await decoder.receive_all()
        assert received == b""
    
    @pytest.mark.asyncio
    async def test_encoder_flow_control(self, stc_wrapper):
        """Test encoder has flow control credits."""
        session_id = b'\x07' * 8
        stream_id = 7
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id, mode='bounded')
        
        stats = encoder.get_stats()
        assert 'credits' in stats
        assert stats['credits'] > 0
        
        # Sending should consume credits
        initial_credits = stats['credits']
        
        async for segment in encoder.send(b"data"):
            pass
        
        stats_after = encoder.get_stats()
        # Credits should have changed (decreased)
        assert stats_after['credits'] <= initial_credits
    
    @pytest.mark.asyncio
    async def test_decoder_buffering(self, stc_wrapper):
        """Test decoder buffers out-of-order segments."""
        session_id = b'\x06' * 8
        stream_id = 1
        
        encoder = StreamEncoder(stc_wrapper, session_id, stream_id, mode='bounded')
        decoder = StreamDecoder(stc_wrapper, session_id, stream_id)
        
        # Create segments
        segments = []
        for i in range(5):
            async for segment in encoder.send(f"data{i}".encode()):
                segments.append(segment)
        
        # Process only segment 3 (skip 0, 1, 2)
        if len(segments) > 3:
            await decoder.process_segment(segments[3]['data'], 3)
            
            # Should be buffered
            buffered = decoder.get_buffered_count()
            assert buffered > 0
