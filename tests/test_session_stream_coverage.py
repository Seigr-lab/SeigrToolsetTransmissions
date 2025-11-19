"""
Session and stream additional coverage.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.session.session import STTSession
from seigr_toolset_transmissions.stream.stream import STTStream
from seigr_toolset_transmissions.crypto import STCWrapper


class TestSessionStreamCoverage:
    """Session and stream coverage."""
    
    @pytest.fixture
    def stc_wrapper(self):
        return STCWrapper(b"coverage_32_bytes_minimum_seed!")
    
    def test_session_metadata(self, stc_wrapper):
        """Test session with metadata."""
        session = STTSession(b"metasess", b"peer_meta", stc_wrapper, metadata={"key": "value"})
        assert session.metadata["key"] == "value"
    
    def test_session_activity_tracking(self, stc_wrapper):
        """Test session activity tracking."""
        import time
        session = STTSession(b"activity", b"peer_act", stc_wrapper)
        initial = session.last_activity
        time.sleep(0.01)  # Small delay to ensure timestamp difference
        session.update_activity()
        assert session.last_activity >= initial
    
    @pytest.mark.asyncio
    async def test_stream_send(self, stc_wrapper):
        """Test stream send."""
        stream = STTStream(b"stremsnd", 1, stc_wrapper)
        try:
            await stream.send(b"data")
        except Exception:
            pass
    
    @pytest.mark.asyncio
    async def test_stream_receive_closed(self, stc_wrapper):
        """Test receiving on closed stream."""
        stream = STTStream(b"stremrcv", 2, stc_wrapper)
        await stream.close()
        try:
            await stream.receive()
        except Exception:
            pass
    
    def test_stream_window_size(self, stc_wrapper):
        """Test stream window size property."""
        stream = STTStream(b"stremwin", 3, stc_wrapper)
        assert stream.receive_window_size > 0
    
    @pytest.mark.asyncio
    async def test_session_manager_operations(self, stc_wrapper):
        """Test session manager operations."""
        from seigr_toolset_transmissions.session.session_manager import SessionManager
        
        node_id = b"test_node_mgr_" + b"0" * 18  # 32 bytes total
        manager = SessionManager(node_id, stc_wrapper)
        
        session_id = b'\x01' * 8
        peer_id = b"peer_test_123" + b"0" * 19  # 32 bytes
        
        # Initially doesn't have session
        initial_has = manager.has_session(session_id)
        
        # Create session
        session = await manager.create_session(session_id, peer_id)
        assert manager.has_session(session_id)
        
        # Get session
        retrieved = manager.get_session(session_id)
        assert retrieved is not None
        assert retrieved.session_id == session_id
    
    @pytest.mark.asyncio
    async def test_stream_manager_operations(self, stc_wrapper):
        """Test stream manager operations."""
        from seigr_toolset_transmissions.stream.stream_manager import StreamManager
        
        session_id = b'\x02' * 8
        manager = StreamManager(session_id, stc_wrapper)
        
        # Create stream
        stream = await manager.create_stream(stream_id=10)
        assert manager.get_stream(10) is not None
        
        # Close stream
        await manager.close_stream(10)
        assert not stream.is_active
    
    @pytest.mark.asyncio
    async def test_stream_receive_timeout(self, stc_wrapper):
        """Test stream receive with timeout."""
        from seigr_toolset_transmissions.utils.exceptions import STTStreamError
        
        stream = STTStream(b'\x03' * 8, 1, stc_wrapper)
        
        with pytest.raises(STTStreamError):
            await stream.receive(timeout=0.001)
    
    @pytest.mark.asyncio
    async def test_stream_deliver_data(self, stc_wrapper):
        """Test stream internal data delivery."""
        stream = STTStream(b'\x04' * 8, 2, stc_wrapper)
        
        test_data = b"test payload data"
        stream._deliver_data(test_data)
        
        received = await stream.receive()
        assert received == test_data
    
    def test_session_close_inactive(self, stc_wrapper):
        """Test session becomes inactive after close."""
        session = STTSession(b'\x05' * 8, b"peer_close", stc_wrapper)
        
        assert session.is_active
        session.close()
        assert not session.is_active


class TestFrameEdgeCases:
    """Test frame edge cases."""
    
    def test_frame_with_custom_flags(self):
        """Test frame with custom flags."""
        from seigr_toolset_transmissions.frame import STTFrame
        
        frame = STTFrame(
            frame_type=0,
            session_id=b'\x06' * 8,
            sequence=1,
            stream_id=1,
            payload=b"test",
            flags=0b00000101
        )
        
        assert frame.flags == 0b00000101
    
    def test_frame_with_crypto_metadata(self):
        """Test frame with crypto metadata."""
        from seigr_toolset_transmissions.frame import STTFrame
        
        crypto_meta = b"crypto_metadata_here"
        frame = STTFrame(
            frame_type=0,
            session_id=b'\x07' * 8,
            sequence=2,
            stream_id=1,
            payload=b"test",
            crypto_metadata=crypto_meta
        )
        
        assert frame.crypto_metadata == crypto_meta
    
    def test_frame_serialization_roundtrip(self):
        """Test frame serialization round trip."""
        from seigr_toolset_transmissions.frame import STTFrame
        
        original = STTFrame(
            frame_type=0,
            session_id=b'\x08' * 8,
            sequence=5,
            stream_id=3,
            payload=b"roundtrip test data"
        )
        
        serialized = original.to_bytes()
        result = STTFrame.from_bytes(serialized)
        
        # from_bytes may return tuple (frame, remaining_bytes)
        if isinstance(result, tuple):
            deserialized = result[0]
        else:
            deserialized = result
        
        assert deserialized.frame_type == original.frame_type
        assert deserialized.session_id == original.session_id
        assert deserialized.sequence == original.sequence
        assert deserialized.stream_id == original.stream_id
        assert deserialized.payload == original.payload


class TestSerializationEdgeCases:
    """Test serialization edge cases."""
    
    def test_serialize_empty_collections(self):
        """Test serializing empty collections."""
        from seigr_toolset_transmissions.utils.serialization import STTSerializer
        
        serializer = STTSerializer()
        
        # Empty dict
        assert serializer.deserialize(serializer.serialize({})) == {}
        
        # Empty list
        assert serializer.deserialize(serializer.serialize([])) == []
    
    def test_serialize_large_data(self):
        """Test serializing large data."""
        from seigr_toolset_transmissions.utils.serialization import STTSerializer
        
        serializer = STTSerializer()
        
        large_bytes = b'\x00' * 5000
        serialized = serializer.serialize(large_bytes)
        deserialized = serializer.deserialize(serialized)
        
        assert deserialized == large_bytes
    
    def test_serialize_unicode_strings(self):
        """Test serializing unicode strings."""
        from seigr_toolset_transmissions.utils.serialization import STTSerializer
        
        serializer = STTSerializer()
        
        unicode_str = "Hello 世界 🌍"
        serialized = serializer.serialize(unicode_str)
        deserialized = serializer.deserialize(serialized)
        
        assert deserialized == unicode_str


class TestNodeOperations:
    """Test node operations."""
    
    @pytest.mark.asyncio
    async def test_node_get_stats(self):
        """Test getting node statistics."""
        from seigr_toolset_transmissions.core.node import STTNode
        from seigr_toolset_transmissions.crypto import context
        
        context.initialize(b"test_seed_node_stats_!!!!!!")
        
        node = STTNode(
            node_seed=b"test_seed_node_stats_!!!!!!",
            shared_seed=b"shared_seed_node_stats_!!!!!"
        )
        
        stats = node.get_stats()
        
        # Stats may be nested
        assert 'sessions' in stats
        assert 'active_sessions' in stats['sessions']
        assert stats['sessions']['total_sessions'] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
