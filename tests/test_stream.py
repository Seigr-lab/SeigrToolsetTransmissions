"""
Tests for STT stream management.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.stream import STTStream as Stream, StreamManager
from seigr_toolset_transmissions.crypto import STCWrapper
from seigr_toolset_transmissions.utils.exceptions import STTStreamError


class TestStream:
    """Test stream data handling."""
    
    @pytest.fixture
    def session_id(self):
        """Session ID for stream."""
        return b'\x01' * 8
    
    @pytest.fixture
    def stream_id(self):
        """Stream ID."""
        return 1
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper for stream."""
        return STCWrapper(b"stream_seed_32_bytes_minimum!!!")
    
    @pytest.fixture
    def stream(self, session_id, stream_id, stc_wrapper):
        """Create stream instance."""
        return Stream(
            session_id=session_id,
            stream_id=stream_id,
            stc_wrapper=stc_wrapper,
        )
    
    def test_create_stream(self, session_id, stream_id, stc_wrapper):
        """Test creating a stream."""
        stream = Stream(
            session_id=session_id,
            stream_id=stream_id,
            stc_wrapper=stc_wrapper,
        )
        
        assert stream.session_id == session_id
        assert stream.stream_id == stream_id
        assert stream.is_active is True
    
    @pytest.mark.asyncio
    async def test_send_data(self, stream):
        """Test sending data on stream."""
        data = b"test message"
        
        await stream.send(data)
        
        assert stream.bytes_sent > 0
    
    @pytest.mark.asyncio
    async def test_receive_data(self, stream):
        """Test receiving data on stream."""
        data = b"incoming data"
        
        # Simulate receiving data
        await stream._handle_incoming(data, sequence=0)
        
        # Read received data
        received = await stream.receive()
        
        assert received == data
    
    @pytest.mark.asyncio
    async def test_ordered_delivery(self, stream):
        """Test that data is delivered in order."""
        messages = [b"first", b"second", b"third"]
        
        # Send messages
        for msg in messages:
            await stream.send(msg)
        
        # Receive out of order
        await stream._handle_incoming(messages[2], sequence=2)
        await stream._handle_incoming(messages[0], sequence=0)
        await stream._handle_incoming(messages[1], sequence=1)
        
        # Should receive in order
        for expected in messages:
            received = await stream.receive()
            assert received == expected
    
    @pytest.mark.asyncio
    async def test_flow_control(self, stream):
        """Test stream flow control."""
        # Fill up receive window
        large_data = b"x" * 10000
        
        # Send many chunks
        for i in range(100):
            await stream._handle_incoming(large_data, sequence=i)
        
        # Should handle backpressure
        assert stream.receive_window_size > 0
    
    @pytest.mark.asyncio
    async def test_close_stream(self, stream):
        """Test closing a stream."""
        assert stream.is_active is True
        
        await stream.close()
        
        assert stream.is_active is False
    
    @pytest.mark.asyncio
    async def test_send_after_close(self, stream):
        """Test sending after stream is closed."""
        await stream.close()
        
        with pytest.raises(STTStreamError):
            await stream.send(b"data")
    
    @pytest.mark.asyncio
    async def test_stream_statistics(self, stream):
        """Test stream statistics."""
        data = b"test" * 100
        
        await stream.send(data)
        await stream._handle_incoming(data, sequence=0)
        
        stats = stream.get_statistics()
        
        assert stats['bytes_sent'] > 0
        assert stats['bytes_received'] > 0
        assert stats['messages_sent'] >= 1
        assert stats['messages_received'] >= 1
    
    @pytest.mark.asyncio
    async def test_stream_timeout(self, stream):
        """Test stream timeout handling."""
        # Simulate timeout
        stream.last_activity = 0
        
        is_expired = stream.is_expired(max_idle=1)
        
        assert is_expired is True
    
    @pytest.mark.asyncio
    async def test_duplicate_sequence(self, stream):
        """Test handling duplicate sequence numbers."""
        data = b"message"
        
        # Send same sequence twice
        await stream._handle_incoming(data, sequence=0)
        await stream._handle_incoming(data, sequence=0)
        
        # Should only receive once
        received = await stream.receive()
        assert received == data
        
        # No more data
        assert stream.receive_buffer_empty()


class TestStreamManager:
    """Test stream manager for multiple streams."""
    
    @pytest.fixture
    def session_id(self):
        """Session ID for manager."""
        return b'\x01' * 8
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper for manager."""
        return STCWrapper(b"manager_seed_32_bytes_minimum!!")
    
    @pytest.fixture
    def manager(self, session_id, stc_wrapper):
        """Create stream manager."""
        return StreamManager(session_id=session_id, stc_wrapper=stc_wrapper)
    
    @pytest.mark.asyncio
    async def test_create_stream(self, manager):
        """Test creating a stream through manager."""
        stream_id = 1
        
        stream = await manager.create_stream(stream_id)
        
        assert stream is not None
        assert stream.stream_id == stream_id
        assert manager.has_stream(stream_id)
    
    @pytest.mark.asyncio
    async def test_get_stream(self, manager):
        """Test getting a stream."""
        stream_id = 2
        
        # Create stream
        created = await manager.create_stream(stream_id)
        
        # Get stream
        retrieved = manager.get_stream(stream_id)
        
        assert retrieved is created
    
    @pytest.mark.asyncio
    async def test_close_stream(self, manager):
        """Test closing a stream through manager."""
        stream_id = 3
        
        # Create stream
        await manager.create_stream(stream_id)
        
        assert manager.has_stream(stream_id)
        
        # Close stream
        await manager.close_stream(stream_id)
        
        # Stream still exists but is closed
        assert manager.has_stream(stream_id)
        stream = manager.get_stream(stream_id)
        assert stream.is_closed()
        
        # Cleanup removes it
        removed = await manager.cleanup_closed_streams()
        assert removed == 1
        assert not manager.has_stream(stream_id)
    
    @pytest.mark.asyncio
    async def test_multiple_streams(self, manager):
        """Test managing multiple streams."""
        stream_ids = [1, 2, 3, 4, 5]
        
        # Create streams
        for stream_id in stream_ids:
            await manager.create_stream(stream_id)
        
        # Verify all exist
        for stream_id in stream_ids:
            assert manager.has_stream(stream_id)
        
        streams = manager.list_streams()
        assert len(streams) == len(stream_ids)
    
    @pytest.mark.asyncio
    async def test_close_all_streams(self, manager):
        """Test closing all streams."""
        # Create multiple streams
        for i in range(5):
            await manager.create_stream(i)
        
        # Close all
        await manager.close_all()
        
        assert len(manager.list_streams()) == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_inactive_streams(self, manager):
        """Test cleaning up inactive streams."""
        # Create and close stream
        stream_id = 10
        stream = await manager.create_stream(stream_id)
        await stream.close()
        
        # Cleanup
        removed = await manager.cleanup_inactive()
        
        assert removed == 1
        assert not manager.has_stream(stream_id)
    
    @pytest.mark.asyncio
    async def test_get_next_stream_id(self, manager):
        """Test getting next available stream ID."""
        # Get current next ID
        next_id = manager.get_next_stream_id()
        assert next_id == 1  # Initial value
        
        # Create stream - this should increment next_id
        await manager.create_stream()
        
        # Next ID should now be incremented
        new_next_id = manager.get_next_stream_id()
        assert new_next_id > next_id  # Should be 3 (increments by 2)
    
    @pytest.mark.asyncio
    async def test_stream_isolation(self, manager):
        """Test that streams are isolated from each other."""
        stream_1 = await manager.create_stream(1)
        stream_2 = await manager.create_stream(2)
        
        # Send data on stream 1
        await stream_1.send(b"stream 1 data")
        
        # Stream 2 should be empty
        assert stream_2.receive_buffer_empty()
    
    @pytest.mark.asyncio
    async def test_concurrent_stream_operations(self, manager):
        """Test concurrent operations on different streams."""
        async def send_on_stream(stream_id):
            stream = await manager.create_stream(stream_id)
            await stream.send(b"data" * 100)
            return stream.bytes_sent
        
        # Operate on 10 streams concurrently
        results = await asyncio.gather(*[send_on_stream(i) for i in range(10)])
        
        assert all(r > 0 for r in results)
        assert len(manager.list_streams()) == 10
    
    @pytest.mark.asyncio
    async def test_stream_context_isolation(self, session_id):
        """Test that each stream has isolated STC context."""
        # Create two managers with same session
        wrapper1 = STCWrapper(b"wrapper_one_32_bytes_minimum!!")
        wrapper2 = STCWrapper(b"wrapper_two_32_bytes_minimum!!")
        
        manager1 = StreamManager(session_id, wrapper1)
        manager2 = StreamManager(session_id, wrapper2)
        
        stream1 = await manager1.create_stream(1)
        stream2 = await manager2.create_stream(1)
        
        # They should have different contexts
        assert stream1.stc_context != stream2.stc_context
