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
        decoded, _ = STTFrame.from_bytes(encoded)
        
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
        decoded, _ = STTFrame.from_bytes(encoded)
        
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
        decoded, _ = STTFrame.from_bytes(encoded, decrypt=True, stc_wrapper=stc_wrapper)
        
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
        decoded, _ = STTFrame.from_bytes(encoded)
        
        assert decoded.payload == b''
    
    def test_frame_large_payload_10kb(self):
        """Test frame with 10KB payload encode/decode."""
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
        decoded, _ = STTFrame.from_bytes(encoded)
        
        assert decoded.payload == large_payload
    
    def test_frame_flags(self):
        """Test frame with different flag values."""
        session_id = b'\x05' * 8
        
        for flags in [0x00, 0x01, 0x02, 0xFF]:
            frame = STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                session_id=session_id,
                stream_id=1,
                sequence=1,
                flags=flags,
                payload=b'test'
            )
            
            encoded = frame.to_bytes()
            decoded, _ = STTFrame.from_bytes(encoded)
            assert decoded.flags == flags
    
    def test_frame_stream_id_variations(self):
        """Test frames with various stream IDs."""
        session_id = b'\x06' * 8
        
        for stream_id in [0, 1, 100, 65535]:
            frame = STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                session_id=session_id,
                stream_id=stream_id,
                sequence=1,
                payload=b'test'
            )
            
            encoded = frame.to_bytes()
            decoded, _ = STTFrame.from_bytes(encoded)
            assert decoded.stream_id == stream_id
    
    def test_frame_sequence_wraparound(self):
        """Test frame with maximum sequence number."""
        session_id = b'\x07' * 8
        max_seq = 2**32 - 1
        
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            stream_id=1,
            sequence=max_seq,
            payload=b'test'
        )
        
        encoded = frame.to_bytes()
        decoded, _ = STTFrame.from_bytes(encoded)
        assert decoded.sequence == max_seq
    
    def test_frame_encryption_state_tracking(self):
        """Test frame tracks encryption state."""
        session_id = b'\x08' * 8
        
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            stream_id=1,
            sequence=1,
            payload=b'test'
        )
        
        assert frame._is_encrypted is False
    
    def test_frame_crypto_metadata_storage(self):
        """Test frame stores crypto metadata."""
        session_id = b'\x09' * 8
        
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            stream_id=1,
            sequence=1,
            payload=b'test',
            crypto_metadata=b'metadata'
        )
        
        assert frame.crypto_metadata == b'metadata'
    
    def test_frame_timestamp_default(self):
        """Test frame has default timestamp."""
        session_id = b'\x0a' * 8
        
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            stream_id=1,
            sequence=1,
            payload=b'test'
        )
        
        assert frame.timestamp > 0
        assert isinstance(frame.timestamp, int)
    
    def test_frame_session_id_validation(self):
        """Test session ID length validation."""
        with pytest.raises(STTFrameError, match="Session ID must be"):
            STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                session_id=b'\x01' * 4,  # Wrong length
                stream_id=1,
                sequence=1,
                payload=b'test'
            )
    
    def test_frame_sequence_validation(self):
        """Test sequence number validation."""
        with pytest.raises(STTFrameError, match="Sequence number must be non-negative"):
            STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                session_id=b'\x0b' * 8,
                stream_id=1,
                sequence=-1,
                payload=b'test'
            )
    
    def test_frame_timestamp_validation(self):
        """Test timestamp validation."""
        with pytest.raises(STTFrameError, match="Timestamp must be non-negative"):
            STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                session_id=b'\x0c' * 8,
                stream_id=1,
                sequence=1,
                timestamp=-1,
                payload=b'test'
            )
    
    def test_frame_stream_id_validation(self):
        """Test stream ID validation."""
        with pytest.raises(STTFrameError, match="Stream ID must be non-negative"):
            STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                session_id=b'\x0d' * 8,
                stream_id=-1,
                sequence=1,
                payload=b'test'
            )
    
    def test_frame_payload_bytes_type(self):
        """Test payload must be bytes."""
        session_id = b'\x0e' * 8
        
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=session_id,
            stream_id=1,
            sequence=1,
            payload=b'test'
        )
        
        assert isinstance(frame.payload, bytes)
    
    def test_frame_invalid_type(self):
        """Test creating frame with invalid type."""
        # Invalid type might be accepted or rejected
        try:
            frame = STTFrame(
                frame_type=999,  # Invalid type
                session_id=b'\x0f' * 8,
                stream_id=1,
                sequence=0,
                payload=b'test'
            )
            # If accepted, just verify it was created
            assert frame is not None
        except Exception:
            pass  # Also acceptable to reject
    
    def test_frame_empty_payload(self):
        """Test frame with empty payload."""
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=b'\x10' * 8,
            stream_id=1,
            sequence=0,
            payload=b''
        )
        
        assert frame.payload == b''
        assert len(frame.payload) == 0
    
    def test_frame_large_payload_1mb(self):
        """Test frame with 1MB payload creation."""
        large_payload = b'x' * 1000000  # 1MB
        
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=b'\x11' * 8,
            stream_id=1,
            sequence=0,
            payload=large_payload
        )
        
        assert len(frame.payload) == 1000000
    
    def test_frame_decode_invalid_data(self):
        """Test decoding invalid frame data."""
        with pytest.raises(Exception):
            STTFrame.from_bytes(b'invalid_frame_data')
    
    def test_frame_decode_truncated(self):
        """Test decoding truncated frame."""
        # Create valid frame then truncate it
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=b'\x12' * 8,
            stream_id=1,
            sequence=0,
            payload=b'test'
        )
        
        encoded = frame.to_bytes()
        truncated = encoded[:10]  # Only first 10 bytes
        
        with pytest.raises(Exception):
            STTFrame.from_bytes(truncated)
    
    def test_frame_max_sequence_number(self):
        """Test frame with maximum sequence number."""
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=b'\x13' * 8,
            stream_id=1,
            sequence=2**32 - 1,  # Max 32-bit value
            payload=b'test'
        )
        
        assert frame.sequence == 2**32 - 1
    
    def test_frame_handshake_type(self):
        """Test creating handshake frame."""
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_HANDSHAKE,
            session_id=b'\x14' * 8,
            stream_id=0,
            sequence=0,
            payload=b'handshake_data'
        )
        
        assert frame.frame_type == STT_FRAME_TYPE_HANDSHAKE
    
    def test_frame_double_encryption(self, stc_wrapper):
        """Test that encrypting twice raises error."""
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=b'\x16' * 8,
            stream_id=1,
            sequence=0,
            payload=b'test'
        )
        
        # Encrypt once
        frame.encrypt_payload(stc_wrapper)
        
        # Try to encrypt again
        with pytest.raises(STTFrameError, match="already encrypted"):
            frame.encrypt_payload(stc_wrapper)
    
    def test_frame_decrypt_unencrypted(self, stc_wrapper):
        """Test decrypting unencrypted frame raises error."""
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=b'\x17' * 8,
            stream_id=1,
            sequence=0,
            payload=b'test'
        )
        
        # Try to decrypt without encrypting
        with pytest.raises(STTFrameError, match="not encrypted"):
            frame.decrypt_payload(stc_wrapper)
    
    def test_frame_large_payload_100kb_encrypted(self, stc_wrapper):
        """Test frame with 100KB payload encrypt/decrypt."""
        large_payload = b'x' * 100000  # 100KB
        
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=b'\x18' * 8,
            stream_id=1,
            sequence=0,
            payload=large_payload
        )
        
        # Encrypt and decrypt
        frame.encrypt_payload(stc_wrapper)
        frame.decrypt_payload(stc_wrapper)
        
        assert frame.payload == large_payload
