"""
Stream manager for handling multiple streams within a session.
"""

import asyncio
from typing import Dict, Optional, List

from .stream import STTStream
from ..utils.constants import STT_STREAM_STATE_CLOSED
from ..utils.exceptions import STTStreamError
from ..utils.logging import get_logger


logger = get_logger(__name__)


class StreamManager:
    """Manages multiple streams within an STT session."""
    
    def __init__(self, session_id: bytes, stc_wrapper):
        """
        Initialize stream manager.
        
        Args:
            session_id: Session identifier
            stc_wrapper: STC wrapper for crypto operations
        """
        self.session_id = session_id
        self.stc_wrapper = stc_wrapper
        self.streams: Dict[int, STTStream] = {}
        self.next_stream_id: int = 1
        self._lock = asyncio.Lock()
    
    async def create_stream(self, stream_id: Optional[int] = None) -> STTStream:
        """
        Create a new stream.
        
        Args:
            stream_id: Optional stream ID (auto-assigned if None)
            
        Returns:
            New STTStream instance
        """
        async with self._lock:
            if stream_id is None:
                stream_id = self.next_stream_id
                self.next_stream_id += 2  # Odd for client, even for server
            
            stream = STTStream(
                stream_id=stream_id,
                session_id=self.session_id,
            )
            
            self.streams[stream_id] = stream
            
            logger.info(f"Created stream {stream_id} for session {self.session_id.hex()}")
            
            return stream
    
    def get_stream(self, stream_id: int) -> Optional[STTStream]:
        """
        Get stream by ID.
        
        Args:
            stream_id: Stream identifier
            
        Returns:
            STTStream or None if not found
        """
        return self.streams.get(stream_id)
    
    async def get_or_create_stream(self, stream_id: int) -> STTStream:
        """
        Get existing stream or create if doesn't exist.
        
        Args:
            stream_id: Stream identifier
            
        Returns:
            STTStream instance
        """
        async with self._lock:
            if stream_id in self.streams:
                return self.streams[stream_id]
            
            stream = STTStream(
                stream_id=stream_id,
                session_id=self.session_id,
            )
            
            self.streams[stream_id] = stream
            
            logger.info(
                f"Created peer-initiated stream {stream_id} "
                f"for session {self.session_id.hex()}"
            )
            
            return stream
    
    async def close_stream(self, stream_id: int) -> None:
        """
        Close a stream.
        
        Args:
            stream_id: Stream to close
        """
        stream = self.streams.get(stream_id)
        if stream:
            stream.close()
            logger.info(f"Closed stream {stream_id}")
    
    async def close_all_streams(self) -> None:
        """Close all streams in this session."""
        async with self._lock:
            for stream in self.streams.values():
                if not stream.is_closed():
                    stream.close()
            
            logger.info(
                f"Closed all {len(self.streams)} streams "
                f"for session {self.session_id.hex()}"
            )
    
    def get_active_streams(self) -> List[STTStream]:
        """Get list of currently active (non-closed) streams."""
        return [
            stream for stream in self.streams.values()
            if not stream.is_closed()
        ]
    
    def get_stream_count(self) -> int:
        """Get total number of streams."""
        return len(self.streams)
    
    def get_active_stream_count(self) -> int:
        """Get number of active streams."""
        return len(self.get_active_streams())
    
    async def cleanup_closed_streams(self) -> int:
        """
        Remove closed streams from manager.
        
        Returns:
            Number of streams removed
        """
        async with self._lock:
            closed_ids = [
                sid for sid, stream in self.streams.items()
                if stream.state == STT_STREAM_STATE_CLOSED
            ]
            
            for sid in closed_ids:
                del self.streams[sid]
            
            if closed_ids:
                logger.debug(f"Cleaned up {len(closed_ids)} closed streams")
            
            return len(closed_ids)
    
    def has_stream(self, stream_id: int) -> bool:
        """Check if stream exists."""
        return stream_id in self.streams
    
    async def close_all(self) -> None:
        """Close all streams (alias for close_all_streams)."""
        await self.close_all_streams()
    
    async def cleanup_inactive(self, timeout: float = 300) -> int:
        """Remove inactive streams (alias for cleanup_closed_streams)."""
        return await self.cleanup_closed_streams()
    
    def get_next_stream_id(self) -> int:
        """Get next available stream ID."""
        return self.next_stream_id
    
    def get_stats(self) -> dict:
        """Get statistics for all streams."""
        return {
            'session_id': self.session_id.hex(),
            'total_streams': len(self.streams),
            'active_streams': self.get_active_stream_count(),
            'streams': [stream.get_stats() for stream in self.streams.values()],
        }
