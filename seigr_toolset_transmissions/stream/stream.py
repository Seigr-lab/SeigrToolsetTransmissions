"""
Stream management for STT multiplexed binary channels.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from ..utils.constants import (
    STT_STREAM_STATE_IDLE,
    STT_STREAM_STATE_OPEN,
    STT_STREAM_STATE_HALF_CLOSED,
    STT_STREAM_STATE_CLOSED,
    STT_INITIAL_STREAM_CREDIT,
    STT_FLAG_STREAM_INIT,
    STT_FLAG_STREAM_CHUNK,
    STT_FLAG_STREAM_END,
)
from ..utils.exceptions import STTStreamError, STTFlowControlError
from ..utils.logging import get_logger


logger = get_logger(__name__)


@dataclass
class STTStream:
    """
    Represents a multiplexed binary stream within a session.
    """
    
    stream_id: int
    session_id: bytes
    state: int = STT_STREAM_STATE_IDLE
    send_credit: int = STT_INITIAL_STREAM_CREDIT
    recv_credit: int = STT_INITIAL_STREAM_CREDIT
    bytes_sent: int = 0
    bytes_received: int = 0
    chunks_sent: int = 0
    chunks_received: int = 0
    send_buffer: asyncio.Queue = field(default_factory=lambda: asyncio.Queue())
    recv_buffer: asyncio.Queue = field(default_factory=lambda: asyncio.Queue())
    _closed_event: asyncio.Event = field(default_factory=asyncio.Event)
    
    def __post_init__(self) -> None:
        """Initialize stream state."""
        if self.stream_id < 0:
            raise STTStreamError("Stream ID must be non-negative")
    
    async def send(self, data: bytes) -> None:
        """
        Queue data for sending on this stream.
        
        Args:
            data: Binary data to send
            
        Raises:
            STTStreamError: If stream is not in sendable state
            STTFlowControlError: If insufficient send credit
        """
        if self.state not in (STT_STREAM_STATE_OPEN, STT_STREAM_STATE_IDLE):
            raise STTStreamError(
                f"Cannot send on stream in state {self.state}"
            )
        
        if len(data) > self.send_credit:
            raise STTFlowControlError(
                f"Insufficient send credit: need {len(data)}, have {self.send_credit}"
            )
        
        await self.send_buffer.put(data)
        self.send_credit -= len(data)
        self.bytes_sent += len(data)
        self.chunks_sent += 1
        
        if self.state == STT_STREAM_STATE_IDLE:
            self.state = STT_STREAM_STATE_OPEN
        
        logger.debug(
            f"Stream {self.stream_id}: queued {len(data)} bytes, "
            f"credit remaining: {self.send_credit}"
        )
    
    async def receive(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """
        Receive data from this stream.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            Received data or None if timeout/closed
        """
        if self.state == STT_STREAM_STATE_CLOSED:
            return None
        
        try:
            if timeout is None:
                data = await self.recv_buffer.get()
            else:
                data = await asyncio.wait_for(
                    self.recv_buffer.get(),
                    timeout=timeout
                )
            
            self.bytes_received += len(data)
            self.chunks_received += 1
            
            logger.debug(
                f"Stream {self.stream_id}: received {len(data)} bytes"
            )
            
            return data
            
        except asyncio.TimeoutError:
            return None
    
    async def put_received_data(self, data: bytes) -> None:
        """
        Put received data into the stream's receive buffer.
        
        Args:
            data: Received binary data
            
        Raises:
            STTFlowControlError: If insufficient receive credit
        """
        if len(data) > self.recv_credit:
            raise STTFlowControlError(
                f"Received data exceeds credit: {len(data)} > {self.recv_credit}"
            )
        
        await self.recv_buffer.put(data)
        self.recv_credit -= len(data)
        
        if self.state == STT_STREAM_STATE_IDLE:
            self.state = STT_STREAM_STATE_OPEN
    
    def add_send_credit(self, amount: int) -> None:
        """Add to send credit (from peer flow control message)."""
        self.send_credit += amount
        logger.debug(f"Stream {self.stream_id}: added {amount} send credit")
    
    def add_recv_credit(self, amount: int) -> None:
        """Add to receive credit (local decision)."""
        self.recv_credit += amount
        logger.debug(f"Stream {self.stream_id}: added {amount} recv credit")
    
    async def close(self) -> None:
        """Close the stream."""
        if self.state != STT_STREAM_STATE_CLOSED:
            self.state = STT_STREAM_STATE_CLOSED
            self._closed_event.set()
            logger.info(f"Stream {self.stream_id}: closed")
    
    async def wait_closed(self) -> None:
        """Wait for stream to be closed."""
        await self._closed_event.wait()
    
    def is_open(self) -> bool:
        """Check if stream is open for communication."""
        return self.state == STT_STREAM_STATE_OPEN
    
    def is_closed(self) -> bool:
        """Check if stream is closed."""
        return self.state == STT_STREAM_STATE_CLOSED
    
    def get_stats(self) -> dict:
        """Get stream statistics."""
        return {
            'stream_id': self.stream_id,
            'state': self.state,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'chunks_sent': self.chunks_sent,
            'chunks_received': self.chunks_received,
            'send_credit': self.send_credit,
            'recv_credit': self.recv_credit,
        }
