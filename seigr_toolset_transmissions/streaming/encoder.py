"""
Agnostic binary stream encoder - NO assumptions about data structure or semantics.

Supports:
- Live streaming (infinite, unbounded)
- Bounded streaming (known total size)
- Pure binary transport (user defines meaning)
"""

import asyncio
from typing import Optional, Callable, AsyncIterator
from interfaces.api.streaming_context import StreamingContext
from ..crypto.stc_wrapper import STCWrapper
from ..utils.exceptions import STTStreamingError


class BinaryStreamEncoder:
    """
    Agnostic binary stream encoder.
    
    NO assumptions about:
    - What bytes represent (files? messages? video? user decides)
    - Data structure (complete? partial? infinite? user decides)
    - Semantics (user defines everything)
    
    Provides:
    - Secure transport (STC encryption)
    - Sequential ordering (sequence numbers)
    - Segment division (transport-level MTU optimization)
    """
    
    def __init__(
        self,
        stc_wrapper: STCWrapper,
        session_id: bytes,
        stream_id: int,
        segment_size: int = 65536,
        mode: str = 'live'
    ):
        """
        Initialize binary stream encoder.
        
        Args:
            stc_wrapper: STC wrapper for cryptography
            session_id: Session identifier (8 bytes)
            stream_id: Stream identifier (4 bytes)
            segment_size: Transport segment size (MTU optimization only)
                         Default 65536 (64KB) balances throughput/latency
            mode: 'live' (infinite) or 'bounded' (known size)
        """
        if mode not in ('live', 'bounded'):
            raise STTStreamingError(f"Invalid mode: {mode}. Must be 'live' or 'bounded'")
        
        self.stc_wrapper = stc_wrapper
        self.session_id = session_id
        self.stream_id = stream_id
        self.segment_size = segment_size
        self.mode = mode
        
        # STC StreamingContext for encryption
        self.stream_context: StreamingContext = stc_wrapper.create_stream_context(
            session_id, stream_id
        )
        
        # Sequence tracking (transport-level ordering)
        self._sequence = 0
        self._total_bytes_sent = 0
        self._ended = False
        
        # Flow control (credit-based)
        self._credits = 100  # Can send 100 segments before waiting
        self._credit_event = asyncio.Event()
        self._credit_event.set()  # Initially can send
    
    async def send(self, data: bytes) -> AsyncIterator[dict]:
        """
        Send arbitrary bytes. Call repeatedly for continuous flow.
        
        For live streams: call indefinitely
        For bounded streams: call until all data sent, then call end()
        
        Args:
            data: Opaque bytes (could be 1 byte or 1GB, STT doesn't care)
        
        Yields:
            dict with 'data' (encrypted segment bytes), 'sequence' (int)
        
        Raises:
            STTStreamingError: If stream ended or data invalid
        
        Example:
            async for segment in encoder.send(b"binary data"):
                # segment = {'data': b'...', 'sequence': 0}
                await transport.transmit(segment['data'])
        """
        if self._ended:
            raise STTStreamingError("Cannot send after stream ended")
        
        if not isinstance(data, bytes):
            raise STTStreamingError("Data must be bytes")
        
        offset = 0
        
        # Split data into transport-optimized segments
        while offset < len(data):
            # Wait for flow control credits
            while self._credits <= 0:
                self._credit_event.clear()
                await self._credit_event.wait()
            
            # Extract segment (transport MTU size)
            segment = data[offset:offset + self.segment_size]
            
            # Encrypt segment with STC
            encrypted_segment = await self._encrypt_segment(segment)
            
            # Yield encrypted segment for transmission
            yield {
                'data': encrypted_segment,
                'sequence': self._sequence
            }
            
            offset += self.segment_size
            self._sequence += 1
            self._credits -= 1
        
        self._total_bytes_sent += len(data)
    
    async def end(self) -> Optional[dict]:
        """
        Signal end of bounded stream.
        
        For live streams: optional (stream can continue indefinitely)
        For bounded streams: MUST call after sending all data
        
        Returns:
            dict with end marker segment or None if already ended
        
        Raises:
            STTStreamingError: If mode is 'live' and end() called
        """
        if self.mode == 'live':
            raise STTStreamingError("Cannot end live stream (infinite mode)")
        
        if self._ended:
            return None  # Already ended
        
        # Create end-of-stream marker (empty segment)
        end_marker = await self._encrypt_segment(b"")
        self._ended = True
        
        return {
            'data': end_marker,
            'sequence': self._sequence,
            'is_end': True
        }
    
    async def _encrypt_segment(self, segment: bytes) -> bytes:
        """
        Encrypt segment with STC.
        
        Args:
            segment: Bytes to encrypt (transport MTU size)
        
        Returns:
            Encrypted segment ready for transmission
            Format: [empty_flag(1)] [header(16)] [encrypted_data]
        """
        # Handle empty segments (end markers)
        is_empty = len(segment) == 0
        encrypt_data = b'\x00' if is_empty else segment
        
        # Seigr Toolset Crypto v0.4.1: encrypt uses STC StreamingContext
        header_obj, encrypted = self.stream_context.encrypt_chunk(encrypt_data)
        header_bytes = header_obj.to_bytes()  # 16-byte fixed header
        
        # Format: [empty_flag(1)] [header(16)] [encrypted_data]
        flag = b'\x01' if is_empty else b'\x00'
        encoded_segment = flag + header_bytes + encrypted
        
        return encoded_segment
    
    def add_credits(self, credits: int) -> None:
        """
        Add flow control credits (called by peer).
        
        Args:
            credits: Number of segments peer can receive
        """
        self._credits += credits
        if self._credits > 0:
            self._credit_event.set()
    
    def get_stats(self) -> dict:
        """
        Get encoder statistics.
        
        Returns:
            dict with sequence, bytes_sent, mode, ended status
        """
        return {
            'sequence': self._sequence,
            'bytes_sent': self._total_bytes_sent,
            'mode': self.mode,
            'ended': self._ended,
            'credits': self._credits
        }
    
    def reset(self) -> None:
        """Reset encoder state (creates new StreamingContext)."""
        self.stream_context = self.stc_wrapper.create_stream_context(
            self.session_id, self.stream_id
        )
        self._sequence = 0
        self._total_bytes_sent = 0
        self._ended = False
        self._credits = 100
        self._credit_event.set()


# Backwards compatibility alias (deprecated)
StreamEncoder = BinaryStreamEncoder
