"""
Tests for core STT Node functionality.

STT is a transmission protocol - storage is optional and pluggable.
"""

import pytest
import asyncio

from seigr_toolset_transmissions.core.node import STTNode, ReceivedPacket
from seigr_toolset_transmissions.utils.exceptions import STTException


class TestSTTNode:
    """Test STT Node core functionality."""
    
    @pytest.fixture
    def node_seed(self):
        """Node seed for testing."""
        return b"test_node_seed_12345678"
    
    @pytest.fixture
    def shared_seed(self):
        """Shared seed for authentication."""
        return b"test_shared_seed_1234567"
    
    @pytest.mark.asyncio
    async def test_create_node(self, node_seed, shared_seed):
        """Test creating STT node."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            host="127.0.0.1",
            port=0,
            storage=None
        )
        
        assert node.host == "127.0.0.1"
        assert node.port == 0
        assert node.stc is not None
        assert node.node_id is not None
        assert node.storage is None  # No storage by default
        assert node.session_manager is not None
        assert node.handshake_manager is not None
        assert not node._running
    
    @pytest.mark.asyncio
    async def test_node_start_stop(self, node_seed, shared_seed):
        """Test starting and stopping node."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            host="127.0.0.1",
            port=0,
            storage=None
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
    async def test_node_double_start(self, node_seed, shared_seed):
        """Test starting node twice returns same address."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        
        addr1 = await node.start()
        addr2 = await node.start()  # Should just return existing address
        
        # Second start returns host/port tuple, but port may be 0 if already running
        assert addr1[0] == addr2[0]  # Same host
        assert addr1[1] > 0  # First start got a real port
        
        await node.stop()
    
    @pytest.mark.asyncio
    async def test_node_stop_when_not_running(self, node_seed, shared_seed):
        """Test stopping node when not running."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        
        # Should not raise error
        await node.stop()
        assert node._running == False
    
    @pytest.mark.asyncio
    async def test_connect_udp_without_start(self, node_seed, shared_seed):
        """Test connecting before starting node raises error."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        
        with pytest.raises(STTException, match="not started"):
            await node.connect_udp("127.0.0.1", 12345)
    
    @pytest.mark.asyncio
    async def test_node_without_storage(self, node_seed, shared_seed):
        """Test node works without storage (pure transmission mode)."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            host="127.0.0.1",
            port=0,
            storage=None
        )
        
        # Storage should be None
        assert node.storage is None
        
        # Node should still work for transmission
        addr = await node.start()
        assert addr is not None
        await node.stop()
    
    @pytest.mark.asyncio
    async def test_node_with_storage(self, node_seed, shared_seed):
        """Test node with pluggable storage."""
        from seigr_toolset_transmissions.storage import InMemoryStorage
        
        storage = InMemoryStorage()
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            host="127.0.0.1",
            port=0,
            storage=storage
        )
        
        # Storage should be set
        assert node.storage is storage
        
        # Node should work
        addr = await node.start()
        assert addr is not None
        await node.stop()
    
    @pytest.mark.asyncio
    async def test_node_id_generation(self, node_seed, shared_seed):
        """Test node ID is generated from seed."""
        node1 = STTNode(node_seed, shared_seed, storage=None)
        node2 = STTNode(node_seed, shared_seed, storage=None)
        
        # Same seed should produce same node ID
        assert node1.node_id == node2.node_id
        
        # Different seed should produce different ID
        node3 = STTNode(b"different_seed_12345", shared_seed, storage=None)
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
    
    @pytest.fixture
    def node_seed(self):
        """Node seed for testing."""
        return b"test_node_seed_12345678"
    
    @pytest.fixture
    def shared_seed(self):
        """Shared seed for authentication."""
        return b"test_shared_seed_1234567"
    
    @pytest.mark.asyncio
    async def test_two_nodes_communication(self):
        """Test two nodes can communicate."""
        node_seed1 = b"node1_seed_1234567890"
        node_seed2 = b"node2_seed_0987654321"
        shared_seed = b"shared_seed_12345678"
        
        # Create two nodes (no storage - pure transmission)
        node1 = STTNode(node_seed1, shared_seed, "127.0.0.1", 0, storage=None)
        node2 = STTNode(node_seed2, shared_seed, "127.0.0.1", 0, storage=None)
        
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
    
    @pytest.mark.asyncio
    async def test_node_lifecycle(self):
        """Test complete node lifecycle."""
        node = STTNode(
            node_seed=b"lifecycle_test_seed_123",
            shared_seed=b"shared_seed_12345678",
            host="127.0.0.1",
            port=0,
            storage=None
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
    
    @pytest.mark.asyncio
    async def test_connect_udp_not_started(self, node_seed, shared_seed):
        """Test connecting UDP before node is started raises error."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        
        with pytest.raises(STTException, match="Node not started"):
            await node.connect_udp("127.0.0.1", 9999)
    
    @pytest.mark.asyncio
    async def test_node_stop_when_not_running(self, node_seed, shared_seed):
        """Test stopping node when not running."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        
        # Should not raise error
        await node.stop()
        assert not node._running
    
    @pytest.mark.asyncio
    async def test_node_session_manager_initialization(self, node_seed, shared_seed):
        """Test node initializes session manager."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        
        assert node.session_manager is not None
        assert node.session_manager.local_node_id == node.node_id
    
    @pytest.mark.asyncio
    async def test_node_handshake_manager_initialization(self, node_seed, shared_seed):
        """Test node initializes handshake manager."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        
        assert node.handshake_manager is not None
        assert node.handshake_manager.node_id == node.node_id
    
    @pytest.mark.asyncio
    async def test_node_receive_queue_initialization(self, node_seed, shared_seed):
        """Test node initializes receive queue."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        
        assert node._recv_queue is not None
        assert isinstance(node._recv_queue, asyncio.Queue)
    
    @pytest.mark.asyncio
    async def test_node_host_port_configuration(self, node_seed, shared_seed):
        """Test node host and port configuration."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            host="192.168.1.1",
            port=5000,
            storage=None
        )
        
        assert node.host == "192.168.1.1"
        assert node.port == 5000
    
    @pytest.mark.asyncio
    async def test_node_ws_connections_empty(self, node_seed, shared_seed):
        """Test WebSocket connections dict is empty initially."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        
        assert len(node.ws_connections) == 0
    
    @pytest.mark.asyncio
    async def test_node_tasks_empty_initially(self, node_seed, shared_seed):
        """Test tasks list is empty initially."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        
        assert len(node._tasks) == 0
    
    @pytest.mark.asyncio
    async def test_node_get_stats(self, node_seed, shared_seed):
        """Test node statistics retrieval."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        
        stats = node.get_stats()
        
        assert isinstance(stats, dict)
        assert 'node_id' in stats
        assert stats['node_id'] == node.node_id.hex()
    
    @pytest.mark.asyncio
    async def test_node_receive_queue(self, node_seed, shared_seed):
        """Test node receive queue."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        
        # Queue should be empty initially
        assert node._recv_queue.empty()
        
        # Put test packet
        test_packet = ReceivedPacket(
            session_id=b'\x01' * 8,
            stream_id=1,
            data=b"test data"
        )
        await node._recv_queue.put(test_packet)
        
        assert not node._recv_queue.empty()
    
    @pytest.mark.asyncio
    async def test_handle_handshake_frame(self, node_seed, shared_seed):
        """Test handling handshake frames."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        await node.start()
        
        try:
            # Create a handshake frame
            from seigr_toolset_transmissions.frame import STTFrame
            from seigr_toolset_transmissions.utils.constants import STT_FRAME_TYPE_HANDSHAKE
            
            frame = STTFrame(
                frame_type=STT_FRAME_TYPE_HANDSHAKE,
                session_id=b'\x00' * 8,
                sequence=0,
                stream_id=0,
                payload=b'test handshake data'
            )
            
            peer_addr = ('127.0.0.1', 5000)
            
            # Call handler directly
            node._handle_frame_received(frame, peer_addr)
            
            # Give async task time to execute
            await asyncio.sleep(0.1)
            
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_handle_data_frame_no_session(self, node_seed, shared_seed):
        """Test handling data frame with no session."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        await node.start()
        
        try:
            from seigr_toolset_transmissions.frame import STTFrame
            from seigr_toolset_transmissions.utils.constants import STT_FRAME_TYPE_DATA
            
            # Create data frame with non-existent session
            frame = STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                session_id=b'\xFF' * 8,
                sequence=0,
                stream_id=1,
                payload=b'test data'
            )
            
            peer_addr = ('127.0.0.1', 5000)
            
            # Should handle gracefully
            node._handle_frame_received(frame, peer_addr)
            
            await asyncio.sleep(0.1)
            
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_handle_data_frame_with_session(self, node_seed, shared_seed):
        """Test handling data frame with valid session."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        await node.start()
        
        try:
            from seigr_toolset_transmissions.frame import STTFrame
            from seigr_toolset_transmissions.utils.constants import STT_FRAME_TYPE_DATA
            
            # Create a session first
            session_id = b'\x01' * 8
            _session = await node.session_manager.create_session(
                session_id=session_id,
                peer_node_id=b'\x02' * 32
            )  # Session created for frame handling
            
            # Create data frame
            frame = STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                session_id=session_id,
                sequence=0,
                stream_id=1,
                payload=b'test data'
            )
            
            peer_addr = ('127.0.0.1', 5000)
            
            # Handle frame
            node._handle_frame_received(frame, peer_addr)
            
            await asyncio.sleep(0.1)
            
            # Check receive queue has data
            assert not node._recv_queue.empty()
            
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_receive_generator(self, node_seed, shared_seed):
        """Test receive generator."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        await node.start()
        
        try:
            # Put test packet in queue
            test_packet = ReceivedPacket(
                session_id=b'\x01' * 8,
                stream_id=1,
                data=b"test data"
            )
            await node._recv_queue.put(test_packet)
            
            # Receive one packet
            received = False
            async for packet in node.receive():
                assert packet.session_id == test_packet.session_id
                assert packet.stream_id == test_packet.stream_id
                assert packet.data == test_packet.data
                received = True
                break
            
            assert received
            
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_handle_unknown_frame_type(self, node_seed, shared_seed):
        """Test handling unknown frame type."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        await node.start()
        
        try:
            from seigr_toolset_transmissions.frame import STTFrame
            
            # Create frame with unknown type
            frame = STTFrame(
                frame_type=99,  # Unknown type
                session_id=b'\x00' * 8,
                sequence=0,
                stream_id=0,
                payload=b'test'
            )
            
            peer_addr = ('127.0.0.1', 5000)
            
            # Should handle gracefully (log warning)
            node._handle_frame_received(frame, peer_addr)
            
            await asyncio.sleep(0.1)
            
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_node_with_background_tasks(self, node_seed, shared_seed):
        """Test node with background tasks gets cancelled on stop."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        await node.start()
        
        # Add a background task
        async def background_task():
            while True:
                await asyncio.sleep(1)
        
        task = asyncio.create_task(background_task())
        node._tasks.append(task)
        
        # Stop should cancel tasks
        await node.stop()
        
        assert task.cancelled() or task.done()
    
    @pytest.mark.asyncio
    async def test_node_stop_with_websockets(self, node_seed, shared_seed):
        """Test stopping node with active WebSocket connections."""
        from unittest.mock import AsyncMock, MagicMock
        
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            storage=None
        )
        
        await node.start()
        
        # Add mock WebSocket connection
        mock_ws = MagicMock()
        mock_ws.close = AsyncMock()
        node.ws_connections["test_ws"] = mock_ws
        
        # Stop should close WebSocket
        await node.stop()
        
        # Verify WebSocket was closed
        mock_ws.close.assert_called_once()
        assert len(node.ws_connections) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
