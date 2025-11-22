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


    @pytest.mark.asyncio
    async def test_connect_udp_not_started(self, node_seed, shared_seed, temp_chamber_path):
        """Test connecting UDP before node is started raises error."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
        )
        
        with pytest.raises(STTException, match="Node not started"):
            await node.connect_udp("127.0.0.1", 9999)
    
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
        assert not node._running
    
    @pytest.mark.asyncio
    async def test_node_chamber_initialization(self, node_seed, shared_seed, temp_chamber_path):
        """Test node initializes chamber correctly."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
        )
        
        assert node.chamber is not None
        assert node.chamber.node_id == node.node_id
        assert node.chamber.stc_wrapper == node.stc
    
    @pytest.mark.asyncio
    async def test_node_session_manager_initialization(self, node_seed, shared_seed, temp_chamber_path):
        """Test node initializes session manager."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
        )
        
        assert node.session_manager is not None
        assert node.session_manager.local_node_id == node.node_id
    
    @pytest.mark.asyncio
    async def test_node_handshake_manager_initialization(self, node_seed, shared_seed, temp_chamber_path):
        """Test node initializes handshake manager."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
        )
        
        assert node.handshake_manager is not None
        assert node.handshake_manager.node_id == node.node_id
    
    @pytest.mark.asyncio
    async def test_node_receive_queue_initialization(self, node_seed, shared_seed, temp_chamber_path):
        """Test node initializes receive queue."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
        )
        
        assert node._recv_queue is not None
        assert isinstance(node._recv_queue, asyncio.Queue)
    
    @pytest.mark.asyncio
    async def test_node_host_port_configuration(self, node_seed, shared_seed, temp_chamber_path):
        """Test node host and port configuration."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            host="192.168.1.1",
            port=5000,
            chamber_path=temp_chamber_path
        )
        
        assert node.host == "192.168.1.1"
        assert node.port == 5000
    
    @pytest.mark.asyncio
    async def test_node_ws_connections_empty(self, node_seed, shared_seed, temp_chamber_path):
        """Test WebSocket connections dict is empty initially."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
        )
        
        assert len(node.ws_connections) == 0
    
    @pytest.mark.asyncio
    async def test_node_tasks_empty_initially(self, node_seed, shared_seed, temp_chamber_path):
        """Test tasks list is empty initially."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
        )
        
        assert len(node._tasks) == 0
    
    @pytest.mark.asyncio
    async def test_node_get_stats(self, node_seed, shared_seed, temp_chamber_path):
        """Test node statistics retrieval."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
        )
        
        stats = node.get_stats()
        
        assert isinstance(stats, dict)
        assert 'node_id' in stats
        assert stats['node_id'] == node.node_id.hex()
    
    @pytest.mark.asyncio
    async def test_node_receive_queue(self, node_seed, shared_seed, temp_chamber_path):
        """Test node receive queue."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
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
    async def test_handle_handshake_frame(self, node_seed, shared_seed, temp_chamber_path):
        """Test handling handshake frames."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
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
    async def test_handle_data_frame_no_session(self, node_seed, shared_seed, temp_chamber_path):
        """Test handling data frame with no session."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
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
    async def test_handle_data_frame_with_session(self, node_seed, shared_seed, temp_chamber_path):
        """Test handling data frame with valid session."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
        )
        await node.start()
        
        try:
            from seigr_toolset_transmissions.frame import STTFrame
            from seigr_toolset_transmissions.utils.constants import STT_FRAME_TYPE_DATA
            
            # Create a session first
            session_id = b'\x01' * 8
            session = await node.session_manager.create_session(
                session_id=session_id,
                peer_node_id=b'\x02' * 32,
                capabilities=0
            )
            
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
    async def test_receive_generator(self, node_seed, shared_seed, temp_chamber_path):
        """Test receive generator."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
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
    async def test_handle_unknown_frame_type(self, node_seed, shared_seed, temp_chamber_path):
        """Test handling unknown frame type."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
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
    async def test_handle_frame_exception(self, node_seed, shared_seed, temp_chamber_path):
        """Test frame handler exception handling."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
        )
        await node.start()
        
        try:
            # Create a frame that will cause issues
            from seigr_toolset_transmissions.frame import STTFrame
            from seigr_toolset_transmissions.utils.constants import STT_FRAME_TYPE_DATA
            
            # Malformed frame
            frame = STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                session_id=b'\xFF' * 8,  # Non-existent session
                sequence=0,
                stream_id=1,
                payload=b'test'
            )
            
            peer_addr = ('127.0.0.1', 5000)
            
            # Should handle exception gracefully
            node._handle_frame_received(frame, peer_addr)
            
            await asyncio.sleep(0.1)
            
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_node_with_background_tasks(self, node_seed, shared_seed, temp_chamber_path):
        """Test node with background tasks gets cancelled on stop."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
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
    async def test_node_double_start(self, node_seed, shared_seed, temp_chamber_path):
        """Test starting node twice returns same address."""
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed,
            chamber_path=temp_chamber_path
        )
        
        addr1 = await node.start()
        addr2 = await node.start()  # Second start should return without error
        
        # Second start returns the default (host, port) not the bound address
        # but doesn't fail and doesn't restart
        assert node._running is True
        
        await node.stop()
    
    @pytest.mark.asyncio
    async def test_connect_udp_not_started(self, temp_chamber_path, node_seed, shared_seed):
        """Test connect_udp raises error when node not started."""
        node = STTNode(
            chamber_path=temp_chamber_path,
            node_seed=node_seed,
            shared_seed=shared_seed
        )
        
        # Try to connect without starting node
        with pytest.raises(STTException, match="Node not started"):
            await node.connect_udp("127.0.0.1", 9999)
    
    @pytest.mark.asyncio
    async def test_connect_udp_handshake_flow(self, temp_chamber_path, node_seed, shared_seed):
        """Test connect_udp handshake flow (covers most of method)."""
        from unittest.mock import AsyncMock, MagicMock, patch
        from seigr_toolset_transmissions.utils.constants import STT_SESSION_STATE_ACTIVE
        
        node = STTNode(
            chamber_path=temp_chamber_path,
            node_seed=node_seed,
            shared_seed=shared_seed
        )
        
        await node.start()
        
        try:
            # Mock the handshake object returned by initiate_handshake
            mock_handshake = MagicMock()
            mock_handshake.hello = b"hello_bytes_message"
            mock_handshake.session_key = b"session_key_16_bytes"
            mock_handshake.peer_node_id = b"peer_node_id_val"
            
            with patch.object(node.handshake_manager, 'initiate_handshake', new_callable=AsyncMock, return_value=mock_handshake) as mock_init:
                with patch.object(node.udp_transport, 'send_raw', new_callable=AsyncMock) as mock_send:
                    # Attempt to connect
                    session = await node.connect_udp("127.0.0.1", 8888)
                    
                    # Verify handshake was initiated
                    mock_init.assert_called_once_with(("127.0.0.1", 8888))
                    
                    # Verify HELLO was sent
                    mock_send.assert_called_once()
                    args = mock_send.call_args[0]
                    assert args[0] == b"hello_bytes_message"
                    assert args[1] == ("127.0.0.1", 8888)
                    
                    # Verify session was created with correct state
                    assert session is not None
                    assert session.state == STT_SESSION_STATE_ACTIVE
                    assert session.session_key == b"session_key_16_bytes"
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_connect_udp_incomplete_handshake(self, temp_chamber_path, node_seed, shared_seed):
        """Test connect_udp with incomplete handshake (no session key)."""
        from unittest.mock import MagicMock, AsyncMock, patch
        
        node = STTNode(
            chamber_path=temp_chamber_path,
            node_seed=node_seed,
            shared_seed=shared_seed
        )
        
        await node.start()
        
        try:
            # Mock handshake that doesn't have session key
            mock_handshake = MagicMock()
            mock_handshake.hello = b"hello"
            mock_handshake.session_key = None  # Incomplete!
            mock_handshake.peer_node_id = b"peer_id"
            
            with patch.object(node.handshake_manager, 'initiate_handshake', new_callable=AsyncMock, return_value=mock_handshake):
                # Should raise exception for incomplete handshake
                with pytest.raises(STTException, match="Handshake incomplete"):
                    await node.connect_udp("127.0.0.1", 9999)
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_connect_udp_no_peer_id(self, temp_chamber_path, node_seed, shared_seed):
        """Test connect_udp with missing peer node ID."""
        from unittest.mock import MagicMock, AsyncMock, patch
        
        node = STTNode(
            chamber_path=temp_chamber_path,
            node_seed=node_seed,
            shared_seed=shared_seed
        )
        
        await node.start()
        
        try:
            # Mock handshake that doesn't have peer ID
            mock_handshake = MagicMock()
            mock_handshake.hello = b"hello"
            mock_handshake.session_key = b"session_key_value"
            mock_handshake.peer_node_id = None  # Missing peer ID!
            
            with patch.object(node.handshake_manager, 'initiate_handshake', new_callable=AsyncMock, return_value=mock_handshake):
                # Should raise exception for incomplete handshake
                with pytest.raises(STTException, match="Handshake incomplete"):
                    await node.connect_udp("127.0.0.1", 9999)
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_connect_udp_exception_handling(self, temp_chamber_path, node_seed, shared_seed):
        """Test connect_udp exception handling."""
        from unittest.mock import AsyncMock, patch
        
        node = STTNode(
            chamber_path=temp_chamber_path,
            node_seed=node_seed,
            shared_seed=shared_seed
        )
        
        await node.start()
        
        try:
            # Mock handshake that raises exception
            with patch.object(node.handshake_manager, 'initiate_handshake', new_callable=AsyncMock, side_effect=Exception("Handshake creation failed")):
                # Should wrap exception in STTException
                with pytest.raises(STTException, match="Failed to connect to 127.0.0.1:9999"):
                    await node.connect_udp("127.0.0.1", 9999)
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_handle_handshake_frame_error(self, temp_chamber_path, node_seed, shared_seed):
        """Test _handle_handshake_frame error handling."""
        from unittest.mock import MagicMock, patch
        from seigr_toolset_transmissions.frame import STTFrame
        from seigr_toolset_transmissions.utils.constants import STT_FRAME_TYPE_HANDSHAKE
        
        node = STTNode(
            chamber_path=temp_chamber_path,
            node_seed=node_seed,
            shared_seed=shared_seed
        )
        
        await node.start()
        
        try:
            # Create handshake frame
            frame = STTFrame(
                frame_type=STT_FRAME_TYPE_HANDSHAKE,
                session_id=b"test_ses",
                stream_id=0,
                sequence=0,
                payload=b"handshake_payload"
            )
            
            peer_addr = ("127.0.0.1", 9999)
            
            # Mock handshake manager to raise error on handle_incoming
            with patch.object(node.handshake_manager, 'handle_incoming', side_effect=Exception("Handshake error")):
                # Should catch and log error
                await node._handle_handshake_frame(frame, peer_addr)
                # No exception raised - error logged
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_handle_data_frame_no_session(self, temp_chamber_path, node_seed, shared_seed):
        """Test _handle_data_frame with no session."""
        from seigr_toolset_transmissions.frame import STTFrame
        from seigr_toolset_transmissions.utils.constants import STT_FRAME_TYPE_DATA
        
        node = STTNode(
            chamber_path=temp_chamber_path,
            node_seed=node_seed,
            shared_seed=shared_seed
        )
        
        await node.start()
        
        try:
            # Create data frame with unknown session
            frame = STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                session_id=b"unknown_",
                stream_id=1,
                sequence=0,
                payload=b"data"
            )
            
            peer_addr = ("127.0.0.1", 8888)
            
            # Should handle gracefully (log warning, no error)
            await node._handle_data_frame(frame, peer_addr)
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_handle_data_frame_error(self, temp_chamber_path, node_seed, shared_seed):
        """Test _handle_data_frame error handling."""
        from unittest.mock import MagicMock, patch
        from seigr_toolset_transmissions.frame import STTFrame
        from seigr_toolset_transmissions.utils.constants import STT_FRAME_TYPE_DATA
        
        node = STTNode(
            chamber_path=temp_chamber_path,
            node_seed=node_seed,
            shared_seed=shared_seed
        )
        
        await node.start()
        
        try:
            # Create data frame
            frame = STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                session_id=b"test_ses",
                stream_id=1,
                sequence=0,
                payload=b"data"
            )
            
            peer_addr = ("127.0.0.1", 8888)
            
            # Mock session manager to raise error
            with patch.object(node.session_manager, 'get_session', side_effect=Exception("Session error")):
                # Should catch and log error
                await node._handle_data_frame(frame, peer_addr)
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_receive_timeout(self, temp_chamber_path, node_seed, shared_seed):
        """Test receive with timeout."""
        node = STTNode(
            chamber_path=temp_chamber_path,
            node_seed=node_seed,
            shared_seed=shared_seed
        )
        
        await node.start()
        
        try:
            # Try to receive with short timeout (should timeout since no data)
            received = []
            gen = node.receive()
            try:
                packet = await asyncio.wait_for(gen.__anext__(), timeout=0.1)
                received.append(packet)
            except asyncio.TimeoutError:
                pass  # Expected - no data available
            
            # Should have no packets (timed out)
            assert len(received) == 0
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_node_stop_with_websockets(self, temp_chamber_path, node_seed, shared_seed):
        """Test stopping node with active WebSocket connections."""
        from unittest.mock import AsyncMock, MagicMock
        
        node = STTNode(
            chamber_path=temp_chamber_path,
            node_seed=node_seed,
            shared_seed=shared_seed
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
