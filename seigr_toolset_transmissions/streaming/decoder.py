"""
Agnostic binary stream decoder - NO assumptions about data structure or semantics.

Handles:
- Out-of-order segment arrival
- Continuous byte flow (AsyncIterator)
- Pure binary decryption (user interprets bytes)
"""

import asyncio
from typing import Dict, Optional, AsyncIterator
from interfaces.api.streaming_context import StreamingContext, ChunkHeader
from ..crypto.stc_wrapper import STCWrapper
from ..utils.exceptions import STTStreamingError


class BinaryStreamDecoder:
    """
    Agnostic binary stream decoder.
    
    NO assumptions about:
    - What bytes represent (user interprets)
    - Data structure (user decides)
    - Semantics (user defines)
    
    Provides:
    - Secure decryption (STC)
    - Sequential ordering (reorders out-of-order segments)
    - Continuous flow (AsyncIterator for live streams)
    """
    
    def __init__(
        self,
        stc_wrapper: STCWrapper,
        session_id: bytes,
        stream_id: int
    ):
        """
        Initialize binary stream decoder.
        
        Args:
            stc_wrapper: STC wrapper for cryptography
            session_id: Session identifier (8 bytes)
            stream_id: Stream identifier (4 bytes)
        """
        self.stc_wrapper = stc_wrapper
        self.session_id = session_id
        self.stream_id = stream_id
        
        # STC StreamingContext for decryption
        self.stream_context: StreamingContext = stc_wrapper.create_stream_context(
            session_id, stream_id
        )
        
        # Segment reordering buffer (sequence -> decrypted_bytes)
        self._segment_buffer: Dict[int, bytes] = {}
        self._next_expected_sequence = 0
        
        # Stream state
        self._ended = False
        self._total_bytes_received = 0
        
        # Async segment queue (for receive() iterator)
        self._segment_queue: asyncio.Queue = asyncio.Queue()
    
    async def receive(self) -> AsyncIterator[bytes]:
        """
        Receive bytes as they arrive (in order).
        
        Infinite async iterator - continues until:
        - Stream ends (bounded mode)
        - Connection closes
        - Error occurs
        
        Yields:
            bytes: Decrypted segment data (opaque, user interprets)
        
        Example:
            async for bytes in decoder.receive():
                # Process bytes as they arrive
                # Could be anything - video, sensor data, messages, etc.
                user_process(bytes)
        """
        while True:
            # Get next in-order segment
            segment = await self._segment_queue.get()
            
            # Check for end marker
            if segment is None:
                break  # Stream ended
            
            yield segment
    
    async def receive_all(self) -> bytes:
        """
        Receive all bytes from bounded stream.
        
        ONLY use for bounded streams (known to end).
        For live streams, this will block indefinitely.
        
        Returns:
            bytes: All received data concatenated
        
        Example:
            data = await decoder.receive_all()  # Bounded stream only
        """
        buffer = bytearray()
        
        async for segment in self.receive():
            buffer.extend(segment)
        
        return bytes(buffer)
    
    async def process_segment(self, encoded_segment: bytes, sequence: int) -> None:
        """
        Process received encrypted segment.
        
        Handles out-of-order arrival by buffering and reordering.
        
        Args:
            encoded_segment: Encrypted segment from transport
                            Format: [empty_flag(1)] [header(16)] [encrypted_data]
            sequence: Segment sequence number
        
        Raises:
            STTStreamingError: If segment corrupted or decryption fails
        """
        try:
            # Decrypt segment
            decrypted = await self._decrypt_segment(encoded_segment)
            
            # Add to buffer
            self._segment_buffer[sequence] = decrypted
            self._total_bytes_received += len(decrypted)
            
            # Yield all in-order segments
            while self._next_expected_sequence in self._segment_buffer:
                segment_data = self._segment_buffer.pop(self._next_expected_sequence)
                await self._segment_queue.put(segment_data)
                self._next_expected_sequence += 1
        
        except Exception as e:
            raise STTStreamingError(f"Failed to process segment {sequence}: {e}")
    
    async def _decrypt_segment(self, encoded_segment: bytes) -> bytes:
        """
        Decrypt single segment.
        
        Args:
            encoded_segment: Format [empty_flag(1)] [header(16)] [encrypted_data]
        
        Returns:
            Decrypted bytes
        """
        if not isinstance(encoded_segment, bytes):
            raise STTStreamingError("Encoded segment must be bytes")
        
        if len(encoded_segment) < 17:  # 1 byte flag + 16 bytes header minimum
            raise STTStreamingError("Encoded segment too short")
        
        # Parse segment
        empty_flag = encoded_segment[0]
        header_bytes = encoded_segment[1:17]  # 16-byte fixed header
        encrypted = encoded_segment[17:]
        
        # Decrypt with Seigr Toolset Crypto v0.4.1
        header_obj = ChunkHeader.from_bytes(header_bytes)
        decrypted = self.stream_context.decrypt_chunk(header_obj, encrypted)
        
        # Handle empty flag
        if empty_flag == 0x01:
            return b""
        
        return decrypted
    
    def signal_end(self) -> None:
        """
        Signal end of stream (bounded mode).
        
        Stops receive() iterator.
        Call this after processing all segments from a bounded stream.
        """
        if not self._ended:
            self._ended = True
            # Put end marker in queue (non-blocking)
            self._segment_queue.put_nowait(None)
    
    def get_buffered_count(self) -> int:
        """
        Get number of out-of-order segments in buffer.
        
        Returns:
            Count of buffered segments waiting for reordering
        """
        return len(self._segment_buffer)
    
    def get_stats(self) -> dict:
        """
        Get decoder statistics.
        
        Returns:
            dict with sequence, bytes_received, buffered segments, ended status
        """
        return {
            'next_expected': self._next_expected_sequence,
            'bytes_received': self._total_bytes_received,
            'buffered_segments': len(self._segment_buffer),
            'ended': self._ended
        }
    
    def reset(self) -> None:
        """Reset decoder state (creates new StreamingContext)."""
        self.stream_context = self.stc_wrapper.create_stream_context(
            self.session_id, self.stream_id
        )
        self._segment_buffer.clear()
        self._next_expected_sequence = 0
        self._ended = False
        self._total_bytes_received = 0
        # Clear queue
        while not self._segment_queue.empty():
            try:
                self._segment_queue.get_nowait()
            except asyncio.QueueEmpty:
                break


# Backwards compatibility alias (deprecated)
StreamDecoder = BinaryStreamDecoder
