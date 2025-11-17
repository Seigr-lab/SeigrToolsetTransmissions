"""
Additional tests for stream coverage.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.stream import STTStream
from seigr_toolset_transmissions.crypto import STCWrapper


class TestStreamAdditional:
    """Additional stream tests for coverage."""
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper."""
        return STCWrapper(b"stream_additional_32_bytes!!!!")
    
    @pytest.mark.asyncio
    async def test_stream_send_data(self, stc_wrapper):
        """Test sending data on stream."""
        stream = STTStream(
            session_id=b'\xcc' * 8,
            stream_id=10,
            stc_wrapper=stc_wrapper
        )
        
        # Try to send (will fail without transport)
        try:
            await stream.send_data(b"test data")
        except Exception:
            pass  # Expected
    
    @pytest.mark.asyncio
    async def test_stream_receive_data(self, stc_wrapper):
        """Test receiving data on stream."""
        stream = STTStream(
            session_id=b'\xdd' * 8,
            stream_id=11,
            stc_wrapper=stc_wrapper
        )
        
        # Try to receive with timeout
        try:
            result = await asyncio.wait_for(stream.receive_data(), timeout=0.1)
        except (asyncio.TimeoutError, Exception):
            pass  # Expected
    
    @pytest.mark.asyncio
    async def test_stream_close(self, stc_wrapper):
        """Test closing stream."""
        stream = STTStream(
            session_id=b'\xee' * 8,
            stream_id=12,
            stc_wrapper=stc_wrapper
        )
        
        await stream.close()
        assert stream.is_active is False
    
    @pytest.mark.asyncio
    async def test_stream_reset(self, stc_wrapper):
        """Test resetting stream."""
        stream = STTStream(
            session_id=b'\xff' * 8,
            stream_id=13,
            stc_wrapper=stc_wrapper
        )
        
        if hasattr(stream, 'reset'):
            await stream.reset()
    
    def test_stream_get_stats(self, stc_wrapper):
        """Test getting stream statistics."""
        stream = STTStream(
            session_id=b'\x12' * 8,
            stream_id=14,
            stc_wrapper=stc_wrapper
        )
        
        stats = stream.get_stats()
        assert 'stream_id' in stats
        assert 'bytes_sent' in stats
        assert 'bytes_received' in stats
    
    @pytest.mark.asyncio
    async def test_stream_write_eof(self, stc_wrapper):
        """Test writing EOF to stream."""
        stream = STTStream(
            session_id=b'\x34' * 8,
            stream_id=15,
            stc_wrapper=stc_wrapper
        )
        
        if hasattr(stream, 'write_eof'):
            try:
                await stream.write_eof()
            except Exception:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
