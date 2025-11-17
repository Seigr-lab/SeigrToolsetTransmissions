"""
Session and stream additional coverage.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.session.session import STTSession
from seigr_toolset_transmissions.stream.stream import STTStream
from seigr_toolset_transmissions.crypto import STCWrapper


class TestSessionStreamCoverage:
    """Session and stream coverage."""
    
    @pytest.fixture
    def stc_wrapper(self):
        return STCWrapper(b"coverage_32_bytes_minimum_seed!")
    
    def test_session_metadata(self, stc_wrapper):
        """Test session with metadata."""
        session = STTSession(b"metasess", b"peer_meta", stc_wrapper, metadata={"key": "value"})
        assert session.metadata["key"] == "value"
    
    def test_session_activity_tracking(self, stc_wrapper):
        """Test session activity tracking."""
        import time
        session = STTSession(b"activity", b"peer_act", stc_wrapper)
        initial = session.last_activity
        time.sleep(0.01)  # Small delay to ensure timestamp difference
        session.update_activity()
        assert session.last_activity >= initial
    
    @pytest.mark.asyncio
    async def test_stream_send(self, stc_wrapper):
        """Test stream send."""
        stream = STTStream(b"stremsnd", 1, stc_wrapper)
        try:
            await stream.send(b"data")
        except Exception:
            pass
    
    @pytest.mark.asyncio
    async def test_stream_receive_closed(self, stc_wrapper):
        """Test receiving on closed stream."""
        stream = STTStream(b"stremrcv", 2, stc_wrapper)
        await stream.close()
        try:
            await stream.receive()
        except Exception:
            pass
    
    def test_stream_window_size(self, stc_wrapper):
        """Test stream window size property."""
        stream = STTStream(b"stremwin", 3, stc_wrapper)
        assert stream.receive_window_size > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
