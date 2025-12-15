"""
STT native binary serialization format.

Self-sovereign binary encoding using STC's TLV (Type-Length-Value) format.
Replaces JSON, msgpack, and other third-party serialization.
"""

from typing import Any
from enum import IntEnum
import struct

from ..utils.exceptions import STTSerializationError
from ..utils.logging import get_logger


logger = get_logger(__name__)


class STTType(IntEnum):
    """STT data type tags."""
    NULL = 0x00
    BOOL_FALSE = 0x01
    BOOL_TRUE = 0x02
    INT8 = 0x10
    INT16 = 0x11
    INT32 = 0x12
    INT64 = 0x13
    UINT8 = 0x14
    UINT16 = 0x15
    UINT32 = 0x16
    UINT64 = 0x17
    FLOAT32 = 0x20
    FLOAT64 = 0x21
    BYTES = 0x30
    STRING = 0x31
    LIST = 0x40
    DICT = 0x41


class STTSerializer:
    """
    Native STT binary serialization.
    
    Uses TLV encoding similar to STC's internal format.
    All data is self-describing and deterministic.
    """
    
    @staticmethod
    def serialize(value: Any) -> bytes:
        """
        Serialize Python value to STT binary format.
        
        Args:
            value: Value to serialize
            
        Returns:
            Serialized bytes
            
        Raises:
            STTSerializationError: If value cannot be serialized
        """
        if value is None:
            return bytes([STTType.NULL])
        
        elif isinstance(value, bool):
            return bytes([STTType.BOOL_TRUE if value else STTType.BOOL_FALSE])
        
        elif isinstance(value, int):
            return STTSerializer._serialize_int(value)
        
        elif isinstance(value, float):
            return STTSerializer._serialize_float(value)
        
        elif isinstance(value, bytes):
            return STTSerializer._serialize_bytes(value)
        
        elif isinstance(value, str):
            return STTSerializer._serialize_string(value)
        
        elif isinstance(value, list):
            return STTSerializer._serialize_list(value)
        
        elif isinstance(value, dict):
            return STTSerializer._serialize_dict(value)
        
        else:
            raise STTSerializationError(f"Cannot serialize type {type(value)}")
    
    @staticmethod
    def deserialize(data: bytes) -> Any:
        """
        Deserialize STT binary format to Python value.
        
        Args:
            data: Serialized bytes
            
        Returns:
            Deserialized value
            
        Raises:
            STTSerializationError: If data is invalid
        """
        if len(data) == 0:
            raise STTSerializationError("Empty data")
        
        value, _consumed = STTSerializer._deserialize_value(data, 0)
        return value
    
    @staticmethod
    def _serialize_int(value: int) -> bytes:
        """Serialize integer with minimal size."""
        if -128 <= value < 128:
            return bytes([STTType.INT8]) + struct.pack("!b", value)
        elif -32768 <= value < 32768:
            return bytes([STTType.INT16]) + struct.pack("!h", value)
        elif -2147483648 <= value < 2147483648:
            return bytes([STTType.INT32]) + struct.pack("!i", value)
        else:
            return bytes([STTType.INT64]) + struct.pack("!q", value)
    
    @staticmethod
    def _serialize_float(value: float) -> bytes:
        """Serialize float as 64-bit."""
        return bytes([STTType.FLOAT64]) + struct.pack("!d", value)
    
    @staticmethod
    def _serialize_bytes(value: bytes) -> bytes:
        """Serialize bytes with length prefix."""
        length = len(value)
        return bytes([STTType.BYTES]) + struct.pack("!I", length) + value
    
    @staticmethod
    def _serialize_string(value: str) -> bytes:
        """Serialize string as UTF-8 bytes."""
        utf8_bytes = value.encode('utf-8')
        length = len(utf8_bytes)
        return bytes([STTType.STRING]) + struct.pack("!I", length) + utf8_bytes
    
    @staticmethod
    def _serialize_list(value: list) -> bytes:
        """Serialize list with element count."""
        result = bytes([STTType.LIST]) + struct.pack("!I", len(value))
        for item in value:
            result += STTSerializer.serialize(item)
        return result
    
    @staticmethod
    def _serialize_dict(value: dict) -> bytes:
        """Serialize dict with key-value pairs."""
        result = bytes([STTType.DICT]) + struct.pack("!I", len(value))
        
        # Sort keys for deterministic encoding
        for key in sorted(value.keys()):
            # Key must be string
            if not isinstance(key, str):
                raise STTSerializationError("Dict keys must be strings")
            
            result += STTSerializer._serialize_string(key)
            result += STTSerializer.serialize(value[key])
        
        return result
    
    @staticmethod
    def _deserialize_value(data: bytes, offset: int) -> tuple[Any, int]:
        """
        Deserialize single value from data.
        
        Args:
            data: Data bytes
            offset: Current offset
            
        Returns:
            Tuple of (value, new_offset)
        """
        if offset >= len(data):
            raise STTSerializationError("Unexpected end of data")
        
        type_tag = data[offset]
        offset += 1
        
        if type_tag == STTType.NULL:
            return None, offset
        
        elif type_tag == STTType.BOOL_FALSE:
            return False, offset
        
        elif type_tag == STTType.BOOL_TRUE:
            return True, offset
        
        elif type_tag == STTType.INT8:
            value = struct.unpack("!b", data[offset:offset+1])[0]
            return value, offset + 1
        
        elif type_tag == STTType.INT16:
            value = struct.unpack("!h", data[offset:offset+2])[0]
            return value, offset + 2
        
        elif type_tag == STTType.INT32:
            value = struct.unpack("!i", data[offset:offset+4])[0]
            return value, offset + 4
        
        elif type_tag == STTType.INT64:
            value = struct.unpack("!q", data[offset:offset+8])[0]
            return value, offset + 8
        
        elif type_tag == STTType.FLOAT64:
            value = struct.unpack("!d", data[offset:offset+8])[0]
            return value, offset + 8
        
        elif type_tag == STTType.BYTES:
            length = struct.unpack("!I", data[offset:offset+4])[0]
            offset += 4
            value = data[offset:offset+length]
            return bytes(value), offset + length
        
        elif type_tag == STTType.STRING:
            length = struct.unpack("!I", data[offset:offset+4])[0]
            offset += 4
            value = data[offset:offset+length].decode('utf-8')
            return value, offset + length
        
        elif type_tag == STTType.LIST:
            count = struct.unpack("!I", data[offset:offset+4])[0]
            offset += 4
            result = []
            for _ in range(count):
                item, offset = STTSerializer._deserialize_value(data, offset)
                result.append(item)
            return result, offset
        
        elif type_tag == STTType.DICT:
            count = struct.unpack("!I", data[offset:offset+4])[0]
            offset += 4
            result = {}
            for _ in range(count):
                # Read key (must be string)
                key, offset = STTSerializer._deserialize_value(data, offset)
                if not isinstance(key, str):
                    raise STTSerializationError("Dict key must be string")
                
                # Read value
                value, offset = STTSerializer._deserialize_value(data, offset)
                result[key] = value
            
            return result, offset
        
        else:
            raise STTSerializationError(f"Unknown type tag: {type_tag}")


def serialize_stt(value: Any) -> bytes:
    """
    Serialize value to STT binary format.
    
    Convenience function for STTSerializer.serialize().
    
    Args:
        value: Value to serialize
        
    Returns:
        Serialized bytes
    """
    return STTSerializer.serialize(value)


def deserialize_stt(data: bytes) -> Any:
    """
    Deserialize STT binary format to value.
    
    Convenience function for STTSerializer.deserialize().
    
    Args:
        data: Serialized bytes
        
    Returns:
        Deserialized value
    """
    return STTSerializer.deserialize(data)
