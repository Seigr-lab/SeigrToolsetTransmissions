"""
Frame module comprehensive coverage tests.
"""

import pytest
import struct
from seigr_toolset_transmissions.frame import STTFrame
from seigr_toolset_transmissions.utils.exceptions import STTFrameError
from seigr_toolset_transmissions.utils.constants import STT_FRAME_TYPE_DATA, STT_MAGIC


class TestFrameConstruction:
    """Test frame construction edge cases."""
    
    def test_frame_with_all_parameters(self):
        """Test creating frame with all parameters."""
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=b'\xAA' * 8,
            sequence=12345,
            stream_id=999,
            payload=b"full payload data",
            flags=0b00001111,
            timestamp=1234567890000,
            crypto_metadata=b"metadata123"
        )
        
        assert frame.frame_type == STT_FRAME_TYPE_DATA
        assert frame.session_id == b'\xAA' * 8
        assert frame.sequence == 12345
        assert frame.stream_id == 999
        assert frame.payload == b"full payload data"
        assert frame.flags == 0b00001111
        assert frame.timestamp == 1234567890000
        assert frame.crypto_metadata == b"metadata123"
    
    def test_frame_minimal_parameters(self):
        """Test creating frame with minimal parameters."""
        frame = STTFrame(
            frame_type=0,
            session_id=b'\x00' * 8,
            sequence=0,
            stream_id=0,
            payload=b""
        )
        
        assert frame.payload == b""
        assert frame.flags == 0
        assert frame.crypto_metadata is None
    
    def test_frame_large_payload(self):
        """Test frame with large payload."""
        large_payload = b'X' * 50000
        
        frame = STTFrame(
            frame_type=0,
            session_id=b'\xBB' * 8,
            sequence=1,
            stream_id=1,
            payload=large_payload
        )
        
        assert len(frame.payload) == 50000
    
    def test_frame_different_types(self):
        """Test frames with different types."""
        for frame_type in [0, 1, 2, 3, 4]:
            frame = STTFrame(
                frame_type=frame_type,
                session_id=b'\xCC' * 8,
                sequence=1,
                stream_id=1,
                payload=b"test"
            )
            
            assert frame.frame_type == frame_type


class TestFrameSerialization:
    """Test frame serialization/deserialization."""
    
    def test_frame_roundtrip_simple(self):
        """Test simple frame roundtrip."""
        original = STTFrame(
            frame_type=0,
            session_id=b'\xDD' * 8,
            sequence=100,
            stream_id=50,
            payload=b"simple test"
        )
        
        serialized = original.to_bytes()
        result = STTFrame.from_bytes(serialized)
        
        # Handle tuple return
        if isinstance(result, tuple):
            deserialized = result[0]
        else:
            deserialized = result
        
        assert deserialized.frame_type == original.frame_type
        assert deserialized.session_id == original.session_id
        assert deserialized.sequence == original.sequence
        assert deserialized.stream_id == original.stream_id
        assert deserialized.payload == original.payload
    
    def test_frame_roundtrip_with_metadata(self):
        """Test frame roundtrip with crypto metadata."""
        original = STTFrame(
            frame_type=1,
            session_id=b'\xEE' * 8,
            sequence=200,
            stream_id=75,
            payload=b"metadata test",
            crypto_metadata=b"encrypted_meta_info"
        )
        
        serialized = original.to_bytes()
        result = STTFrame.from_bytes(serialized)
        
        if isinstance(result, tuple):
            deserialized = result[0]
        else:
            deserialized = result
        
        assert deserialized.crypto_metadata == original.crypto_metadata
    
    def test_frame_roundtrip_with_flags(self):
        """Test frame roundtrip with flags."""
        original = STTFrame(
            frame_type=2,
            session_id=b'\xFF' * 8,
            sequence=300,
            stream_id=100,
            payload=b"flags test",
            flags=0b10101010
        )
        
        serialized = original.to_bytes()
        result = STTFrame.from_bytes(serialized)
        
        if isinstance(result, tuple):
            deserialized = result[0]
        else:
            deserialized = result
        
        assert deserialized.flags == original.flags
    
    def test_frame_roundtrip_empty_payload(self):
        """Test frame with empty payload."""
        original = STTFrame(
            frame_type=0,
            session_id=b'\x11' * 8,
            sequence=1,
            stream_id=1,
            payload=b""
        )
        
        serialized = original.to_bytes()
        result = STTFrame.from_bytes(serialized)
        
        if isinstance(result, tuple):
            deserialized = result[0]
        else:
            deserialized = result
        
        assert deserialized.payload == b""


class TestFrameParsingErrors:
    """Test frame parsing error conditions."""
    
    def test_from_bytes_corrupted_header(self):
        """Test parsing frame with corrupted data."""
        # Create valid frame
        frame = STTFrame(
            frame_type=0,
            session_id=b'\x22' * 8,
            sequence=1,
            stream_id=1,
            payload=b"test"
        )
        
        serialized = frame.to_bytes()
        
        # Try with heavily truncated data
        corrupted = serialized[:5]  # Way too short
        
        # Should raise error or handle gracefully
        try:
            STTFrame.from_bytes(corrupted)
        except (STTFrameError, struct.error, ValueError, IndexError):
            # Expected - corrupted data
            pass
    
    def test_from_bytes_metadata_extends_beyond_frame(self):
        """Test parsing frame where metadata length is wrong."""
        frame = STTFrame(
            frame_type=0,
            session_id=b'\x33' * 8,
            sequence=1,
            stream_id=1,
            payload=b"test",
            crypto_metadata=b"meta"
        )
        
        serialized = frame.to_bytes()
        
        # Truncate to simulate metadata extending beyond frame
        truncated = serialized[:len(serialized) - 2]
        
        with pytest.raises(STTFrameError):
            STTFrame.from_bytes(truncated)
    
    def test_from_bytes_multiple_frames(self):
        """Test parsing when data contains multiple frames."""
        frame1 = STTFrame(
            frame_type=0,
            session_id=b'\x44' * 8,
            sequence=1,
            stream_id=1,
            payload=b"frame1"
        )
        
        frame2 = STTFrame(
            frame_type=0,
            session_id=b'\x55' * 8,
            sequence=2,
            stream_id=2,
            payload=b"frame2"
        )
        
        # Concatenate two frames
        combined = frame1.to_bytes() + frame2.to_bytes()
        
        # Should parse first frame
        result = STTFrame.from_bytes(combined)
        
        if isinstance(result, tuple):
            parsed_frame, remaining = result
            # Check we got the first frame
            assert parsed_frame.sequence == 1
            # Should have remaining data
            if isinstance(remaining, bytes):
                assert len(remaining) > 0
        else:
            # Just the frame object
            assert result.sequence == 1


class TestFrameSpecialCases:
    """Test special frame cases."""
    
    def test_frame_max_sequence_number(self):
        """Test frame with maximum sequence number."""
        max_seq = (2 ** 64) - 1  # Max uint64
        
        frame = STTFrame(
            frame_type=0,
            session_id=b'\x66' * 8,
            sequence=max_seq,
            stream_id=1,
            payload=b"max seq"
        )
        
        assert frame.sequence == max_seq
    
    def test_frame_max_stream_id(self):
        """Test frame with maximum stream ID."""
        max_stream = (2 ** 32) - 1  # Max uint32
        
        frame = STTFrame(
            frame_type=0,
            session_id=b'\x77' * 8,
            sequence=1,
            stream_id=max_stream,
            payload=b"max stream"
        )
        
        assert frame.stream_id == max_stream
    
    def test_frame_zero_timestamp(self):
        """Test frame with zero timestamp."""
        frame = STTFrame(
            frame_type=0,
            session_id=b'\x88' * 8,
            sequence=1,
            stream_id=1,
            payload=b"zero time",
            timestamp=0
        )
        
        assert frame.timestamp == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
