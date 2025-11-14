"""
STC-based streaming encoder for chunk-wise encryption.
"""

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
        
        # Create isolated stream context
        self.stream_context = stc_wrapper.create_stream_context(session_id, stream_id)
        
        # Track sequence
        self._sequence = 0
    
    def encode_chunk(self, data: bytes) -> bytes:
        """
        Encode (encrypt) a data chunk.
        
        Args:
            data: Chunk data to encrypt
            
        Returns:
            Encrypted chunk with metadata
        """
        # Encrypt chunk using stream context
        encrypted, metadata = self.stream_context.encrypt_chunk(data)
        
        # Combine encrypted data and metadata
        # Format: [metadata_length (4 bytes)] [metadata] [encrypted_data]
        metadata_length = len(metadata).to_bytes(4, 'big')
        encoded = metadata_length + metadata + encrypted
        
        # Increment sequence
        self._sequence += 1
        
        return encoded
    
    def get_sequence(self) -> int:
        """Get current sequence number."""
        return self._sequence
    
    def reset(self) -> None:
        """Reset encoder sequence."""
        self.stream_context.reset_index()
        self._sequence = 0
