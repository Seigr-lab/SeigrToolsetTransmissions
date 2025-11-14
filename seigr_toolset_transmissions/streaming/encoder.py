"""
Streaming encoder using STC's native encrypt_stream.

Provides chunked encryption for large data streams without loading
entire payload into memory.
"""

from typing import Iterator, Optional, Dict, Any
import secrets

from ..crypto.stc_wrapper import StreamContext
from ..utils.exceptions import STTStreamError
from ..utils.logging import get_logger


logger = get_logger(__name__)


class StreamEncoder:
    """
    Encode data stream with STC encryption.
    
    Uses STC's native encrypt_stream for efficient chunked processing.
    Each chunk is encrypted independently with chunk-specific associated data.
    """
    
    def __init__(
        self,
        stream_context: StreamContext,
        chunk_size: int = 65536,  # 64KB chunks
    ):
        """
        Initialize stream encoder.
        
        Args:
            stream_context: STC stream context for encryption
            chunk_size: Size of chunks in bytes (default 64KB)
        """
        if chunk_size <= 0:
            raise STTStreamError("Chunk size must be positive")
        
        self.stream_context = stream_context
        self.chunk_size = chunk_size
        self.chunks_encoded = 0
        self.total_bytes_encoded = 0
    
    def encode_stream(
        self,
        data_stream: Iterator[bytes],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Iterator[bytes]:
        """
        Encode data stream chunk by chunk.
        
        Args:
            data_stream: Iterator yielding data chunks
            metadata: Optional metadata for associated data
            
        Yields:
            Encrypted chunks
            
        Raises:
            STTStreamError: If encoding fails
        """
        chunk_index = 0
        
        try:
            for chunk in data_stream:
                if not chunk:
                    continue
                
                # Encrypt chunk with STC stream context
                encrypted_chunk = self.stream_context.encrypt_chunk(
                    chunk,
                    chunk_index=chunk_index
                )
                
                # Update stats
                chunk_index += 1
                self.chunks_encoded += 1
                self.total_bytes_encoded += len(chunk)
                
                yield encrypted_chunk
            
            logger.debug(
                f"Encoded {self.chunks_encoded} chunks "
                f"({self.total_bytes_encoded} bytes)"
            )
            
        except Exception as e:
            raise STTStreamError(f"Stream encoding failed: {e}")
    
    def encode_bytes(
        self,
        data: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Iterator[bytes]:
        """
        Encode bytes by splitting into chunks.
        
        Args:
            data: Data to encode
            metadata: Optional metadata
            
        Yields:
            Encrypted chunks
        """
        # Split data into chunks
        def chunk_generator():
            offset = 0
            while offset < len(data):
                yield data[offset:offset + self.chunk_size]
                offset += self.chunk_size
        
        yield from self.encode_stream(chunk_generator(), metadata)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get encoding statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            'chunks_encoded': self.chunks_encoded,
            'total_bytes_encoded': self.total_bytes_encoded,
            'chunk_size': self.chunk_size,
        }
    
    def reset(self) -> None:
        """Reset encoding statistics."""
        self.chunks_encoded = 0
        self.total_bytes_encoded = 0
