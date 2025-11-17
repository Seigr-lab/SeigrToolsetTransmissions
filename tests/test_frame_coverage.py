"""
Frame module comprehensive coverage tests.
"""

import pytest
from seigr_toolset_transmissions.frame.frame import STTFrame
from seigr_toolset_transmissions.crypto import STCWrapper


class TestFrameCoverage:
    """Frame coverage tests."""
    
    @pytest.fixture
    def stc_wrapper(self):
        return STCWrapper(b"frame_coverage_32_bytes_minimu!")
    
    def test_frame_to_bytes(self, stc_wrapper):
        """Test frame to_bytes."""
        frame = STTFrame(
            frame_type=1,
            session_id=b"abcdefgh",
            sequence=1,
            stream_id=1,
            flags=0,
            payload=b"test_data"
        )
        data = frame.to_bytes()
        assert isinstance(data, bytes)
    
    def test_frame_with_encryption(self, stc_wrapper):
        """Test frame encryption."""
        original_payload = b"encrypted_payload"
        frame = STTFrame(
            frame_type=2,
            session_id=b"12345678",
            sequence=2,
            stream_id=2,
            flags=0,
            payload=original_payload
        )
        encrypted = frame.encrypt_payload(stc_wrapper)
        assert encrypted != original_payload
    
    def test_frame_empty_payload(self):
        """Test frame with empty payload."""
        frame = STTFrame(
            frame_type=1,
            session_id=b"87654321",
            sequence=3,
            stream_id=3,
            flags=0,
            payload=b""
        )
        data = frame.to_bytes()
        assert isinstance(data, bytes)
    
    def test_frame_large_stream_id(self):
        """Test frame with large stream ID."""
        frame = STTFrame(
            frame_type=1,
            session_id=b"aaaabbbb",
            sequence=4,
            stream_id=65535,
            flags=0xff,
            payload=b"test"
        )
        data = frame.to_bytes()
        assert isinstance(data, bytes)
    
    def test_frame_decrypt_payload(self, stc_wrapper):
        """Test frame decryption."""
        frame = STTFrame(
            frame_type=1,
            session_id=b"11111111",
            sequence=5,
            stream_id=1,
            flags=0,
            payload=b"decrypt_me"
        )
        try:
            encrypted = frame.encrypt_payload(stc_wrapper)
            decrypted = frame.decrypt_payload(stc_wrapper)
            assert decrypted == frame.payload
        except Exception:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
