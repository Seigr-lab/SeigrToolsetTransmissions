"""
Tests for native STT binary serialization.
"""

import pytest
from seigr_toolset_transmissions.utils.serialization import STTSerializer
from seigr_toolset_transmissions.utils.exceptions import STTSerializationError


class TestSTTSerializer:
    """Test native STT binary serialization."""
    
    def test_serialize_none(self):
        """Test serializing None."""
        data = None
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized is None
    
    def test_serialize_bool_true(self):
        """Test serializing True."""
        data = True
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized is True
    
    def test_serialize_bool_false(self):
        """Test serializing False."""
        data = False
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized is False
    
    def test_serialize_int_small(self):
        """Test serializing small integer."""
        data = 42
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == 42
    
    def test_serialize_int_large(self):
        """Test serializing large integer."""
        data = 2**63 - 1
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == data
    
    def test_serialize_int_negative(self):
        """Test serializing negative integer."""
        data = -12345
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == -12345
    
    def test_serialize_float(self):
        """Test serializing float."""
        data = 3.14159
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert abs(deserialized - data) < 0.0001
    
    def test_serialize_bytes(self):
        """Test serializing bytes."""
        data = b'\x00\x01\x02\xff\xfe\xfd'
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == data
    
    def test_serialize_string(self):
        """Test serializing string."""
        data = "Hello, STT!"
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == data
    
    def test_serialize_unicode_string(self):
        """Test serializing unicode string."""
        data = "Hello 世界 🌍"
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == data
    
    def test_serialize_list(self):
        """Test serializing list."""
        data = [1, 2, 3, "four", 5.0]
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == data
    
    def test_serialize_nested_list(self):
        """Test serializing nested list."""
        data = [[1, 2], [3, 4], [5, [6, 7]]]
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == data
    
    def test_serialize_dict(self):
        """Test serializing dictionary."""
        data = {"key1": "value1", "key2": 42, "key3": True}
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == data
    
    def test_serialize_nested_dict(self):
        """Test serializing nested dictionary."""
        data = {
            "outer": {
                "inner": {
                    "deep": "value"
                }
            },
            "list": [1, 2, 3]
        }
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == data
    
    def test_serialize_complex_structure(self):
        """Test serializing complex nested structure."""
        data = {
            "session_id": b'\x01\x02\x03\x04',
            "metadata": {
                "type": "handshake",
                "version": 1,
                "flags": [True, False, True],
            },
            "payload": {
                "data": [1, 2, 3],
                "text": "message",
            }
        }
        
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == data
    
    def test_serialize_empty_list(self):
        """Test serializing empty list."""
        data = []
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == []
    
    def test_serialize_empty_dict(self):
        """Test serializing empty dictionary."""
        data = {}
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == {}
    
    def test_serialize_empty_bytes(self):
        """Test serializing empty bytes."""
        data = b''
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == b''
    
    def test_serialize_empty_string(self):
        """Test serializing empty string."""
        data = ""
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == ""
    
    def test_not_json_format(self):
        """Test that output is NOT JSON."""
        data = {"key": "value"}
        serialized = STTSerializer.serialize(data)
        
        # Should NOT be JSON
        assert not serialized.startswith(b'{')
        assert not serialized.startswith(b'[')
    
    def test_not_msgpack_format(self):
        """Test that output is NOT msgpack."""
        data = {"key": "value"}
        serialized = STTSerializer.serialize(data)
        
        # Should NOT be msgpack (which typically starts with 0x80-0x8f for fixmap)
        assert not serialized.startswith(b'\x80')
    
    def test_deterministic_serialization(self):
        """Test that serialization is deterministic."""
        data = {"key1": "value1", "key2": 42}
        
        serialized1 = STTSerializer.serialize(data)
        serialized2 = STTSerializer.serialize(data)
        
        assert serialized1 == serialized2
    
    def test_roundtrip_all_types(self):
        """Test roundtrip for all supported types."""
        data = {
            "none": None,
            "bool_true": True,
            "bool_false": False,
            "int": 42,
            "float": 3.14,
            "bytes": b'\x00\xff',
            "string": "text",
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }
        
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == data
    
    def test_deserialize_invalid_data(self):
        """Test deserializing invalid data."""
        with pytest.raises(STTSerializationError):
            STTSerializer.deserialize(b'\xff\xff\xff\xff')
    
    def test_deserialize_truncated_data(self):
        """Test deserializing truncated data."""
        data = {"key": "value"}
        serialized = STTSerializer.serialize(data)
        
        # Truncate
        truncated = serialized[:len(serialized) // 2]
        
        with pytest.raises(STTSerializationError):
            STTSerializer.deserialize(truncated)
    
    def test_serialize_large_data(self):
        """Test serializing large data."""
        data = {
            "large_list": list(range(10000)),
            "large_string": "x" * 100000,
            "large_bytes": b'y' * 100000,
        }
        
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == data
    
    def test_serialize_deeply_nested(self):
        """Test serializing deeply nested structure."""
        data = {"level": 1}
        current = data
        
        # Create 50 levels of nesting
        for i in range(2, 51):
            current["nested"] = {"level": i}
            current = current["nested"]
        
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        
        assert deserialized == data
    
    def test_binary_format_efficiency(self):
        """Test that binary format is reasonably efficient."""
        data = {"key": "value"}
        
        serialized = STTSerializer.serialize(data)
        
        # Binary should be compact (reasonable overhead)
        # This is a sanity check, not a strict requirement
        assert len(serialized) < 100  # Should be much less than this
    
    def test_preserve_type_distinction(self):
        """Test that types are preserved correctly."""
        # These should NOT be equal after deserialization
        int_data = 42
        float_data = 42.0
        string_data = "42"
        bytes_data = b'42'
        
        int_result = STTSerializer.deserialize(STTSerializer.serialize(int_data))
        float_result = STTSerializer.deserialize(STTSerializer.serialize(float_data))
        string_result = STTSerializer.deserialize(STTSerializer.serialize(string_data))
        bytes_result = STTSerializer.deserialize(STTSerializer.serialize(bytes_data))
        
        assert isinstance(int_result, int)
        assert isinstance(float_result, float)
        assert isinstance(string_result, str)
        assert isinstance(bytes_result, bytes)
        
        assert int_result == 42
        assert float_result == 42.0
        assert string_result == "42"
        assert bytes_result == b'42'
