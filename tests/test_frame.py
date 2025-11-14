"""
Tests for STT frame encoding/decoding with STC encryption.
"""

import pytest
from seigr_toolset_transmissions.frame import STTFrame
from seigr_toolset_transmissions.crypto import STCWrapper
from seigr_toolset_transmissions.utils.constants import (
    STT_FRAME_TYPE_DATA,
    STT_FRAME_TYPE_HANDSHAKE,
    STT_FLAG_NONE,
)
from seigr_toolset_transmissions.utils.exceptions import STTFrameError


class TestSTTFrame:
    """Test STT frame structure with STC encryption."""
    
    @pytest.fixture
    def stc_wrapper(self):
        """Create STC wrapper for tests."""
        return STCWrapper(b"test_seed_32_bytes_minimum!!!!!")
    
    def test_create_frame(self):
        """Test creating a frame."""
        session_id = b'\x01\x02\x03\x04\x05\x06\x07\x08'
        payload = b'test payload'
        
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            stream_id=1,
            sequence=42,
            payload=payload,
        )
        
        assert frame.frame_type == STT_FRAME_TYPE_DATA
        assert frame.session_id == session_id
        assert frame.stream_id == 1
        assert frame.sequence == 42
        assert frame.payload == payload
    
    def test_frame_encoding(self):
        """Test frame encoding to bytes."""
        session_id = b'\x00' * 8
        payload = b'hello'
        
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            stream_id=1,
            sequence=0,
            payload=payload,
        )
        
        encoded = frame.to_bytes()
        assert isinstance(encoded, bytes)
        assert len(encoded) > 0
        # Check magic bytes
        assert encoded[:2] == b'\x53\x54'
    
    def test_frame_decoding(self):
        """Test frame decoding from bytes."""
        session_id = b'\x11' * 8
        payload = b'test data'
        
        # Create and encode frame
        original = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            stream_id=2,
            sequence=100,
            payload=payload,
        )
        
        encoded = original.to_bytes()
        
        # Decode frame
        decoded = STTFrame.from_bytes(encoded)
        
        assert decoded.frame_type == original.frame_type
        assert decoded.session_id == original.session_id
        assert decoded.stream_id == original.stream_id
        assert decoded.sequence == original.sequence
        assert decoded.payload == original.payload
    
    def test_frame_roundtrip(self):
        """Test encoding and decoding roundtrip."""
        session_id = b'\xaa' * 8
        payload = b'roundtrip test payload'
        
        original = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            stream_id=3,
            sequence=999,
            flags=STT_FLAG_NONE,
            payload=payload,
        )
        
        # Encode and decode
        encoded = original.to_bytes()
        decoded = STTFrame.from_bytes(encoded)
        
        # Verify all fields match
        assert decoded.frame_type == original.frame_type
        assert decoded.flags == original.flags
        assert decoded.session_id == original.session_id
        assert decoded.stream_id == original.stream_id
        assert decoded.sequence == original.sequence
        assert decoded.payload == original.payload
    
    def test_invalid_session_id_length(self):
        """Test that invalid session ID length raises error."""
        with pytest.raises(STTFrameError):
            STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                session_id=b'\x00' * 7,  # Wrong length
                stream_id=1,
                sequence=0,
                payload=b'',
            )
    
    def test_encrypt_decrypt_payload(self, stc_wrapper):
        """Test encrypting and decrypting frame payload."""
        session_id = b'\x01' * 8
        payload = b'secret data'
        
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            stream_id=1,
            sequence=42,
            payload=payload,
        )
        
        # Encrypt
        frame.encrypt_payload(stc_wrapper)
        assert frame._is_encrypted
        assert frame.payload != payload  # Payload should be encrypted
        assert frame.crypto_metadata is not None
        
        # Decrypt
        decrypted = frame.decrypt_payload(stc_wrapper)
        assert decrypted == payload
    
    def test_encrypt_decrypt_roundtrip(self, stc_wrapper):
        """Test full encrypt/decrypt roundtrip."""
        session_id = b'\x02' * 8
        original_payload = b'confidential message'
        
        # Create and encrypt frame
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            stream_id=2,
            sequence=100,
            payload=original_payload,
        )
        frame.encrypt_payload(stc_wrapper)
        
        # Serialize
        encoded = frame.to_bytes()
        
        # Deserialize and decrypt
        decoded = STTFrame.from_bytes(encoded, decrypt=True, stc_wrapper=stc_wrapper)
        
        assert decoded.payload == original_payload
    
    def test_decode_invalid_magic(self):
        """Test decoding with invalid magic bytes."""
        bad_data = b'XX\x00\x00\x00'
        
        with pytest.raises(STTFrameError, match="Invalid magic bytes"):
            STTFrame.from_bytes(bad_data)
    
    def test_decode_insufficient_data(self):
        """Test decoding with insufficient data."""
        with pytest.raises(STTFrameError):
            STTFrame.from_bytes(b'S')
    
    def test_frame_with_empty_payload(self):
        """Test frame with empty payload."""
        session_id = b'\x03' * 8
        
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_HANDSHAKE,
            session_id=session_id,
            stream_id=0,
            sequence=0,
            payload=b'',
        )
        
        encoded = frame.to_bytes()
        decoded = STTFrame.from_bytes(encoded)
        
        assert decoded.payload == b''
    
    def test_frame_large_payload(self):
        """Test frame with large payload."""
        session_id = b'\x04' * 8
        large_payload = b'x' * 10000  # 10KB
        
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            stream_id=5,
            sequence=1,
            payload=large_payload,
        )
        
        encoded = frame.to_bytes()
        decoded = STTFrame.from_bytes(encoded)
        
        assert decoded.payload == large_payload
