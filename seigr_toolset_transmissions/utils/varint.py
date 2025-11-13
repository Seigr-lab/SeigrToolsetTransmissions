"""
Variable-length integer encoding/decoding for STT frames.
"""

from typing import Tuple


def encode_varint(value: int) -> bytes:
    """
    Encode an integer as a variable-length byte sequence.
    
    Args:
        value: Non-negative integer to encode
        
    Returns:
        Bytes representing the varint
        
    Raises:
        ValueError: If value is negative
    """
    if value < 0:
        raise ValueError("Cannot encode negative integers as varint")
    
    result = bytearray()
    while value >= 0x80:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)


def decode_varint(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """
    Decode a variable-length integer from bytes.
    
    Args:
        data: Byte sequence containing the varint
        offset: Starting offset in the data
        
    Returns:
        Tuple of (decoded_value, bytes_consumed)
        
    Raises:
        ValueError: If data is malformed or incomplete
    """
    if not data or offset >= len(data):
        raise ValueError("Insufficient data for varint decoding")
    
    result = 0
    shift = 0
    bytes_read = 0
    
    while True:
        if offset + bytes_read >= len(data):
            raise ValueError("Incomplete varint in data")
            
        byte = data[offset + bytes_read]
        bytes_read += 1
        
        result |= (byte & 0x7F) << shift
        
        if not (byte & 0x80):
            break
            
        shift += 7
        
        if shift >= 64:
            raise ValueError("Varint too large (exceeds 64 bits)")
    
    return result, bytes_read


def varint_size(value: int) -> int:
    """
    Calculate the size in bytes of a varint encoding.
    
    Args:
        value: Non-negative integer
        
    Returns:
        Number of bytes required for varint encoding
    """
    if value < 0:
        raise ValueError("Cannot calculate size for negative integers")
    
    if value == 0:
        return 1
    
    size = 0
    while value > 0:
        size += 1
        value >>= 7
    
    return size
