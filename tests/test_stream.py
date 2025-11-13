"""
Tests for stream management.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.stream import STTStream, StreamManager
from seigr_toolset_transmissions.utils.constants import (
    STT_STREAM_STATE_IDLE,
    STT_STREAM_STATE_OPEN,
    STT_STREAM_STATE_CLOSED,
)
from seigr_toolset_transmissions.utils.exceptions import (
    STTStreamError,
    STTFlowControlError,
)


class TestSTTStream:
    """Test STT stream."""
    
    @pytest.mark.asyncio
    async def test_stream_creation(self):
        """Test creating a stream."""
        session_id = b'\x01' * 8
        stream = STTStream(stream_id=1, session_id=session_id)
        
        assert stream.stream_id == 1
        assert stream.session_id == session_id
        assert stream.state == STT_STREAM_STATE_IDLE
    
    @pytest.mark.asyncio
    async def test_stream_send(self):
        """Test sending data on stream."""
        session_id = b'\x02' * 8
        stream = STTStream(stream_id=2, session_id=session_id)
        
        data = b'test data'
        await stream.send(data)
        
        assert stream.state == STT_STREAM_STATE_OPEN
        assert stream.bytes_sent == len(data)
        assert stream.chunks_sent == 1
    
    @pytest.mark.asyncio
    async def test_stream_receive(self):
        """Test receiving data from stream."""
        session_id = b'\x03' * 8
        stream = STTStream(stream_id=3, session_id=session_id)
        
        test_data = b'received data'
        await stream.put_received_data(test_data)
        
        received = await stream.receive(timeout=1.0)
        
        assert received == test_data
        assert stream.bytes_received == len(test_data)
    
    @pytest.mark.asyncio
    async def test_stream_flow_control(self):
        """Test flow control."""
        session_id = b'\x04' * 8
        stream = STTStream(stream_id=4, session_id=session_id, send_credit=100)
        
        # Should succeed
        await stream.send(b'a' * 50)
        
        # Should fail - exceeds credit
        with pytest.raises(STTFlowControlError):
            await stream.send(b'b' * 100)
    
    @pytest.mark.asyncio
    async def test_stream_close(self):
        """Test closing stream."""
        session_id = b'\x05' * 8
        stream = STTStream(stream_id=5, session_id=session_id)
        
        await stream.close()
        
        assert stream.state == STT_STREAM_STATE_CLOSED
        assert stream.is_closed()
    
    @pytest.mark.asyncio
    async def test_stream_stats(self):
        """Test getting stream statistics."""
        session_id = b'\x06' * 8
        stream = STTStream(stream_id=6, session_id=session_id)
        
        await stream.send(b'test')
        
        stats = stream.get_stats()
        
        assert stats['stream_id'] == 6
        assert stats['bytes_sent'] > 0
        assert 'send_credit' in stats


class TestStreamManager:
    """Test stream manager."""
    
    @pytest.mark.asyncio
    async def test_create_stream(self):
        """Test creating streams."""
        session_id = b'\x07' * 8
        manager = StreamManager(session_id)
        
        stream = await manager.create_stream()
        
        assert stream is not None
        assert stream.stream_id > 0
    
    @pytest.mark.asyncio
    async def test_get_stream(self):
        """Test getting stream by ID."""
        session_id = b'\x08' * 8
        manager = StreamManager(session_id)
        
        stream = await manager.create_stream()
        retrieved = await manager.get_stream(stream.stream_id)
        
        assert retrieved is stream
    
    @pytest.mark.asyncio
    async def test_close_all_streams(self):
        """Test closing all streams."""
        session_id = b'\x09' * 8
        manager = StreamManager(session_id)
        
        # Create multiple streams
        stream1 = await manager.create_stream()
        stream2 = await manager.create_stream()
        
        await manager.close_all_streams()
        
        assert stream1.is_closed()
        assert stream2.is_closed()
    
    @pytest.mark.asyncio
    async def test_cleanup_closed_streams(self):
        """Test cleaning up closed streams."""
        session_id = b'\x0a' * 8
        manager = StreamManager(session_id)
        
        stream = await manager.create_stream()
        await stream.close()
        
        removed = await manager.cleanup_closed_streams()
        
        assert removed == 1
        assert await manager.get_stream(stream.stream_id) is None
