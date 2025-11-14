"""
Streaming decoder using STC's native decrypt_stream.

Provides chunked decryption for large data streams without loading
entire payload into memory.
"""

from typing import Iterator, Optional, Dict, Any

from ..crypto.stc_wrapper import StreamContext
from ..utils.exceptions import STTStreamError
from ..utils.logging import get_logger


logger = get_logger(__name__)


class StreamDecoder:
    """
    Decode encrypted data stream with STC decryption.
    
    Uses STC's native decrypt_stream for efficient chunked processing.
    Must decrypt chunks in same order they were encrypted.
    """
    
    def __init__(
        self,
        stream_context: StreamContext,
    ):
        """
        Initialize stream decoder.
        
        Args:
            stream_context: STC stream context for decryption
        """
        self.stream_context = stream_context
        self.chunks_decoded = 0
        self.total_bytes_decoded = 0
    
    def decode_stream(
        self,
        encrypted_stream: Iterator[bytes],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Iterator[bytes]:
        """
        Decode encrypted stream chunk by chunk.
        
        Args:
            encrypted_stream: Iterator yielding encrypted chunks
            metadata: Optional metadata for verification
            
        Yields:
            Decrypted chunks
            
        Raises:
            STTStreamError: If decoding fails
        """
        chunk_index = 0
        
        try:
            for encrypted_chunk in encrypted_stream:
                if not encrypted_chunk:
                    continue
                
                # Decrypt chunk with STC stream context
                decrypted_chunk = self.stream_context.decrypt_chunk(
                    encrypted_chunk,
                    chunk_index=chunk_index
                )
                
                # Update stats
                chunk_index += 1
                self.chunks_decoded += 1
                self.total_bytes_decoded += len(decrypted_chunk)
                
                yield decrypted_chunk
            
            logger.debug(
                f"Decoded {self.chunks_decoded} chunks "
                f"({self.total_bytes_decoded} bytes)"
            )
            
        except Exception as e:
            raise STTStreamError(f"Stream decoding failed: {e}")
    
    def decode_to_bytes(
        self,
        encrypted_stream: Iterator[bytes],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Decode stream and return complete bytes.
        
        Args:
            encrypted_stream: Iterator yielding encrypted chunks
            metadata: Optional metadata
            
        Returns:
            Complete decrypted data
        """
        chunks = list(self.decode_stream(encrypted_stream, metadata))
        return b''.join(chunks)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get decoding statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            'chunks_decoded': self.chunks_decoded,
            'total_bytes_decoded': self.total_bytes_decoded,
        }
    
    def reset(self) -> None:
        """Reset decoding statistics."""
        self.chunks_decoded = 0
        self.total_bytes_decoded = 0
