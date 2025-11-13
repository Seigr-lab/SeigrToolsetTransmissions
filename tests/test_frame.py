"""
Tests for STT frame encoding/decoding.
"""

import pytest
from seigr_toolset_transmissions.frame import STTFrame
from seigr_toolset_transmissions.utils.constants import (
    STT_FRAME_TYPE_DATA,
    STT_FLAG_NONE,
)
from seigr_toolset_transmissions.utils.exceptions import STTFrameError


class TestSTTFrame:
    """Test STT frame structure."""
    
    def test_create_frame(self):
        """Test creating a frame."""
        session_id = b'\x01\x02\x03\x04\x05\x06\x07\x08'
        payload = b'test payload'
        
        frame = STTFrame.create_frame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            sequence=42,
            payload=payload,
        )
        
        assert frame.frame_type == STT_FRAME_TYPE_DATA
        assert frame.session_id == session_id
        assert frame.sequence == 42
        assert frame.payload == payload
    
    def test_frame_encoding(self):
        """Test frame encoding to bytes."""
        session_id = b'\x00' * 8
        payload = b'hello'
        
        frame = STTFrame.create_frame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            sequence=0,
            payload=payload,
        )
        
        encoded = frame.to_bytes()
        assert isinstance(encoded, bytes)
        assert len(encoded) > 0
    
    def test_frame_decoding(self):
        """Test frame decoding from bytes."""
        session_id = b'\x11' * 8
        payload = b'test data'
        
        # Create and encode frame
        original = STTFrame.create_frame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            sequence=100,
            payload=payload,
        )
        
        encoded = original.to_bytes()
        
        # Decode frame
        decoded, bytes_consumed = STTFrame.from_bytes(encoded)
        
        assert decoded.frame_type == original.frame_type
        assert decoded.session_id == original.session_id
        assert decoded.sequence == original.sequence
        assert decoded.payload == original.payload
        assert bytes_consumed == len(encoded)
    
    def test_frame_roundtrip(self):
        """Test encoding and decoding roundtrip."""
        session_id = b'\xaa' * 8
        payload = b'roundtrip test payload'
        
        original = STTFrame.create_frame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            sequence=999,
            payload=payload,
            flags=STT_FLAG_NONE,
        )
        
        # Encode and decode
        encoded = original.to_bytes()
        decoded, _ = STTFrame.from_bytes(encoded)
        
        # Verify all fields match
        assert decoded.frame_type == original.frame_type
        assert decoded.flags == original.flags
        assert decoded.session_id == original.session_id
        assert decoded.sequence == original.sequence
        assert decoded.payload == original.payload
    
    def test_invalid_session_id_length(self):
        """Test that invalid session ID length raises error."""
        with pytest.raises(STTFrameError):
            STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                flags=0,
                session_id=b'\x00' * 7,  # Wrong length
                sequence=0,
                timestamp=0,
                payload=b'',
            )
    
    def test_get_associated_data(self):
        """Test getting associated data for AEAD."""
        session_id = b'\x01' * 8
        
        frame = STTFrame.create_frame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            sequence=42,
            payload=b'test',
        )
        
        ad = frame.get_associated_data()
        assert isinstance(ad, bytes)
        assert len(ad) > 0
    
    def test_decode_invalid_magic(self):
        """Test decoding with invalid magic bytes."""
        bad_data = b'XX\x00\x00\x00'
        
        with pytest.raises(STTFrameError, match="Invalid magic bytes"):
            STTFrame.from_bytes(bad_data)
    
    def test_decode_insufficient_data(self):
        """Test decoding with insufficient data."""
        with pytest.raises(STTFrameError):
            STTFrame.from_bytes(b'S')
