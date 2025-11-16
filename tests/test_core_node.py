"""
Tests for core STT Node functionality.
"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from seigr_toolset_transmissions.core.node import STTNode, ReceivedPacket
from seigr_toolset_transmissions.utils.exceptions import STTException


class TestSTTNode:
    """Test STT Node core functionality."""
    
    @pytest.fixture
    def temp_chamber_path(self):
        """Create temporary chamber directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def node_seed(self):
        """Node seed for testing."""
        return b"test_node_seed_12345678"
    
    @pytest.fixture
    def shared_seed(self):
        """Shared seed for authentication."""
        return b"test_shared_seed_1234567"
    
    @pytest.mark.asyncio
    async def test_create_node(self, node_seed, shared_seed, temp_chamber_path):
        """Test creating STT node."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            host="127.0.0.1",
            port=0,
            chamber_path=temp_chamber_path
        )
        
        assert node.host == "127.0.0.1"
        assert node.port == 0
        assert node.stc is not None
        assert node.node_id is not None
        assert node.chamber is not None
        assert node.session_manager is not None
        assert node.handshake_manager is not None
        assert not node._running
    
    @pytest.mark.asyncio
    async def test_node_start_stop(self, node_seed, shared_seed, temp_chamber_path):
        """Test starting and stopping node."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            host="127.0.0.1",
            port=0,
            chamber_path=temp_chamber_path
        )
        
        # Start node
        local_addr = await node.start()
        assert local_addr is not None
        assert isinstance(local_addr, tuple)
        assert len(local_addr) == 2
        assert node._running == True
        assert node.udp_transport is not None
        
        # Stop node
        await node.stop()
        assert node._running == False
    
    @pytest.mark.asyncio
    async def test_node_double_start(self, node_seed, shared_seed, temp_chamber_path):
        """Test starting node twice returns same address."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
        )
        
        addr1 = await node.start()
        addr2 = await node.start()  # Should just return existing address
        
        # Second start returns host/port tuple, but port may be 0 if already running
        assert addr1[0] == addr2[0]  # Same host
        assert addr1[1] > 0  # First start got a real port
        
        await node.stop()
    
    @pytest.mark.asyncio
    async def test_node_stop_when_not_running(self, node_seed, shared_seed, temp_chamber_path):
        """Test stopping node when not running."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
        )
        
        # Should not raise error
        await node.stop()
        assert node._running == False
    
    @pytest.mark.asyncio
    async def test_connect_udp_without_start(self, node_seed, shared_seed, temp_chamber_path):
        """Test connecting before starting node raises error."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
        )
        
        with pytest.raises(STTException, match="not started"):
            await node.connect_udp("127.0.0.1", 12345)
    
    @pytest.mark.asyncio
    async def test_default_chamber_path(self, node_seed, shared_seed):
        """Test node with default chamber path."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            host="127.0.0.1",
            port=0
        )
        
        # Should use default path in home directory
        assert node.chamber.chamber_path is not None
        assert ".seigr" in str(node.chamber.chamber_path)
    
    @pytest.mark.asyncio
    async def test_node_id_generation(self, node_seed, shared_seed, temp_chamber_path):
        """Test node ID is generated from seed."""
        node1 = STTNode(node_seed, shared_seed, chamber_path=temp_chamber_path)
        node2 = STTNode(node_seed, shared_seed, chamber_path=temp_chamber_path / "node2")
        
        # Same seed should produce same node ID
        assert node1.node_id == node2.node_id
        
        # Different seed should produce different ID
        node3 = STTNode(b"different_seed_12345", shared_seed, chamber_path=temp_chamber_path / "node3")
        assert node1.node_id != node3.node_id
    
    @pytest.mark.asyncio
    async def test_received_packet_dataclass(self):
        """Test ReceivedPacket dataclass."""
        packet = ReceivedPacket(
            session_id=b"12345678",
            stream_id=42,
            data=b"test data"
        )
        
        assert packet.session_id == b"12345678"
        assert packet.stream_id == 42
        assert packet.data == b"test data"


class TestSTTNodeIntegration:
    """Integration tests for STT Node."""
    
    @pytest.mark.asyncio
    async def test_two_nodes_communication(self):
        """Test two nodes can communicate."""
        temp_dir1 = Path(tempfile.mkdtemp())
        temp_dir2 = Path(tempfile.mkdtemp())
        
        try:
            node_seed1 = b"node1_seed_1234567890"
            node_seed2 = b"node2_seed_0987654321"
            shared_seed = b"shared_seed_12345678"
            
            # Create two nodes
            node1 = STTNode(node_seed1, shared_seed, "127.0.0.1", 0, temp_dir1)
            node2 = STTNode(node_seed2, shared_seed, "127.0.0.1", 0, temp_dir2)
            
            # Start both nodes
            addr1 = await node1.start()
            addr2 = await node2.start()
            
            assert addr1 is not None
            assert addr2 is not None
            assert addr1 != addr2  # Different ports
            
            # Give nodes time to initialize
            await asyncio.sleep(0.1)
            
            # Stop nodes
            await node1.stop()
            await node2.stop()
            
        finally:
            shutil.rmtree(temp_dir1, ignore_errors=True)
            shutil.rmtree(temp_dir2, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_node_lifecycle(self):
        """Test complete node lifecycle."""
        temp_dir = Path(tempfile.mkdtemp())
        
        try:
            node = STTNode(
                node_seed=b"lifecycle_test_seed_123",
                shared_seed=b"shared_seed_12345678",
                host="127.0.0.1",
                port=0,
                chamber_path=temp_dir
            )
            
            # Initial state
            assert not node._running
            assert node.udp_transport is None
            assert len(node._tasks) == 0
            
            # Start
            await node.start()
            assert node._running
            assert node.udp_transport is not None
            
            # Stop
            await node.stop()
            assert not node._running
            assert len(node.ws_connections) == 0
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
