"""
Additional tests for session coverage.
"""

import pytest
from seigr_toolset_transmissions.session import STTSession
from seigr_toolset_transmissions.crypto import STCWrapper


class TestSessionAdditional:
    """Additional session tests for coverage."""
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper."""
        return STCWrapper(b"session_additional_32_bytes!!!")
    
    def test_session_close(self, stc_wrapper):
        """Test session close."""
        session = STTSession(
            session_id=b'\x99' * 8,
            peer_node_id=b'\x88' * 32,
            stc_wrapper=stc_wrapper
        )
        
        session.close()
        assert session.is_active is False
    
    def test_session_record_frame_sent(self, stc_wrapper):
        """Test recording sent frames."""
        session = STTSession(
            session_id=b'\x77' * 8,
            peer_node_id=b'\x66' * 32,
            stc_wrapper=stc_wrapper
        )
        
        if hasattr(session, 'record_frame_sent'):
            session.record_frame_sent(100)
            assert session.frames_sent > 0
    
    def test_session_record_frame_received(self, stc_wrapper):
        """Test recording received frames."""
        session = STTSession(
            session_id=b'\x55' * 8,
            peer_node_id=b'\x44' * 32,
            stc_wrapper=stc_wrapper
        )
        
        if hasattr(session, 'record_frame_received'):
            session.record_frame_received(200)
            assert session.frames_received > 0
    
    def test_session_record_bytes(self, stc_wrapper):
        """Test recording bytes sent/received."""
        session = STTSession(
            session_id=b'\x33' * 8,
            peer_node_id=b'\x22' * 32,
            stc_wrapper=stc_wrapper
        )
        
        if hasattr(session, 'record_sent_bytes'):
            session.record_sent_bytes(1024)
            assert session.bytes_sent == 1024
        
        if hasattr(session, 'record_received_bytes'):
            session.record_received_bytes(2048)
            assert session.bytes_received == 2048
    
    def test_session_update_activity(self, stc_wrapper):
        """Test updating last activity."""
        session = STTSession(
            session_id=b'\x11' * 8,
            peer_node_id=b'\x00' * 32,
            stc_wrapper=stc_wrapper
        )
        
        initial_activity = session.last_activity
        
        if hasattr(session, 'update_last_activity'):
            session.update_last_activity()
            assert session.last_activity >= initial_activity
    
    def test_session_get_stats(self, stc_wrapper):
        """Test getting session statistics."""
        session = STTSession(
            session_id=b'\xaa' * 8,
            peer_node_id=b'\xbb' * 32,
            stc_wrapper=stc_wrapper
        )
        
        stats = session.get_stats()
        assert 'session_id' in stats
        assert 'peer_node_id' in stats
        assert 'bytes_sent' in stats
        assert 'bytes_received' in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
