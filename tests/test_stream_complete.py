"""Comprehensive stream.py coverage tests."""

import pytest
import asyncio
import time

from seigr_toolset_transmissions.stream.stream import (
    STTStream,
    StreamManager
)
from seigr_toolset_transmissions.crypto import STCWrapper
from seigr_toolset_transmissions.utils.exceptions import STTStreamError


class TestStreamOutOfOrderHandling:
    """Test stream out-of-order message handling."""
    
    @pytest.mark.asyncio
    async def test_handle_incoming_in_order(self):
        """Test handling in-order incoming data."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        stream = STTStream(b'\x11' * 8, 1, stc)
        
        # Send in-order data
        await stream._handle_incoming(b"data1", 0)
        await stream._handle_incoming(b"data2", 1)
        
        # Should be able to receive
        data1 = await stream.receive(timeout=0.1)
        assert data1 == b"data1"
        
        data2 = await stream.receive(timeout=0.1)
        assert data2 == b"data2"
    
    @pytest.mark.asyncio
    async def test_handle_incoming_out_of_order(self):
        """Test handling out-of-order data (future sequence buffered)."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        stream = STTStream(b'\x11' * 8, 1, stc)
        
        # Receive sequence 2 before 0 and 1
        await stream._handle_incoming(b"data2", 2)
        
        # Should be buffered, not delivered yet
        assert 2 in stream.out_of_order_buffer
        assert len(stream.receive_buffer) == 0
        
        # Now receive sequence 0
        await stream._handle_incoming(b"data0", 0)
        
        # Should deliver data0
        data0 = await stream.receive(timeout=0.1)
        assert data0 == b"data0"
        
        # Receive sequence 1
        await stream._handle_incoming(b"data1", 1)
        
        # Should deliver data1 AND data2 (cascading)
        data1 = await stream.receive(timeout=0.1)
        assert data1 == b"data1"
        
        data2 = await stream.receive(timeout=0.1)
        assert data2 == b"data2"
        
        # Out-of-order buffer should be empty now
        assert len(stream.out_of_order_buffer) == 0
    
    @pytest.mark.asyncio
    async def test_handle_incoming_old_sequence_ignored(self):
        """Test old/duplicate sequences are ignored."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        stream = STTStream(b'\x11' * 8, 1, stc)
        
        # Receive in order
        await stream._handle_incoming(b"data0", 0)
        await stream._handle_incoming(b"data1", 1)
        
        # Now try to send old sequence
        await stream._handle_incoming(b"old_data", 0)
        
        # Should only have the original data
        data0 = await stream.receive(timeout=0.1)
        assert data0 == b"data0"
        
        data1 = await stream.receive(timeout=0.1)
        assert data1 == b"data1"
        
        # No more data
        with pytest.raises(STTStreamError, match="Receive timeout"):
            await stream.receive(timeout=0.05)
    
    @pytest.mark.asyncio
    async def test_handle_incoming_when_closed(self):
        """Test handling incoming data when stream is closed."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        stream = STTStream(b'\x11' * 8, 1, stc)
        
        await stream.close()
        
        with pytest.raises(STTStreamError, match="Stream is closed"):
            await stream._handle_incoming(b"data", 0)


class TestStreamReceiveBuffer:
    """Test stream receive buffer operations."""
    
    @pytest.mark.asyncio
    async def test_receive_clears_event_when_empty(self):
        """Test receive clears event when buffer becomes empty."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        stream = STTStream(b'\x11' * 8, 1, stc)
        
        # Add single data item
        stream._deliver_data(b"single")
        
        # Event should be set
        assert stream._receive_event.is_set()
        
        # Receive it
        data = await stream.receive(timeout=0.1)
        assert data == b"single"
        
        # Buffer is now empty, event should be cleared
        assert not stream._receive_event.is_set()
    
    @pytest.mark.asyncio
    async def test_deliver_data_sets_event(self):
        """Test _deliver_data sets the receive event."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        stream = STTStream(b'\x11' * 8, 1, stc)
        
        # Initially clear
        assert not stream._receive_event.is_set()
        
        # Deliver data
        stream._deliver_data(b"test")
        
        # Event should be set
        assert stream._receive_event.is_set()
        assert len(stream.receive_buffer) == 1
    
    @pytest.mark.asyncio
    async def test_receive_returns_empty_when_no_data(self):
        """Test receive returns empty bytes when no data and event not set."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        stream = STTStream(b'\x11' * 8, 1, stc)
        
        # Manually clear event and ensure buffer empty
        stream._receive_event.clear()
        stream.receive_buffer.clear()
        
        # receive() should return empty if wait times out
        # But we need to test the path where event.wait() returns but buffer is empty
        # This can happen in race conditions
        
        # Set event but don't add data
        stream._receive_event.set()
        
        # Should return empty bytes
        data = await stream.receive(timeout=0.1)
        assert data == b''


class TestStreamSendOperations:
    """Test stream send operations."""
    
    @pytest.mark.asyncio
    async def test_send_when_closed(self):
        """Test sending raises error when stream is closed."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        stream = STTStream(b'\x11' * 8, 1, stc)
        
        await stream.close()
        
        with pytest.raises(STTStreamError, match="Stream is closed"):
            await stream.send(b"data")
    
    @pytest.mark.asyncio
    async def test_send_updates_statistics(self):
        """Test send updates bytes_sent and messages_sent."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        stream = STTStream(b'\x11' * 8, 1, stc)
        
        initial_bytes = stream.bytes_sent
        initial_messages = stream.messages_sent
        
        data = b"test_data"
        await stream.send(data)
        
        assert stream.bytes_sent == initial_bytes + len(data)
        assert stream.messages_sent == initial_messages + 1


class TestStreamManagerOperations:
    """Test StreamManager operations."""
    
    @pytest.mark.asyncio
    async def test_create_stream_with_auto_id(self):
        """Test creating stream with auto-assigned ID."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = StreamManager(b'\xAA' * 8, stc)
        
        stream1 = await mgr.create_stream()
        stream2 = await mgr.create_stream()
        
        assert stream1.stream_id == 1
        assert stream2.stream_id == 2
        assert mgr.next_stream_id == 3
    
    @pytest.mark.asyncio
    async def test_create_stream_with_explicit_id(self):
        """Test creating stream with explicit ID."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = StreamManager(b'\xAA' * 8, stc)
        
        stream = await mgr.create_stream(stream_id=99)
        
        assert stream.stream_id == 99
        assert mgr.has_stream(99)
    
    @pytest.mark.asyncio
    async def test_create_stream_duplicate_id_raises_error(self):
        """Test creating stream with duplicate ID raises error."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = StreamManager(b'\xAA' * 8, stc)
        
        await mgr.create_stream(stream_id=10)
        
        with pytest.raises(STTStreamError, match="already exists"):
            await mgr.create_stream(stream_id=10)
    
    def test_get_stream_existing(self):
        """Test getting existing stream."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = StreamManager(b'\xAA' * 8, stc)
        
        stream = STTStream(b'\xAA' * 8, 5, stc)
        mgr.streams[5] = stream
        
        retrieved = mgr.get_stream(5)
        assert retrieved is stream
    
    def test_get_stream_nonexistent(self):
        """Test getting nonexistent stream returns None."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = StreamManager(b'\xAA' * 8, stc)
        
        result = mgr.get_stream(999)
        assert result is None
    
    def test_close_stream(self):
        """Test closing a stream."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = StreamManager(b'\xAA' * 8, stc)
        
        stream = STTStream(b'\xAA' * 8, 3, stc)
        mgr.streams[3] = stream
        
        mgr.close_stream(3)
        
        # close() is async but not awaited in manager, state may not update
        assert not mgr.has_stream(3)
    
    def test_close_nonexistent_stream(self):
        """Test closing nonexistent stream doesn't raise error."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = StreamManager(b'\xAA' * 8, stc)
        
        # Should not raise error
        mgr.close_stream(999)
    
    @pytest.mark.asyncio
    async def test_close_all_streams(self):
        """Test closing all streams."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = StreamManager(b'\xAA' * 8, stc)
        
        # Create multiple streams
        stream1 = await mgr.create_stream()
        stream2 = await mgr.create_stream()
        stream3 = await mgr.create_stream()
        
        await mgr.close_all()
        
        # close() is async but not awaited, just check streams cleared
        assert len(mgr.streams) == 0
    
    def test_list_streams(self):
        """Test listing all stream IDs."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = StreamManager(b'\xAA' * 8, stc)
        
        mgr.streams[1] = STTStream(b'\xAA' * 8, 1, stc)
        mgr.streams[5] = STTStream(b'\xAA' * 8, 5, stc)
        mgr.streams[10] = STTStream(b'\xAA' * 8, 10, stc)
        
        stream_ids = mgr.list_streams()
        
        assert len(stream_ids) == 3
        assert 1 in stream_ids
        assert 5 in stream_ids
        assert 10 in stream_ids


class TestStreamManagerCleanup:
    """Test StreamManager cleanup operations."""
    
    @pytest.mark.asyncio
    async def test_cleanup_inactive_by_status(self):
        """Test cleanup removes inactive streams."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = StreamManager(b'\xAA' * 8, stc)
        
        # Create active and inactive streams
        active = await mgr.create_stream(stream_id=1)
        inactive = await mgr.create_stream(stream_id=2)
        inactive.is_active = False
        
        removed = await mgr.cleanup_inactive(timeout=600)
        
        assert removed == 1
        assert mgr.has_stream(1)
        assert not mgr.has_stream(2)
    
    @pytest.mark.asyncio
    async def test_cleanup_inactive_by_timeout(self):
        """Test cleanup removes streams by timeout."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = StreamManager(b'\xAA' * 8, stc)
        
        # Create stream with old activity
        old_stream = await mgr.create_stream(stream_id=1)
        old_stream.last_activity = time.time() - 1000
        
        # Create recent stream
        recent_stream = await mgr.create_stream(stream_id=2)
        
        removed = await mgr.cleanup_inactive(timeout=500)
        
        assert removed == 1
        assert not mgr.has_stream(1)
        assert mgr.has_stream(2)
    
    @pytest.mark.asyncio
    async def test_cleanup_inactive_no_streams_removed(self):
        """Test cleanup when all streams are active and recent."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = StreamManager(b'\xAA' * 8, stc)
        
        # Create active recent streams
        await mgr.create_stream(stream_id=1)
        await mgr.create_stream(stream_id=2)
        
        removed = await mgr.cleanup_inactive(timeout=600)
        
        assert removed == 0
        assert len(mgr.streams) == 2


class TestStreamStatistics:
    """Test stream statistics tracking."""
    
    @pytest.mark.asyncio
    async def test_incoming_updates_statistics(self):
        """Test _handle_incoming updates bytes_received and messages_received."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        stream = STTStream(b'\x11' * 8, 1, stc)
        
        initial_bytes = stream.bytes_received
        initial_messages = stream.messages_received
        
        data = b"incoming_test_data"
        await stream._handle_incoming(data, 0)
        
        assert stream.bytes_received == initial_bytes + len(data)
        assert stream.messages_received == initial_messages + 1
    
    @pytest.mark.asyncio
    async def test_incoming_updates_last_activity(self):
        """Test _handle_incoming updates last_activity timestamp."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        stream = STTStream(b'\x11' * 8, 1, stc)
        
        initial_activity = stream.last_activity
        
        # Wait a bit
        await asyncio.sleep(0.05)
        
        await stream._handle_incoming(b"data", 0)
        
        assert stream.last_activity > initial_activity


class TestStreamEdgeCases:
    """Test stream edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_multiple_out_of_order_cascade(self):
        """Test multiple out-of-order messages cascade correctly."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        stream = STTStream(b'\x11' * 8, 1, stc)
        
        # Receive 3, 2, 1, 0 (reverse order)
        await stream._handle_incoming(b"data3", 3)
        await stream._handle_incoming(b"data2", 2)
        await stream._handle_incoming(b"data1", 1)
        
        # All should be buffered
        assert len(stream.out_of_order_buffer) == 3
        assert len(stream.receive_buffer) == 0
        
        # Now receive 0
        await stream._handle_incoming(b"data0", 0)
        
        # Should cascade all 4 messages
        assert len(stream.out_of_order_buffer) == 0
        assert len(stream.receive_buffer) == 4
        
        # Verify order
        assert await stream.receive(timeout=0.1) == b"data0"
        assert await stream.receive(timeout=0.1) == b"data1"
        assert await stream.receive(timeout=0.1) == b"data2"
        assert await stream.receive(timeout=0.1) == b"data3"
    
    @pytest.mark.asyncio
    async def test_receive_timeout_behavior(self):
        """Test receive timeout behavior."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        stream = STTStream(b'\x11' * 8, 1, stc)
        
        # No data available
        with pytest.raises(STTStreamError, match="Receive timeout"):
            await stream.receive(timeout=0.05)
    
    @pytest.mark.asyncio
    async def test_stream_close_state(self):
        """Test stream close changes state."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        stream = STTStream(b'\x11' * 8, 1, stc)
        
        assert stream.is_active
        
        await stream.close()
        
        assert not stream.is_active
