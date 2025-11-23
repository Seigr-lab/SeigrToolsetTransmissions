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
    
    def test_deserialize_invalid_type_tag(self):
        """Test deserializing data with invalid type tag."""
        # Create data with invalid type tag (999)
        invalid_data = b'\x03\xe7'  # Type tag 999
        with pytest.raises(STTSerializationError, match="Unknown type tag"):
            STTSerializer.deserialize(invalid_data)
    
    def test_deserialize_truncated_int(self):
        """Test deserializing truncated integer data."""
        # INT32 type but not enough bytes
        truncated = b'\x05\x00\x01'  # Type tag INT32 but only 2 bytes
        with pytest.raises((STTSerializationError, ValueError)):
            STTSerializer.deserialize(truncated)
    
    def test_deserialize_truncated_string(self):
        """Test deserializing truncated string data."""
        # STRING type with length but missing data
        truncated = b'\x08\x00\x00\x00\x0a'  # Claims 10 bytes but none follow
        with pytest.raises((STTSerializationError, ValueError, IndexError)):
            STTSerializer.deserialize(truncated)
    
    def test_deserialize_truncated_bytes(self):
        """Test deserializing truncated bytes data."""
        # BYTES type with length but missing data
        truncated = b'\x07\x00\x00\x00\x05ab'  # Claims 5 bytes but only 2
        with pytest.raises((STTSerializationError, ValueError, IndexError)):
            STTSerializer.deserialize(truncated)
    
    def test_deserialize_invalid_utf8_string(self):
        """Test deserializing invalid UTF-8 in string."""
        # STRING with invalid UTF-8 sequence
        invalid_utf8 = b'\x08\x00\x00\x00\x02\xff\xfe'
        with pytest.raises((STTSerializationError, UnicodeDecodeError)):
            STTSerializer.deserialize(invalid_utf8)
    
    def test_deserialize_empty_data(self):
        """Test deserializing empty data."""
        with pytest.raises((STTSerializationError, ValueError, IndexError)):
            STTSerializer.deserialize(b'')
    
    def test_serialize_unsupported_type(self):
        """Test serializing unsupported type raises error."""
        class CustomClass:
            pass
        
        with pytest.raises(STTSerializationError):
            STTSerializer.serialize(CustomClass())
    
    def test_deserialize_truncated_list(self):
        """Test deserializing list with truncated count."""
        # LIST type but truncated count
        truncated = b'\x09\x00\x00'  # Type tag LIST but incomplete count
        with pytest.raises((STTSerializationError, ValueError)):
            STTSerializer.deserialize(truncated)
    
    def test_deserialize_list_truncated_items(self):
        """Test deserializing list with missing items."""
        # LIST claiming 2 items but only 1 present
        truncated = b'\x09\x00\x00\x00\x02\x00'  # Claims 2 items, has NULL, missing item 2
        with pytest.raises((STTSerializationError, ValueError, IndexError)):
            STTSerializer.deserialize(truncated)
    
    def test_deserialize_truncated_dict(self):
        """Test deserializing dict with truncated data."""
        # DICT type but truncated count
        truncated = b'\x0a\x00\x00'  # Type tag DICT but incomplete count
        with pytest.raises((STTSerializationError, ValueError)):
            STTSerializer.deserialize(truncated)
    
    def test_deserialize_dict_truncated_items(self):
        """Test deserializing dict with missing items."""
        # DICT claiming 1 item but incomplete key/value
        truncated = b'\x0a\x00\x00\x00\x01\x08\x00\x00\x00\x03key'  # Has key but no value
        with pytest.raises((STTSerializationError, ValueError, IndexError)):
            STTSerializer.deserialize(truncated)
    
    def test_serialize_dict_non_string_keys(self):
        """Test serializing dict with non-string keys."""
        # STT requires string keys for dicts
        data = {42: "value"}
        with pytest.raises(STTSerializationError):
            STTSerializer.serialize(data)
    
    def test_deserialize_dict_non_string_key(self):
        """Test deserializing dict with non-string key in data."""
        # Manually construct data: valid DICT with INT key (should fail)
        import struct
        
        # DICT tag (0x41), count=1
        data = b'\x41'  # DICT type
        data += struct.pack("!I", 1)  # count = 1
        # Add INT key (invalid - should be STRING)
        data += b'\x10'  # INT8 type (0x10)
        data += struct.pack("!b", 42)  # value = 42
        # Add STRING value
        data += b'\x31'  # STRING type (0x31)
        data += struct.pack("!I", 5)  # length = 5
        data += b'value'
        
        with pytest.raises(STTSerializationError, match="Dict key must be string"):
            STTSerializer.deserialize(data)
    
    def test_serialize_extreme_nesting(self):
        """Test serializing extremely nested structure."""
        # Create 100+ levels of nesting
        data = {"level": 1}
        current = data
        for i in range(2, 101):
            current["nested"] = {"level": i}
            current = current["nested"]
        
        serialized = STTSerializer.serialize(data)
        deserialized = STTSerializer.deserialize(serialized)
        assert deserialized == data
    
    def test_serialize_large_integers(self):
        """Test serializing very large integers."""
        large_int = 2**50
        serialized = STTSerializer.serialize(large_int)
        deserialized = STTSerializer.deserialize(serialized)
        assert deserialized == large_int
    
    def test_serialize_negative_integers(self):
        """Test serializing negative integers."""
        neg_vals = [-1, -127, -128, -32768, -2147483648]
        for val in neg_vals:
            serialized = STTSerializer.serialize(val)
            deserialized = STTSerializer.deserialize(serialized)
            assert deserialized == val
    
    def test_serialize_special_floats(self):
        """Test serializing special float values."""
        import math
        
        # Test infinity
        inf_serialized = STTSerializer.serialize(math.inf)
        inf_deserialized = STTSerializer.deserialize(inf_serialized)
        assert math.isinf(inf_deserialized)
        
        # Test negative infinity
        neginf_serialized = STTSerializer.serialize(-math.inf)
        neginf_deserialized = STTSerializer.deserialize(neginf_serialized)
        assert math.isinf(neginf_deserialized) and neginf_deserialized < 0
        
        # Test NaN
        nan_serialized = STTSerializer.serialize(math.nan)
        nan_deserialized = STTSerializer.deserialize(nan_serialized)
        assert math.isnan(nan_deserialized)
