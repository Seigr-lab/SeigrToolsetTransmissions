"""
Tests for varint encoding/decoding.
"""

import pytest
from seigr_toolset_transmissions.utils.varint import (
    encode_varint,
    decode_varint,
    varint_size,
)


class TestVarint:
    """Test varint encoding and decoding."""
    
    def test_encode_zero(self):
        """Test encoding zero."""
        result = encode_varint(0)
        assert result == b'\x00'
    
    def test_encode_small_values(self):
        """Test encoding small values."""
        assert encode_varint(1) == b'\x01'
        assert encode_varint(127) == b'\x7f'
    
    def test_encode_medium_values(self):
        """Test encoding medium values."""
        assert encode_varint(128) == b'\x80\x01'
        assert encode_varint(300) == b'\xac\x02'
    
    def test_encode_large_values(self):
        """Test encoding large values."""
        assert encode_varint(16384) == b'\x80\x80\x01'
    
    def test_decode_zero(self):
        """Test decoding zero."""
        value, size = decode_varint(b'\x00')
        assert value == 0
        assert size == 1
    
    def test_decode_small_values(self):
        """Test decoding small values."""
        value, size = decode_varint(b'\x01')
        assert value == 1
        assert size == 1
        
        value, size = decode_varint(b'\x7f')
        assert value == 127
        assert size == 1
    
    def test_decode_medium_values(self):
        """Test decoding medium values."""
        value, size = decode_varint(b'\x80\x01')
        assert value == 128
        assert size == 2
    
    def test_encode_decode_roundtrip(self):
        """Test encoding and decoding roundtrip."""
        test_values = [0, 1, 127, 128, 255, 256, 16383, 16384, 1000000]
        
        for original in test_values:
            encoded = encode_varint(original)
            decoded, _ = decode_varint(encoded)
            assert decoded == original
    
    def test_decode_with_offset(self):
        """Test decoding with offset."""
        data = b'\xff\xff\x80\x01\xff'
        value, size = decode_varint(data, offset=2)
        assert value == 128
        assert size == 2
    
    def test_varint_size(self):
        """Test varint size calculation."""
        assert varint_size(0) == 1
        assert varint_size(127) == 1
        assert varint_size(128) == 2
        assert varint_size(16383) == 2
        assert varint_size(16384) == 3
    
    def test_encode_negative_raises(self):
        """Test encoding negative value raises error."""
        with pytest.raises(ValueError):
            encode_varint(-1)
    
    def test_decode_insufficient_data(self):
        """Test decoding with insufficient data."""
        with pytest.raises(ValueError):
            decode_varint(b'')
        
        with pytest.raises(ValueError):
            decode_varint(b'\x80')  # Incomplete varint
