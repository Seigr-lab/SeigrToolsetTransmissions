"""
STC-based streaming decoder for chunk-wise decryption.
"""

from typing import Dict

from ..crypto.stc_wrapper import STCWrapper
from ..utils.exceptions import STTStreamingError


class StreamDecoder:
    """
    Streaming decoder for chunk-wise data decryption.
    """
    
    def __init__(self, stc_wrapper: STCWrapper, session_id: bytes, stream_id: int):
        """
        Initialize stream decoder.
        
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
        
        # Track chunks for out-of-order delivery
        self.chunk_buffer: Dict[int, bytes] = {}
        self.next_expected_index = 0
    
    def decode_chunk(self, encoded_data: bytes, chunk_index: int) -> bytes:
        """
        Decode (decrypt) a data chunk.
        
        Args:
            encoded_data: Encrypted chunk with metadata
            chunk_index: Chunk sequence number
            
        Returns:
            Decrypted chunk data
        """
        # Parse encoded data
        # Format: [metadata_length (4 bytes)] [metadata] [encrypted_data]
        metadata_length = int.from_bytes(encoded_data[:4], 'big')
        metadata = encoded_data[4:4 + metadata_length]
        encrypted = encoded_data[4 + metadata_length:]
        
        # Decrypt chunk using stream context
        decrypted = self.stream_context.decrypt_chunk(
            encrypted,
            metadata,
            chunk_index
        )
        
        return decrypted
    
    def reset(self) -> None:
        """Reset decoder state."""
        self.chunk_buffer.clear()
        self.next_expected_index = 0
        self.stream_context.reset_index()
