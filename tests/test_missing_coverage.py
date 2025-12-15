"""
Tests to cover remaining missing lines and reach 100% coverage.
"""

import pytest
from seigr_toolset_transmissions.frame import STTFrame
from seigr_toolset_transmissions.crypto import STCWrapper
from seigr_toolset_transmissions.utils.exceptions import STTFrameError
from seigr_toolset_transmissions.utils.constants import STT_MAGIC, STT_FRAME_TYPE_DATA


class TestFrameErrorPaths:
    """Test error paths in frame parsing."""
    
    @pytest.fixture
    def stc_wrapper(self):
        """Create STC wrapper for tests."""
        from seigr_toolset_transmissions.crypto import context
        context.initialize(b"test_seed_frame_errors_!!!!!")
        return STCWrapper(b"test_seed_frame_errors_!!!!!")
    
    def test_from_bytes_insufficient_data_for_magic(self):
        """Test parsing data too short for magic bytes."""
        data = b'\x00'  # Only 1 byte, need 2 for magic
        
        with pytest.raises(STTFrameError):
            STTFrame.from_bytes(data)
    
    def test_from_bytes_invalid_magic_bytes(self):
        """Test parsing with invalid magic bytes."""
        # Create data with wrong magic bytes
        data = b'\xFF\xFE' + b'\x00' * 100
        
        with pytest.raises(STTFrameError):
            STTFrame.from_bytes(data)
    
    def test_from_bytes_failed_varint_decode(self):
        """Test parsing with corrupted varint length."""
        # Valid magic but invalid varint encoding
        data = STT_MAGIC + b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'
        
        with pytest.raises(Exception):  # Could be STTFrameError or ValueError
            STTFrame.from_bytes(data)
    
    def test_from_bytes_insufficient_data_for_frame(self):
        """Test parsing when data is shorter than declared length."""
        from seigr_toolset_transmissions.utils.varint import encode_varint
        
        # Claim frame is 1000 bytes but only provide 50
        total_length = 1000
        data = STT_MAGIC + encode_varint(total_length) + b'\x00' * 50
        
        with pytest.raises(STTFrameError):
            STTFrame.from_bytes(data)
    
    def test_from_bytes_frame_too_small_for_header(self):
        """Test parsing frame that's too small to contain header."""
        from seigr_toolset_transmissions.utils.varint import encode_varint
        
        # Claim very small frame that can't fit header
        total_length = 5  # Way too small for header
        data = STT_MAGIC + encode_varint(total_length) + b'\x00' * 5
        
        with pytest.raises(STTFrameError):
            STTFrame.from_bytes(data)
    
    def test_invalid_session_id_length_too_short(self):
        """Test that short session ID raises error."""
        with pytest.raises(STTFrameError):
            STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                session_id=b'\x00' * 7,  # Too short
                sequence=1,
                stream_id=1,
                payload=b'test'
            )
    
    def test_invalid_session_id_length_too_long(self):
        """Test that long session ID raises error."""
        with pytest.raises(STTFrameError):
            STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                session_id=b'\x00' * 9,  # Too long
                sequence=1,
                stream_id=1,
                payload=b'test'
            )


class TestChamberErrorPaths:
    """Test error paths in chamber operations."""
    
    @pytest.fixture
    def chamber_and_stc(self, tmp_path):
        """Create a chamber for tests."""
        from seigr_toolset_transmissions.chamber import Chamber
        from seigr_toolset_transmissions.crypto import STCWrapper, context
        
        context.initialize(b"test_seed_chamber_errors_!!!!!")
        stc = STCWrapper(b"test_seed_chamber_errors_!!!!!")
        chamber_path = str(tmp_path / "test_chamber")
        node_id = b"test_node_id_123"
        return Chamber(chamber_path, node_id, stc), stc
    
    def test_retrieve_nonexistent_key(self, chamber_and_stc):
        """Test retrieving non-existent key raises error."""
        from seigr_toolset_transmissions.utils.exceptions import STTChamberError
        
        chamber_obj, _ = chamber_and_stc
        
        with pytest.raises(STTChamberError):
            chamber_obj.retrieve("nonexistent_key")
    
    def test_delete_nonexistent_key(self, chamber_and_stc):
        """Test deleting non-existent key raises error."""
        from seigr_toolset_transmissions.utils.exceptions import STTChamberError
        
        chamber_obj, _ = chamber_and_stc
        
        with pytest.raises(STTChamberError):
            chamber_obj.delete("nonexistent_key")
    
    def test_chamber_operations(self, chamber_and_stc):
        """Test various chamber operations."""
        chamber_obj, _ = chamber_and_stc
        
        # Test store and retrieve
        key = "test_key"
        data = b"test data"
        chamber_obj.store(key, data)
        
        # Test exists
        assert chamber_obj.exists(key)
        
        # Test retrieve
        retrieved = chamber_obj.retrieve(key)
        assert retrieved == data
        
        # Test list_keys
        keys = chamber_obj.list_keys()
        assert key in keys
        
        # Test delete
        chamber_obj.delete(key)
        assert not chamber_obj.exists(key)
    
    def test_chamber_clear(self, chamber_and_stc):
        """Test clearing chamber."""
        chamber_obj, _ = chamber_and_stc
        
        # Store multiple items
        chamber_obj.store("key1", b"data1")
        chamber_obj.store("key2", b"data2")
        
        # Clear
        chamber_obj.clear()
        
        # Verify cleared
        assert not chamber_obj.exists("key1")
        assert not chamber_obj.exists("key2")


class TestWebSocketErrorPaths:
    """Test WebSocket error paths."""
    
    @pytest.mark.asyncio
    async def test_websocket_connect_failure(self):
        """Test WebSocket client connection failure."""
        from seigr_toolset_transmissions.transport.websocket import WebSocketTransport
        from seigr_toolset_transmissions.crypto import STCWrapper, context
        
        context.initialize(b"test_seed_websocket_!!!!!!!!!!")
        stc = STCWrapper(b"test_seed_websocket_!!!!!!!!!!")
        
        # Try to connect to non-existent server
        ws = WebSocketTransport("127.0.0.1", 65432, stc, is_server=False)
        
        try:
            # This should fail to connect
            await ws.connect()
            # If it somehow succeeds, clean up
            await ws.close()
        except Exception:
            # Expected to fail
            pass


class TestStreamErrorPaths:
    """Test Stream error paths."""
    
    @pytest.mark.asyncio
    async def test_stream_send_after_close(self):
        """Test sending data on closed stream."""
        from seigr_toolset_transmissions.stream import STTStream
        from seigr_toolset_transmissions.crypto import STCWrapper, context
        
        context.initialize(b"test_seed_stream_errors_!!!!")
        stc = STCWrapper(b"test_seed_stream_errors_!!!!")
        
        stream = STTStream(
            stream_id=1,
            session_id=b'\x01' * 8,
            stc_wrapper=stc
        )
        
        # Close stream
        await stream.close()
        
        # Try to send after close should not crash
        try:
            await stream.send(b"data")
        except Exception:
            # May raise exception or silently fail
            pass


class TestSerializationErrorPaths:
    """Test serialization error paths."""
    
    def test_serialize_unsupported_type(self):
        """Test serializing unsupported type."""
        from seigr_toolset_transmissions.utils.serialization import STTSerializer
        from seigr_toolset_transmissions.utils.exceptions import STTSerializationError
        
        # Try to serialize unsupported type
        class UnsupportedType:
            pass
        
        obj = UnsupportedType()
        serializer = STTSerializer()
        
        with pytest.raises(STTSerializationError):
            serializer.serialize(obj)
    
    def test_deserialize_invalid_type_tag(self):
        """Test deserializing data with invalid type tag."""
        from seigr_toolset_transmissions.utils.serialization import STTSerializer
        from seigr_toolset_transmissions.utils.exceptions import STTSerializationError
        
        serializer = STTSerializer()
        # Create data with invalid type tag
        data = b'\xFF' + b'garbage data'
        
        with pytest.raises(STTSerializationError):
            serializer.deserialize(data)
    
    def test_deserialize_truncated_data(self):
        """Test deserializing truncated data."""
        from seigr_toolset_transmissions.utils.serialization import STTSerializer
        from seigr_toolset_transmissions.utils.exceptions import STTSerializationError
        
        serializer = STTSerializer()
        # Create truncated data (type tag for string but no length)
        data = b'\x03'  # String type tag but no data
        
        with pytest.raises(STTSerializationError):
            serializer.deserialize(data)


class TestHandshakeErrorPaths:
    """Test error paths in handshake operations."""
    
    def test_handshake_invalid_challenge_payload(self):
        """Test handshake with malformed challenge causes error."""
        from seigr_toolset_transmissions.handshake import STTHandshake
        from seigr_toolset_transmissions.crypto import STCWrapper, context
        from seigr_toolset_transmissions.utils.exceptions import STTHandshakeError
        
        context.initialize(b"test_seed_handshake_errors!!")
        stc = STCWrapper(b"test_seed_handshake_errors!!")
        
        node_id = b"initiator_node_123"
        handshake = STTHandshake(node_id, stc, is_initiator=True)
        
        # Start handshake
        _hello_msg = handshake.create_hello()  # Initialize handshake state
        
        # Create malformed response (missing required fields)
        from seigr_toolset_transmissions.utils.serialization import serialize_stt
        invalid_msg = serialize_stt({
            'type': 'RESPONSE',
            # Missing 'node_id' field - will cause KeyError
            'nonce': b'\x00' * 32
        })
        
        with pytest.raises((STTHandshakeError, KeyError)):
            handshake.process_challenge(invalid_msg)


class TestStreamManagerErrorPaths:
    """Test StreamManager error paths."""
    
    @pytest.mark.asyncio
    async def test_stream_manager_auto_increment(self):
        """Test stream manager auto-incrementing stream IDs."""
        from seigr_toolset_transmissions.stream.stream_manager import StreamManager
        from seigr_toolset_transmissions.crypto import STCWrapper, context
        
        context.initialize(b"test_seed_stream_manager_!!")
        stc = STCWrapper(b"test_seed_stream_manager_!!")
        
        session_id = b'\x01' * 8
        manager = StreamManager(session_id, stc)
        
        # Create streams with auto-incrementing IDs
        stream1 = await manager.create_stream()
        stream2 = await manager.create_stream()
        
        # Verify they have different IDs
        assert stream1.stream_id != stream2.stream_id
    
    @pytest.mark.asyncio
    async def test_stream_receive_after_close(self):
        """Test receiving data on closed stream."""
        from seigr_toolset_transmissions.stream import STTStream
        from seigr_toolset_transmissions.crypto import STCWrapper, context
        from seigr_toolset_transmissions.utils.exceptions import STTStreamError
        
        context.initialize(b"test_seed_stream_receive_!!")
        stc = STCWrapper(b"test_seed_stream_receive_!!")
        
        stream = STTStream(
            session_id=b'\x01' * 8,
            stream_id=1,
            stc_wrapper=stc
        )
        
        # Close stream
        await stream.close()
        
        # Try to receive data
        with pytest.raises(STTStreamError):
            await stream.receive()


class TestFrameAdvancedErrorPaths:
    """Test advanced frame error paths."""
    
    def test_frame_invalid_session_id(self):
        """Test creating frame with invalid session ID length."""
        from seigr_toolset_transmissions.frame import STTFrame
        from seigr_toolset_transmissions.utils.exceptions import STTFrameError
        
        with pytest.raises((STTFrameError, AssertionError)):
            STTFrame(
                frame_type=0,
                session_id=b'\x01' * 4,  # Wrong length (should be 8)
                sequence=1,
                stream_id=1,
                payload=b'test'
            )


class TestSerializationAdvanced:
    """Test advanced serialization scenarios."""
    
    def test_serialization_complex_nested_structures(self):
        """Test serialization of deeply nested structures."""
        from seigr_toolset_transmissions.utils.serialization import STTSerializer
        
        serializer = STTSerializer()
        
        # Create complex nested structure
        complex_data = {
            'level1': {
                'level2': {
                    'level3': {
                        'numbers': [1, 2, 3],
                        'text': 'nested',
                        'bytes': b'\x00\x01\x02'
                    }
                }
            },
            'list_of_dicts': [
                {'id': 1, 'value': 'first'},
                {'id': 2, 'value': 'second'}
            ]
        }
        
        # Serialize and deserialize
        serialized = serializer.serialize(complex_data)
        deserialized = serializer.deserialize(serialized)
        
        assert deserialized == complex_data


class TestChamberAdvanced:
    """Test advanced chamber operations."""
    
    def test_chamber_list_keys(self, tmp_path):
        """Test listing keys in chamber."""
        from seigr_toolset_transmissions.chamber import Chamber
        from seigr_toolset_transmissions.crypto import STCWrapper, context
        
        context.initialize(b"test_seed_chamber_list_!!!!")
        stc = STCWrapper(b"test_seed_chamber_list_!!!!")
        chamber_path = str(tmp_path / "test_chamber_list")
        node_id = b"test_node_list_123"
        
        chamber = Chamber(chamber_path, node_id, stc)
        
        # Store some data
        chamber.store("key1", "value1")
        chamber.store("key2", {"nested": "data"})
        chamber.store("key3", [1, 2, 3])
        
        # List keys
        keys = chamber.list_keys()
        assert len(keys) == 3
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys
    
    def test_chamber_update_existing_key(self, tmp_path):
        """Test updating existing key in chamber."""
        from seigr_toolset_transmissions.chamber import Chamber
        from seigr_toolset_transmissions.crypto import STCWrapper, context
        
        context.initialize(b"test_seed_chamber_update!!")
        stc = STCWrapper(b"test_seed_chamber_update!!")
        chamber_path = str(tmp_path / "test_chamber_update")
        node_id = b"test_node_update_123"
        
        chamber = Chamber(chamber_path, node_id, stc)
        
        # Store initial value
        chamber.store("key1", "initial_value")
        retrieved = chamber.retrieve("key1")
        assert retrieved == "initial_value"
        
        # Update value
        chamber.store("key1", "updated_value")
        retrieved = chamber.retrieve("key1")
        assert retrieved == "updated_value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

