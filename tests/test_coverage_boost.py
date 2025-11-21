"""
Simple tests to boost coverage for specific uncovered lines.
"""
import pytest
from seigr_toolset_transmissions.session.session_manager import SessionManager
from seigr_toolset_transmissions.stream.stream_manager import StreamManager


class TestCoverageBoost:
    """Tests targeting specific uncovered lines."""
    
    def test_session_manager_active_count(self, test_node_id, stc_wrapper):
        """Test get_active_session_count method (line 124)."""
        manager = SessionManager(test_node_id, stc_wrapper)
        
        # Should be 0 initially
        count = manager.get_active_session_count()
        assert count == 0
    
    def test_stream_manager_get_active_streams(self, test_node_id, stc_wrapper):
        """Test get_active_streams method (line 133)."""
        manager = StreamManager(test_node_id, stc_wrapper)
        
        # Should be empty list initially
        active_streams = manager.get_active_streams()
        assert active_streams == []
    
    def test_stream_manager_get_stream_count(self, test_node_id, stc_wrapper):
        """Test get_stream_count method (line 140)."""
        manager = StreamManager(test_node_id, stc_wrapper)
        
        # Should be 0 initially
        count = manager.get_stream_count()
        assert count == 0
    
    def test_stream_manager_has_stream(self, test_node_id, stc_wrapper):
        """Test has_stream method."""
        manager = StreamManager(test_node_id, stc_wrapper)
        
        # Non-existent stream
        exists = manager.has_stream(999)
        assert exists is False
    
    async def test_stream_manager_close_all(self, test_node_id, stc_wrapper):
        """Test close_all_streams method (line 189)."""
        manager = StreamManager(test_node_id, stc_wrapper)
        
        # Close all streams (should be 0)
        closed_count = await manager.close_all_streams()
        assert closed_count == 0
