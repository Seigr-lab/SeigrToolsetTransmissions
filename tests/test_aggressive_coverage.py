"""
More aggressive tests for remaining gaps.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.session.session import STTSession
from seigr_toolset_transmissions.stream.stream import STTStream
from seigr_toolset_transmissions.handshake.handshake import STTHandshake
from seigr_toolset_transmissions.transport.udp import UDPTransport
from seigr_toolset_transmissions.crypto import STCWrapper


class TestAggressiveCoverage:
    """Aggressive coverage tests."""
    
    @pytest.fixture
    def stc_wrapper(self):
        return STCWrapper(b"aggressive_32_bytes_minimum_se!")
    
    @pytest.mark.asyncio
    async def test_session_rotate_key(self, stc_wrapper):
        """Test session key rotation."""
        session = STTSession(b"rotkeyyy", b"peer_rot", stc_wrapper)
        await session.rotate_key(stc_wrapper)
        assert session.key_version == 1
    
    @pytest.mark.asyncio
    async def test_session_rotate_key_existing(self, stc_wrapper):
        """Test rotating existing session key."""
        session = STTSession(b"rotkey22", b"peer_rot2", stc_wrapper)
        await session.rotate_key(stc_wrapper)
        await session.rotate_key(stc_wrapper)
        assert session.key_version == 2
    
    def test_session_get_statistics_alias(self, stc_wrapper):
        """Test get_statistics alias."""
        session = STTSession(b"statsyyy", b"peer_stt", stc_wrapper)
        stats = session.get_statistics()
        assert stats == session.get_stats()
    
    def test_session_is_active_method(self, stc_wrapper):
        """Test is_active_method."""
        session = STTSession(b"activvee", b"peer_act2", stc_wrapper)
        assert session.is_active_method() is True
        session.close()
        assert session.is_active_method() is False
    
    @pytest.mark.asyncio
    async def test_stream_sequence_tracking(self, stc_wrapper):
        """Test stream sequence tracking."""
        stream = STTStream(b"seqtrack", 5, stc_wrapper)
        await stream.send(b"data1")
        assert stream.sequence == 1
        await stream.send(b"data2")
        assert stream.sequence == 2
    
    @pytest.mark.asyncio
    async def test_udp_send_frame(self, stc_wrapper):
        """Test UDP send frame."""
        from seigr_toolset_transmissions.frame import STTFrame
        
        udp = UDPTransport("127.0.0.1", 0, stc_wrapper)
        await udp.start()
        
        frame = STTFrame(
            frame_type=1,
            session_id=b"udpframe",
            sequence=1,
            stream_id=1,
            payload=b"udp_test"
        )
        
        try:
            await udp.send_frame(frame, ("127.0.0.1", 9999))
        except Exception:
            pass
        
        await udp.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
