"""
STT Stream management for multiplexed data streams.
"""

import asyncio
import time
from typing import Optional, Dict, List
from collections import deque

from ..crypto.stc_wrapper import STCWrapper
from ..utils.exceptions import STTStreamError


class STTStream:
    """
    Multiplexed stream within an STT session.
    """
    
    def __init__(self, session_id: bytes, stream_id: int, stc_wrapper: STCWrapper):
        """
        Initialize stream.
        
        Args:
            session_id: Parent session identifier
            stream_id: Unique stream identifier within session
            stc_wrapper: STC wrapper for stream encryption
        """
        self.session_id = session_id
        self.stream_id = stream_id
        self.stc_wrapper = stc_wrapper
        
        # Stream state
        self.is_active = True
        self.sequence = 0
        self.created_at = time.time()
        self.last_activity = time.time()
        
        # Flow control
        self.send_window = 65536  # 64KB initial window
        self.receive_window = 65536
        
        # Statistics
        self.bytes_sent = 0
        self.bytes_received = 0
        self.messages_sent = 0
        self.messages_received = 0
        
        # Buffering
        self.receive_buffer = deque()
        self.send_buffer = deque()
        
        # Sequence tracking for ordered delivery
        self.expected_sequence = 0
        self.out_of_order_buffer: Dict[int, bytes] = {}
        
        # Async support
        self._receive_event = asyncio.Event()
    
    async def send(self, data: bytes) -> None:
        """
        Send data on stream.
        
        Args:
            data: Data to send
        """
        if not self.is_active:
            raise STTStreamError("Stream is closed")
        
        # Update statistics
        self.bytes_sent += len(data)
        self.messages_sent += 1
        self.sequence += 1
        self.last_activity = time.time()
        
        # In real implementation, this would create frames and send
        # For now, just update stats
        await asyncio.sleep(0)  # Yield control
    
    async def receive(self, timeout: Optional[float] = None) -> bytes:
        """
        Receive data from stream.
        
        Args:
            timeout: Receive timeout in seconds
            
        Returns:
            Received data
        """
        if not self.is_active:
            raise STTStreamError("Stream is closed")
        
        # Wait for data with timeout
        try:
            if timeout:
                await asyncio.wait_for(self._receive_event.wait(), timeout)
            else:
                await self._receive_event.wait()
        except asyncio.TimeoutError:
            raise STTStreamError("Receive timeout")
        
        # Get data from buffer
        if self.receive_buffer:
            data = self.receive_buffer.popleft()
            self.bytes_received += len(data)
            self.messages_received += 1
            self.last_activity = time.time()
            
            # Clear event if buffer empty
            if not self.receive_buffer:
                self._receive_event.clear()
            
            return data
        
        return b''
    
    def _deliver_data(self, data: bytes) -> None:
        """
        Internal method to deliver received data to buffer.
        
        Args:
            data: Received data
        """
        self.receive_buffer.append(data)
        self._receive_event.set()
    
    async def _handle_incoming(self, data: bytes, sequence: int) -> None:
        """
        Handle incoming data with sequence ordering.
        
        Args:
            data: Received data
            sequence: Sequence number for ordering
        """
        if not self.is_active:
            raise STTStreamError("Stream is closed")
        
        self.last_activity = time.time()
        
        # Check if this is the expected sequence
        if sequence == self.expected_sequence:
            # Deliver in order
            self._deliver_data(data)
            self.expected_sequence += 1
            
            # Check if we have buffered out-of-order messages that can now be delivered
            while self.expected_sequence in self.out_of_order_buffer:
                buffered_data = self.out_of_order_buffer.pop(self.expected_sequence)
                self._deliver_data(buffered_data)
                self.expected_sequence += 1
        elif sequence > self.expected_sequence:
            # Future sequence - buffer it
            self.out_of_order_buffer[sequence] = data
        # else: duplicate or old sequence - ignore
    
    def is_expired(self, max_idle: float) -> bool:
        """
        Check if stream has expired due to inactivity.
        
        Args:
            max_idle: Maximum idle time in seconds
            
        Returns:
            True if stream has been idle longer than max_idle
        """
        return (time.time() - self.last_activity) > max_idle
    
    @property
    def receive_window_size(self) -> int:
        """Get current receive window size."""
        return self.receive_window
    
    def receive_buffer_empty(self) -> bool:
        """Check if receive buffer is empty."""
        return len(self.receive_buffer) == 0
    
    def close(self) -> None:
        """Close stream."""
        self.is_active = False
        self._receive_event.set()  # Wake up any waiters
    
    def get_stats(self) -> Dict:
        """Get stream statistics."""
        return {
            'session_id': self.session_id.hex(),
            'stream_id': self.stream_id,
            'is_active': self.is_active,
            'sequence': self.sequence,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'messages_sent': self.messages_sent,
            'messages_received': self.messages_received,
            'send_window': self.send_window,
            'receive_window': self.receive_window,
        }
    
    def get_statistics(self) -> Dict:
        """Get stream statistics (alias for compatibility)."""
        return self.get_stats()


class StreamManager:
    """Manages multiple streams within a session."""
    
    def __init__(self, session_id: bytes, stc_wrapper: STCWrapper):
        """
        Initialize stream manager.
        
        Args:
            session_id: Parent session identifier
            stc_wrapper: STC wrapper for crypto
        """
        self.session_id = session_id
        self.stc_wrapper = stc_wrapper
        self.streams: Dict[int, STTStream] = {}
        self.next_stream_id = 1
    
    async def create_stream(self, stream_id: Optional[int] = None) -> STTStream:
        """
        Create new stream.
        
        Args:
            stream_id: Optional stream ID (auto-assigned if None)
            
        Returns:
            New stream instance
        """
        if stream_id is None:
            stream_id = self.next_stream_id
            self.next_stream_id += 1
        
        if stream_id in self.streams:
            raise STTStreamError(f"Stream {stream_id} already exists")
        
        stream = STTStream(self.session_id, stream_id, self.stc_wrapper)
        self.streams[stream_id] = stream
        return stream
    
    def get_stream(self, stream_id: int) -> Optional[STTStream]:
        """Get stream by ID."""
        return self.streams.get(stream_id)
    
    def close_stream(self, stream_id: int) -> None:
        """Close and remove stream."""
        stream = self.streams.get(stream_id)
        if stream:
            stream.close()
            del self.streams[stream_id]
    
    def has_stream(self, stream_id: int) -> bool:
        """Check if stream exists."""
        return stream_id in self.streams
    
    async def close_all(self) -> None:
        """Close all streams."""
        for stream in list(self.streams.values()):
            stream.close()
        self.streams.clear()
    
    def list_streams(self) -> List[int]:
        """List all stream IDs."""
        return list(self.streams.keys())
    
    async def cleanup_inactive(self, timeout: float = 300) -> int:
        """
        Remove inactive streams.
        
        Args:
            timeout: Inactivity timeout in seconds
            
        Returns:
            Number of streams cleaned up
        """
        now = time.time()
        to_remove = []
        
        for stream_id, stream in self.streams.items():
            if not stream.is_active or (now - stream.last_activity) > timeout:
                to_remove.append(stream_id)
        
        for stream_id in to_remove:
            self.close_stream(stream_id)
        
        return len(to_remove)
    
    def get_next_stream_id(self) -> int:
        """Get next available stream ID."""
        return self.next_stream_id
