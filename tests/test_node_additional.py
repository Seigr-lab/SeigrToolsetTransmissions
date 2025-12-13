"""
Additional core node tests targeting uncovered lines.
"""

import pytest
from seigr_toolset_transmissions.core.node import STTNode


class TestNodeAdditional:
    """Additional node tests for uncovered lines."""
    
    @pytest.fixture
    def node(self):
        node_seed = b"node_additional_32_bytes_minim!"
        shared_seed = b"shared_additional_32_bytes_min!"
        return STTNode(node_seed, shared_seed, "127.0.0.1", 0)
    
    @pytest.mark.asyncio
    async def test_node_storage_initialization(self, node):
        """Test node storage initialization (storage is optional)."""
        # Storage is now optional - defaults to None
        assert node.storage is None
        assert node.node_id is not None
    
    @pytest.mark.asyncio
    async def test_node_session_manager(self, node):
        """Test node session manager."""
        assert node.session_manager is not None
        assert node.handshake_manager is not None
    
    @pytest.mark.asyncio
    async def test_node_start_udp_transport(self, node):
        """Test node starts UDP transport."""
        addr, port = await node.start()
        assert port > 0
        assert node.udp_transport is not None
        await node.stop()
    
    @pytest.mark.asyncio
    async def test_node_receive_queue(self, node):
        """Test node receive queue initialization."""
        assert node._recv_queue is not None
        await node.start()
        await node.stop()
    
    @pytest.mark.asyncio
    async def test_node_running_flag(self, node):
        """Test node running flag."""
        assert node._running is False
        await node.start()
        assert node._running is True
        await node.stop()
        assert node._running is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
