"""
STC-based streaming decoder for chunk-wise decryption.
"""

from typing import Dict, List, Optional

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
        
        # Keep ordered list of decoded chunks
        self.decoded_chunks: List[bytes] = []
    
    def decode_chunk(self, encoded_data: bytes, sequence: Optional[int] = None) -> bytes:
        """
        Decode (decrypt) a data chunk.
        
        Args:
            encoded_data: Encrypted chunk with TLV metadata
            sequence: Optional sequence number for out-of-order delivery
            
        Returns:
            Decrypted chunk data
            
        Raises:
            STTStreamingError: If data is corrupted or decryption fails
        """
        try:
            if not isinstance(encoded_data, bytes):
                raise STTStreamingError("Encoded data must be bytes")
            
            if len(encoded_data) < 5:  # 1 byte flag + 4 bytes length minimum
                raise STTStreamingError("Encoded data too short")
            
            # Parse encoded data
            # Format: [empty_flag (1 byte)] [metadata_length (4 bytes)] [metadata_bytes] [encrypted_data]
            empty_flag = encoded_data[0]
            metadata_length = int.from_bytes(encoded_data[1:5], 'big')
            
            if metadata_length > len(encoded_data) - 5:
                raise STTStreamingError("Invalid metadata length")
            
            metadata_bytes = encoded_data[5:5 + metadata_length]
            encrypted = encoded_data[5 + metadata_length:]
            
            # Use provided sequence or auto-increment
            chunk_index = sequence if sequence is not None else self.next_expected_index
            
            # Decrypt chunk using stream context
            # metadata_bytes is already in TLV format from STC
            decrypted = self.stream_context.decrypt_chunk(
                encrypted,
                metadata_bytes,
                chunk_index
            )
            
            # If empty flag is set, return empty bytes (ignore decrypted placeholder)
            if empty_flag == 0x01:
                decrypted = b""
            
            # Store in buffer if out-of-order
            if sequence is not None:
                self.chunk_buffer[sequence] = decrypted
            else:
                # In-order chunk, add to decoded list
                self.decoded_chunks.append(decrypted)
                self.next_expected_index += 1
            
            return decrypted
            
        except (ValueError, IndexError, KeyError) as e:
            raise STTStreamingError(f"Failed to decode chunk: {e}")
        except Exception as e:
            raise STTStreamingError(f"Decryption failed: {e}")
    
    def get_ordered_chunks(self) -> List[bytes]:
        """
        Get chunks in order from buffer.
        
        Returns:
            List of chunks in sequence order
        """
        if not self.chunk_buffer:
            return []
        
        # Sort by sequence number and return chunk data
        sorted_indices = sorted(self.chunk_buffer.keys())
        return [self.chunk_buffer[i] for i in sorted_indices]
    
    def get_received_chunks(self) -> List[bytes]:
        """
        Get all received chunks (buffered out-of-order chunks).
        
        Returns:
            List of buffered chunks
        """
        return list(self.chunk_buffer.values())
    
    def reset(self) -> None:
        """Reset decoder state."""
        self.chunk_buffer.clear()
        self.decoded_chunks.clear()
        self.next_expected_index = 0
        self.stream_context.reset_index()
