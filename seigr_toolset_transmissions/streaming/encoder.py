"""
STC-based streaming encoder for chunk-wise encryption.
"""

from interfaces.api.streaming_context import StreamingContext
from ..crypto.stc_wrapper import STCWrapper
from ..utils.exceptions import STTStreamingError


class StreamEncoder:
    """
    Streaming encoder for chunk-wise data encryption.
    """
    
    def __init__(self, stc_wrapper: STCWrapper, session_id: bytes, stream_id: int):
        """
        Initialize stream encoder.
        
        Args:
            stc_wrapper: STC wrapper for crypto
            session_id: Session identifier
            stream_id: Stream identifier
        """
        self.stc_wrapper = stc_wrapper
        self.session_id = session_id
        self.stream_id = stream_id
        
        # Get StreamingContext directly from STC v0.4.0 (no wrapper)
        self.stream_context: StreamingContext = stc_wrapper.create_stream_context(session_id, stream_id)
        
        # Track sequence
        self._sequence = 0
    
    def encode_chunk(self, data: bytes) -> bytes:
        """
        Encode (encrypt) a data chunk using STC v0.4.0 StreamingContext.
        
        Args:
            data: Chunk data to encrypt (can be empty)
            
        Returns:
            Encrypted chunk with 16-byte fixed header
            Format: [empty_flag(1)] [header(16)] [encrypted_data]
        """
        if not isinstance(data, bytes):
            raise STTStreamingError("Data must be bytes")
        
        # Handle empty data - StreamingContext handles gracefully
        is_empty = len(data) == 0
        encrypt_data = b'\x00' if is_empty else data
        
        # StreamingContext.encrypt_chunk returns (ChunkHeader, encrypted_bytes)
        header_obj, encrypted = self.stream_context.encrypt_chunk(encrypt_data)
        
        # Serialize ChunkHeader to 16-byte fixed format
        header_bytes = header_obj.to_bytes()
        
        # Format: [empty_flag(1)] [header(16)] [encrypted]
        flag = b'\x01' if is_empty else b'\x00'
        encoded = flag + header_bytes + encrypted
        
        # Increment sequence
        self._sequence += 1
        
        return encoded
    
    def get_sequence(self) -> int:
        """Get current sequence number."""
        return self._sequence
    
    def reset(self) -> None:
        """Reset encoder sequence."""
        # Recreate StreamingContext (no reset method in v0.4.0)
        self.stream_context = self.stc_wrapper.create_stream_context(
            self.session_id, self.stream_id
        )
        self._sequence = 0
