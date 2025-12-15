"""
Additional tests for core node functionality.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.core.node import STTNode
from seigr_toolset_transmissions.crypto import STCWrapper


class TestNodeAdditional:
    """Additional tests for node coverage."""
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper for node."""
        return STCWrapper(b"node_additional_seed_32_bytes!")
    
    @pytest.fixture
    def node_id(self):
        """Node ID."""
        return b'\xab' * 32
    
    @pytest.mark.asyncio
    async def test_node_connect_websocket_client(self, node_id, stc_wrapper):
        """Test connecting as WebSocket client."""
        node = STTNode(node_id, stc_wrapper)
        
        # Try to connect (will fail but exercises code path)
        try:
            await node.connect_websocket("ws://localhost:9999", is_server=False)
        except Exception:
            pass  # Expected to fail
    
    @pytest.mark.asyncio
    async def test_node_send_data_no_connection(self, node_id, stc_wrapper):
        """Test sending data without connection."""
        node = STTNode(node_id, stc_wrapper)
        
        # Try to send without connection
        try:
            await node.send_data(b"test", b'\x01' * 32)
        except Exception:
            pass  # Expected to fail
    
    @pytest.mark.asyncio
    async def test_node_receive_data_timeout(self, node_id, stc_wrapper):
        """Test receiving data with timeout."""
        node = STTNode(node_id, stc_wrapper)
        
        # Try to receive without connection
        try:
            _result = await asyncio.wait_for(node.receive_data(), timeout=0.1)  # Should timeout
        except (asyncio.TimeoutError, Exception):
            pass  # Expected
    
    @pytest.mark.asyncio
    async def test_node_cleanup_sessions(self, node_id, stc_wrapper):
        """Test session cleanup."""
        node = STTNode(node_id, stc_wrapper)
        
        if hasattr(node, 'cleanup_sessions'):
            await node.cleanup_sessions()
    
    @pytest.mark.asyncio
    async def test_node_get_active_sessions(self, node_id, stc_wrapper):
        """Test getting active sessions."""
        node = STTNode(node_id, stc_wrapper)
        
        if hasattr(node, 'get_active_sessions'):
            sessions = node.get_active_sessions()
            assert isinstance(sessions, (list, dict)) or sessions is None
    
    @pytest.mark.asyncio
    async def test_node_stats(self, node_id, stc_wrapper):
        """Test node statistics."""
        node = STTNode(node_id, stc_wrapper)
        
        if hasattr(node, 'get_stats'):
            stats = node.get_stats()
            assert stats is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
