"""
STT Frame structure and encoding/decoding with STC encryption.
"""

import struct
import time
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from ..utils.constants import (
    STT_MAGIC,
    STT_VERSION,
    STT_SESSION_ID_LENGTH,
    STT_SEQUENCE_LENGTH,
    STT_TIMESTAMP_LENGTH,
    STT_RESERVED_LENGTH,
    STT_MAX_FRAME_SIZE,
    STT_FRAME_TYPE_DATA,
)
from ..utils.exceptions import STTFrameError
from ..utils.varint import encode_varint, decode_varint

if TYPE_CHECKING:
    from ..crypto.stc_wrapper import STCWrapper


@dataclass
class STTFrame:
    """
    Represents an STT protocol frame with STC encryption.
    
    Frame Structure:
    | Magic (2) | Length (varint) | Type (1) | Flags (1) |
    | Session ID (8) | Seq (8) | Timestamp (8) | Stream ID (4) |
    | Meta Length (varint) | Crypto Metadata (variable) |
    | Payload (variable, encrypted) |
    """
    
    frame_type: int
    session_id: bytes
    sequence: int
    stream_id: int
    payload: bytes
    flags: int = 0
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    crypto_metadata: Optional[bytes] = field(default=None)
    _is_encrypted: bool = field(default=False, repr=False)
    
    def __post_init__(self) -> None:
        """Validate frame fields."""
        if len(self.session_id) != STT_SESSION_ID_LENGTH:
            raise STTFrameError(
                f"Session ID must be {STT_SESSION_ID_LENGTH} bytes"
            )
        
        if self.sequence < 0:
            raise STTFrameError("Sequence number must be non-negative")
        
        if self.timestamp < 0:
            raise STTFrameError("Timestamp must be non-negative")
        
        if self.stream_id < 0:
            raise STTFrameError("Stream ID must be non-negative")
    
    def encrypt_payload(self, stc_wrapper: 'STCWrapper') -> bytes:
        """
        Encrypt frame payload using STC with associated data.
        
        Args:
            stc_wrapper: STCWrapper instance for encryption
            
        Returns:
            Encrypted payload bytes
            
        Raises:
            STTFrameError: If encryption fails
        """
        if self._is_encrypted:
            raise STTFrameError("Payload already encrypted")
        
        # Build associated data for AEAD-like authentication
        associated_data = {
            'frame_type': self.frame_type,
            'flags': self.flags,
            'session_id': self.session_id,
            'sequence': self.sequence,
            'timestamp': self.timestamp,
            'stream_id': self.stream_id
        }
        
        try:
            # Encrypt using STC wrapper
            encrypted_payload, metadata = stc_wrapper.encrypt_frame(
                self.payload,
                associated_data
            )
            
            # Store metadata and encrypted payload
            # NOTE: Metadata can be large (~100KB with minimal STC params)
            # In production, consider session-level metadata exchange
            self.crypto_metadata = metadata
            original_payload = self.payload
            self.payload = encrypted_payload
            self._is_encrypted = True
            
            return encrypted_payload
            
        except Exception as e:
            raise STTFrameError(f"Encryption failed: {e}")
    
    def decrypt_payload(self, stc_wrapper: 'STCWrapper') -> bytes:
        """
        Decrypt frame payload using STC.
        
        Args:
            stc_wrapper: STCWrapper instance for decryption
            
        Returns:
            Decrypted payload bytes
            
        Raises:
            STTFrameError: If decryption fails
        """
        if not self._is_encrypted:
            raise STTFrameError("Payload not encrypted")
        
        if self.crypto_metadata is None:
            raise STTFrameError("Missing crypto metadata")
        
        # Build same associated data used during encryption
        associated_data = {
            'frame_type': self.frame_type,
            'flags': self.flags,
            'session_id': self.session_id,
            'sequence': self.sequence,
            'timestamp': self.timestamp,
            'stream_id': self.stream_id
        }
        
        try:
            # Decrypt using STC wrapper
            decrypted_payload = stc_wrapper.decrypt_frame(
                self.payload,
                self.crypto_metadata,
                associated_data
            )
            
            # Update payload and mark as decrypted
            self.payload = decrypted_payload
            self._is_encrypted = False
            
            return decrypted_payload
            
        except Exception as e:
            raise STTFrameError(f"Decryption failed: {e}")
    
    def to_bytes(self) -> bytes:
        """
        Encode frame to bytes (call encrypt_payload first if encrypting).
        
        Returns:
            Encoded frame bytes
            
        Raises:
            STTFrameError: If encoding fails
        """
        # Build header (without magic and length)
        header = struct.pack(
            '!BB8sQQI',
            self.frame_type,
            self.flags,
            self.session_id,
            self.sequence,
            self.timestamp,
            self.stream_id
        )
        
        # Add crypto metadata if present
        frame_body = header
        if self.crypto_metadata:
            meta_len = encode_varint(len(self.crypto_metadata))
            frame_body += meta_len + self.crypto_metadata
        else:
            # No metadata, encode zero length
            frame_body += encode_varint(0)
        
        # Add payload
        frame_body += self.payload
        
        # Calculate total length
        total_length = len(frame_body)
        
        if total_length > STT_MAX_FRAME_SIZE:
            raise STTFrameError(
                f"Frame size {total_length} exceeds maximum {STT_MAX_FRAME_SIZE}"
            )
        
        # Encode length as varint
        length_bytes = encode_varint(total_length)
        
        # Assemble complete frame
        frame = STT_MAGIC + length_bytes + frame_body
        
        return frame
    
    @classmethod
    def from_bytes(cls, data: bytes, decrypt: bool = False, 
                   stc_wrapper: Optional['STCWrapper'] = None) -> tuple['STTFrame', int]:
        """
        Decode frame from bytes.
        
        Args:
            data: Bytes containing frame data
            decrypt: Whether to decrypt payload immediately
            stc_wrapper: STCWrapper instance (required if decrypt=True)
            
        Returns:
            Tuple of (decoded frame, bytes consumed)
            
        Raises:
            STTFrameError: If decoding fails
        """
        if len(data) < 2:
            raise STTFrameError("Insufficient data for magic bytes")
        
        # Verify magic
        if data[:2] != STT_MAGIC:
            raise STTFrameError(
                f"Invalid magic bytes: expected {STT_MAGIC!r}, got {data[:2]!r}"
            )
        
        # Decode length
        try:
            total_length, varint_size = decode_varint(data, 2)
        except ValueError as e:
            raise STTFrameError(f"Failed to decode length: {e}")
        
        # Calculate header start and frame end
        header_offset = 2 + varint_size
        frame_end = header_offset + total_length
        
        if len(data) < frame_end:
            raise STTFrameError(
                f"Insufficient data: need {frame_end}, have {len(data)}"
            )
        
        # Parse header
        header_size = 1 + 1 + STT_SESSION_ID_LENGTH + STT_SEQUENCE_LENGTH + \
                      STT_TIMESTAMP_LENGTH + 4  # stream_id is 4 bytes
        
        if total_length < header_size:
            raise STTFrameError(f"Frame too small: {total_length} < {header_size}")
        
        header_data = data[header_offset:header_offset + header_size]
        
        try:
            frame_type, flags, session_id, sequence, timestamp, stream_id = struct.unpack(
                '!BB8sQQI',
                header_data
            )
        except struct.error as e:
            raise STTFrameError(f"Failed to parse header: {e}")
        
        # Parse crypto metadata
        meta_offset = header_offset + header_size
        try:
            meta_len, meta_varint_size = decode_varint(data, meta_offset)
        except ValueError as e:
            raise STTFrameError(f"Failed to decode metadata length: {e}")
        
        meta_offset += meta_varint_size
        
        if meta_len > 0:
            if meta_offset + meta_len > frame_end:
                raise STTFrameError("Metadata extends beyond frame")
            crypto_metadata = data[meta_offset:meta_offset + meta_len]
            meta_offset += meta_len
        else:
            crypto_metadata = None
        
        # Extract payload
        payload = data[meta_offset:frame_end]
        
        frame = cls(
            frame_type=frame_type,
            flags=flags,
            session_id=session_id,
            sequence=sequence,
            timestamp=timestamp,
            stream_id=stream_id,
            payload=payload,
            crypto_metadata=crypto_metadata,
            _is_encrypted=(crypto_metadata is not None)
        )
        
        # Decrypt if requested
        if decrypt and crypto_metadata:
            if stc_wrapper is None:
                raise STTFrameError("STCWrapper required for decryption")
            frame.decrypt_payload(stc_wrapper)
        
        return frame, frame_end
    
    def get_associated_data(self) -> bytes:
        """
        Get associated data for AEAD encryption.
        
        Returns:
            AD = type | flags | session_id | seq | timestamp | stream_id
        """
        return struct.pack(
            '!BB8sQQI',
            self.frame_type,
            self.flags,
            self.session_id,
            self.sequence,
            self.timestamp,
            self.stream_id,
        )
    
    @staticmethod
    def create_frame(
        frame_type: int,
        session_id: bytes,
        sequence: int,
        stream_id: int,
        payload: bytes,
        flags: int = 0,
        timestamp: Optional[int] = None,
    ) -> 'STTFrame':
        """
        Factory method to create a new frame.
        
        Args:
            frame_type: Frame type constant
            session_id: Session identifier (8 bytes)
            sequence: Sequence number
            stream_id: Stream identifier
            payload: Frame payload
            flags: Optional flags
            timestamp: Optional timestamp (uses current time if None)
            
        Returns:
            New STTFrame instance
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)  # Milliseconds
        
        return STTFrame(
            frame_type=frame_type,
            flags=flags,
            session_id=session_id,
            sequence=sequence,
            timestamp=timestamp,
            stream_id=stream_id,
            payload=payload,
        )
