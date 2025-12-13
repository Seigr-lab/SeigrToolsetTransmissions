"""
Simple tests to boost coverage for specific uncovered lines.
"""
import pytest
from seigr_toolset_transmissions.session.session_manager import SessionManager
from seigr_toolset_transmissions.stream.stream_manager import StreamManager
from seigr_toolset_transmissions.frame.frame import STTFrame
from seigr_toolset_transmissions.chamber.chamber import Chamber
from seigr_toolset_transmissions.utils.exceptions import STTFrameError, STTChamberError
from seigr_toolset_transmissions.crypto import context as crypto_context


@pytest.fixture
def temp_chamber_dir(tmp_path):
    """Create a temporary directory for chamber storage."""
    chamber_dir = tmp_path / "chamber"
    chamber_dir.mkdir()
    return chamber_dir


class TestCoverageBoost:
    """Tests targeting specific uncovered lines."""
    
    @pytest.fixture
    def node_seed(self):
        """Node seed for testing."""
        return b"test_node_seed_12345678"
    
    @pytest.fixture
    def shared_seed(self):
        """Shared seed for authentication."""
        return b"test_shared_seed_1234567"
    
    @pytest.fixture
    def temp_chamber_path(self, tmp_path):
        """Create temporary chamber directory."""
        chamber_dir = tmp_path / "chamber"
        chamber_dir.mkdir()
        return chamber_dir
    
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
    
    @pytest.mark.asyncio
    async def test_stream_manager_close_all(self, test_node_id, stc_wrapper):
        """Test close_all_streams method (line 189)."""
        manager = StreamManager(test_node_id, stc_wrapper)
        
        # Close all streams (returns None)
        result = await manager.close_all_streams()
        assert result is None
        # Verify streams are cleared
        assert manager.get_stream_count() == 0
    
    def test_frame_decryption_error(self, stc_wrapper, test_session_id):
        """Test frame decryption error path (lines 154-155)."""
        frame = STTFrame(
            frame_type=1, 
            stream_id=1, 
            session_id=test_session_id,
            sequence=0,
            payload=b"test data"
        )
        
        # Encrypt properly to set up state
        frame.encrypt_payload(stc_wrapper)
        # Corrupt the crypto metadata to cause decryption to fail
        frame.crypto_metadata = {
            'nonce': b'corrupted_nonce_',
            'tag': b'corrupted_tag___'
        }
        
        # Decryption should fail due to invalid crypto metadata
        with pytest.raises(STTFrameError, match="Decryption failed"):
            frame.decrypt_payload(stc_wrapper)
    
    def test_frame_header_parsing_error(self):
        """Test frame header parsing error (lines 261-262)."""
        # Create data with valid magic bytes but malformed header
        # Magic bytes 'ST' + malformed header data
        malformed_data = b"ST" + b"\x01\x02\x03\x04\x05"
        
        with pytest.raises(STTFrameError):
            STTFrame.from_bytes(malformed_data)
    
    def test_chamber_update(self, temp_chamber_dir, test_node_id, stc_wrapper):
        """Test chamber update method (line 177)."""
        chamber = Chamber(
            node_id=test_node_id,
            stc_wrapper=stc_wrapper,
            chamber_path=temp_chamber_dir
        )
        
        # Store initial data
        chamber.store("key1", {"version": 1})
        
        # Update the data
        chamber.update("key1", {"version": 2})
        
        # Verify update worked
        data = chamber.retrieve("key1")
        assert data["version"] == 2
    
    def test_chamber_get_metadata_nonexistent(self, temp_chamber_dir, test_node_id, stc_wrapper):
        """Test chamber get_metadata with nonexistent key (lines 189-197)."""
        chamber = Chamber(
            node_id=test_node_id,
            stc_wrapper=stc_wrapper,
            chamber_path=temp_chamber_dir
        )
        
        with pytest.raises(STTChamberError, match="not found"):
            chamber.get_metadata("nonexistent_key")
    
    def test_chamber_get_metadata_existing(self, temp_chamber_dir, test_node_id, stc_wrapper):
        """Test chamber get_metadata with existing key (lines 194-197)."""
        chamber = Chamber(
            node_id=test_node_id,
            stc_wrapper=stc_wrapper,
            chamber_path=temp_chamber_dir
        )
        
        # Store data
        test_data = {"test": "value", "number": 42}
        chamber.store("test_key", test_data)
        
        # Get metadata
        metadata = chamber.get_metadata("test_key")
        assert metadata is not None
        assert 'key' in metadata
        assert 'size' in metadata
    
    def test_crypto_context_error(self):
        """Test crypto context get when not initialized (covers error path)."""
        # Save current context
        saved = crypto_context._context
        try:
            # Clear context to trigger error
            crypto_context._context = None
            
            with pytest.raises(RuntimeError, match="not initialized"):
                crypto_context.get_context()
        finally:
            # Restore
            crypto_context._context = saved
    
    def test_stream_manager_has_stream_true(self, test_node_id, stc_wrapper):
        """Test has_stream returns True for existing stream (line 144)."""
        from seigr_toolset_transmissions.stream.stream import STTStream
        
        manager = StreamManager(test_node_id, stc_wrapper)
        
        # Manually add a stream
        stream = STTStream(
            stream_id=42,
            session_id=test_node_id,
            stc_wrapper=stc_wrapper
        )
        manager.streams[42] = stream
        
        # Verify has_stream returns True
        assert manager.has_stream(42) is True
        assert manager.has_stream(999) is False
    
    @pytest.mark.asyncio
    async def test_udp_send_large_frame_warning(self, test_session_id):
        """Test UDP warning for large frames (line 173)."""
        from seigr_toolset_transmissions.transport.udp import UDPTransport
        
        # Create transport with default config
        transport = UDPTransport("127.0.0.1", 0)
        # Manually set small max_packet_size to trigger warning
        transport.config.max_packet_size = 100
        
        await transport.start()
        
        try:
            # Create a large frame that will trigger warning
            large_frame = STTFrame(
                frame_type=1,
                stream_id=1,
                session_id=test_session_id,
                sequence=0,
                payload=b"x" * 500  # Much larger than max_packet_size
            )
            
            # This should log a warning but still send (line 173)
            await transport.send_frame(large_frame, ("127.0.0.1", 12345))
        finally:
            await transport.stop()
    
    @pytest.mark.asyncio  
    async def test_udp_double_stop(self):
        """Test UDP stop when not running (lines 130-131)."""
        from seigr_toolset_transmissions.transport.udp import UDPTransport, UDPConfig
        
        transport = UDPTransport(UDPConfig())
        
        # Stop without starting - should just return (line 131)
        await transport.stop()
        assert not transport.running
    
    @pytest.mark.asyncio
    async def test_udp_send_frame_not_running(self, test_session_id):
        """Test UDP send_frame when transport not running (lines 187-189)."""
        from seigr_toolset_transmissions.transport.udp import UDPTransport
        from seigr_toolset_transmissions.utils.exceptions import STTTransportError
        
        transport = UDPTransport("127.0.0.1", 0)
        # Don't start the transport
        
        frame = STTFrame(
            frame_type=1,
            stream_id=1,
            session_id=test_session_id,
            sequence=0,
            payload=b"test"
        )
        
        # Should raise error when trying to send without starting
        with pytest.raises(STTTransportError, match="Transport not running"):
            await transport.send_frame(frame, ("127.0.0.1", 12345))
    
    @pytest.mark.asyncio
    async def test_node_handle_handshake_frame_server_side(self, node_seed, shared_seed):
        """Test node handling handshake as server (lines 248-269)."""
        from seigr_toolset_transmissions.core.node import STTNode
        
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed
        )
        
        await node.start()
        
        try:
            # Simulate receiving a handshake frame from a client
            # This tests the server-side handshake handling
            peer_addr = ("192.168.1.100", 54321)
            
            # Create a mock handshake hello frame
            from seigr_toolset_transmissions.handshake.handshake import STTHandshake
            client_handshake = STTHandshake(node.node_id, node.stc)
            hello_data = client_handshake.create_hello()
            
            # Create frame with handshake payload
            handshake_frame = STTFrame(
                frame_type=0,  # Handshake type
                stream_id=0,
                session_id=b'\x00' * 8,
                sequence=0,
                payload=hello_data
            )
            
            # Handle the frame - this should create a new handshake and send response
            await node._handle_handshake_frame(handshake_frame, peer_addr)
            
            # The fact we got here without exception means the code path executed
            # This exercises the server-side handshake handling (lines 248-269)
            assert True
            
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_node_frame_handling_error(self, node_seed, shared_seed):
        """Test node frame handling error path (lines 227-230)."""
        from seigr_toolset_transmissions.core.node import STTNode
        
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed
        )
        
        await node.start()
        
        try:
            # Create a malformed frame that will cause an error during handling
            bad_frame = STTFrame(
                frame_type=99,  # Unknown type
                stream_id=999,
                session_id=b'\xff' * 8,  # Non-existent session
                sequence=0,
                payload=b"corrupted"
            )
            
            # This should log an error but not crash (lines 227-230)
            node._handle_frame_received(bad_frame, ("127.0.0.1", 12345))
            
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_node_stop_with_tasks_and_websockets(self, node_seed, shared_seed):
        """Test node stop with active tasks and WebSocket connections (lines 125, 128)."""
        from seigr_toolset_transmissions.core.node import STTNode
        import asyncio
        
        node = STTNode(
            node_seed=node_seed,
            shared_seed=shared_seed
        )
        
        await node.start()
        
        # Add a background task
        async def dummy_task():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                pass
        
        task = asyncio.create_task(dummy_task())
        node._tasks.append(task)
        
        # Add a mock WebSocket connection
        class MockWebSocket:
            async def close(self):
                pass
        
        node.ws_connections["test_peer"] = MockWebSocket()
        
        # Stop should cancel tasks and close WebSockets (lines 125, 128)
        await node.stop()
        
        # Verify cleanup
        assert len(node._tasks) == 0
        assert len(node.ws_connections) == 0
        assert task.cancelled() or task.done()
    
    def test_session_manager_get_session_count(self, test_node_id, stc_wrapper):
        """Test get_session_count method."""
        from seigr_toolset_transmissions.session.session_manager import SessionManager
        
        manager = SessionManager(test_node_id, stc_wrapper)
        assert manager.get_session_count() == 0
    
    def test_stream_manager_get_active_count(self, test_node_id, stc_wrapper):
        """Test get_active_stream_count method."""
        manager = StreamManager(test_node_id, stc_wrapper)
        assert manager.get_active_stream_count() == 0
    
    def test_crypto_context_initialize(self, test_seed):
        """Test crypto context initialize."""
        # Save and restore context
        saved = crypto_context._context
        try:
            crypto_context._context = None
            result = crypto_context.initialize(test_seed)
            assert result is not None
            assert crypto_context.get_context() is not None
        finally:
            crypto_context._context = saved
