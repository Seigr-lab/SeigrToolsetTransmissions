"""
STT Frame structure and encoding/decoding.
"""

import struct
import time
from dataclasses import dataclass
from typing import Optional

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


@dataclass
class STTFrame:
    """
    Represents an STT protocol frame.
    
    Frame Structure:
    | Magic (2) | Length (varint) | Type (1) | Flags (1) |
    | Session ID (8) | Seq (8) | Timestamp (8) | Reserved (2) |
    | Payload (variable) |
    """
    
    frame_type: int
    flags: int
    session_id: bytes
    sequence: int
    timestamp: int
    payload: bytes
    
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
    
    def to_bytes(self) -> bytes:
        """
        Encode frame to bytes.
        
        Returns:
            Encoded frame bytes
            
        Raises:
            STTFrameError: If encoding fails
        """
        # Build header (without magic and length)
        header = struct.pack(
            '!BB8sQQH',
            self.frame_type,
            self.flags,
            self.session_id,
            self.sequence,
            self.timestamp,
            0  # Reserved
        )
        
        # Calculate total length (header + payload)
        total_length = len(header) + len(self.payload)
        
        if total_length > STT_MAX_FRAME_SIZE:
            raise STTFrameError(
                f"Frame size {total_length} exceeds maximum {STT_MAX_FRAME_SIZE}"
            )
        
        # Encode length as varint
        length_bytes = encode_varint(total_length)
        
        # Assemble complete frame
        frame = STT_MAGIC + length_bytes + header + self.payload
        
        return frame
    
    @classmethod
    def from_bytes(cls, data: bytes) -> tuple['STTFrame', int]:
        """
        Decode frame from bytes.
        
        Args:
            data: Bytes containing frame data
            
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
                      STT_TIMESTAMP_LENGTH + STT_RESERVED_LENGTH
        
        if total_length < header_size:
            raise STTFrameError(f"Frame too small: {total_length} < {header_size}")
        
        header_data = data[header_offset:header_offset + header_size]
        
        try:
            frame_type, flags, session_id, sequence, timestamp, _ = struct.unpack(
                '!BB8sQQH',
                header_data
            )
        except struct.error as e:
            raise STTFrameError(f"Failed to parse header: {e}")
        
        # Extract payload
        payload_offset = header_offset + header_size
        payload = data[payload_offset:frame_end]
        
        frame = cls(
            frame_type=frame_type,
            flags=flags,
            session_id=session_id,
            sequence=sequence,
            timestamp=timestamp,
            payload=payload,
        )
        
        return frame, frame_end
    
    def get_associated_data(self) -> bytes:
        """
        Get associated data for AEAD encryption.
        
        Returns:
            AD = type | flags | session_id | seq | timestamp
        """
        return struct.pack(
            '!BB8sQQ',
            self.frame_type,
            self.flags,
            self.session_id,
            self.sequence,
            self.timestamp,
        )
    
    @staticmethod
    def create_frame(
        frame_type: int,
        session_id: bytes,
        sequence: int,
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
            payload=payload,
        )
