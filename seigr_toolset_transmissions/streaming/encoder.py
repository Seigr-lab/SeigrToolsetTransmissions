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
            data: Chunk data to encrypt (can be empty)
            
        Returns:
            Encrypted chunk with metadata in TLV format
        """
        if not isinstance(data, bytes):
            raise STTStreamingError("Data must be bytes")
        
        # Handle empty data - STC DSF doesn't accept empty data
        # Use a placeholder byte and mark it in metadata
        is_empty = len(data) == 0
        encrypt_data = b'\x00' if is_empty else data
        
        # Encrypt chunk using stream context - returns (encrypted_bytes, metadata_bytes)
        encrypted, metadata_bytes = self.stream_context.encrypt_chunk(encrypt_data)
        
        # If original was empty, prepend a flag byte (0x01 = empty, 0x00 = not empty)
        flag = b'\x01' if is_empty else b'\x00'
        
        # Metadata is already in TLV format from STC
        # Format: [empty_flag (1 byte)] [metadata_length (4 bytes)] [metadata_bytes] [encrypted_data]
        metadata_length = len(metadata_bytes).to_bytes(4, 'big')
        encoded = flag + metadata_length + metadata_bytes + encrypted
        
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
