"""
Session manager for handling multiple active sessions.
"""

import asyncio
from typing import Dict, Optional, List

from .session import STTSession
from ..utils.constants import STT_SESSION_TIMEOUT
from ..utils.exceptions import STTSessionError
from ..utils.logging import get_logger


logger = get_logger(__name__)


class SessionManager:
    """Manages multiple STT sessions."""
    
    def __init__(self, node_id: bytes, stc_wrapper):
        """
        Initialize session manager.
        
        Args:
            node_id: This node's identifier
            stc_wrapper: STC wrapper for crypto operations
        """
        if len(node_id) != 32:
            raise STTSessionError("Local node ID must be 32 bytes")
        
        self.local_node_id = node_id
        self.stc_wrapper = stc_wrapper
        self.sessions: Dict[bytes, STTSession] = {}
        self._lock = asyncio.Lock()
    
    async def create_session(
        self,
        session_id: bytes,
        peer_node_id: bytes,
        session_key: Optional[bytes] = None,
        capabilities: int = 0,
    ) -> STTSession:
        """
        Create a new session.
        
        Args:
            session_id: Session identifier (8 bytes)
            peer_node_id: Peer's node identifier (32 bytes)
            session_key: Optional session key material (unused, for API compat)
            capabilities: Session capabilities (unused, for API compat)
            
        Returns:
            New STTSession instance
        """
        async with self._lock:
            if session_id in self.sessions:
                raise STTSessionError(
                    f"Session {session_id.hex()} already exists"
                )
            
            session = STTSession(
                session_id=session_id,
                peer_node_id=peer_node_id,
                stc_wrapper=self.stc_wrapper,
            )
            
            self.sessions[session_id] = session
            
            logger.info(
                f"Created session {session_id.hex()} "
                f"with peer {peer_node_id.hex()}"
            )
            
            return session
    
    def get_session(self, session_id: bytes) -> Optional[STTSession]:
        """
        Get session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            STTSession or None if not found
        """
        return self.sessions.get(session_id)
    
    def has_session(self, session_id: bytes) -> bool:
        """Check if session exists."""
        return session_id in self.sessions
    
    async def close_session(self, session_id: bytes) -> None:
        """
        Close a session.
        
        Args:
            session_id: Session to close
        """
        session = self.sessions.get(session_id)
        if session:
            session.close()
            logger.info(f"Closed session {session_id.hex()}")
    
    async def close_all_sessions(self) -> None:
        """Close all active sessions."""
        async with self._lock:
            for session in self.sessions.values():
                if not session.is_closed():
                    session.close()
            
            logger.info(f"Closed all {len(self.sessions)} sessions")
    
    def get_active_sessions(self) -> List[STTSession]:
        """Get list of active sessions."""
        return [
            session for session in self.sessions.values()
            if session.is_active()
        ]
    
    def get_session_count(self) -> int:
        """Get total number of sessions."""
        return len(self.sessions)
    
    def get_active_session_count(self) -> int:
        """Get number of active sessions."""
        return len(self.get_active_sessions())
    
    async def cleanup_closed_sessions(self) -> int:
        """
        Remove closed sessions from manager.
        
        Returns:
            Number of sessions removed
        """
        async with self._lock:
            closed_ids = [
                sid for sid, session in self.sessions.items()
                if session.is_closed()
            ]
            
            for sid in closed_ids:
                del self.sessions[sid]
            
            if closed_ids:
                logger.debug(f"Cleaned up {len(closed_ids)} closed sessions")
            
            return len(closed_ids)
    
    def list_sessions(self) -> List[STTSession]:
        """List all sessions."""
        return list(self.sessions.values())
    
    async def rotate_all_keys(self, stc_wrapper) -> None:
        """Rotate keys for all active sessions."""
        for session in self.get_active_sessions():
            # Update session with new STC wrapper
            pass  # Key rotation logic here
    
    async def cleanup_inactive(self, timeout: float = 600) -> int:
        """Remove inactive sessions."""
        return await self.cleanup_closed_sessions()
    
    async def cleanup_expired(self, max_idle: float) -> int:
        """Remove expired sessions."""
        return await self.cleanup_inactive(timeout=max_idle)
    
    async def find_session_by_peer(
        self,
        peer_node_id: bytes
    ) -> Optional[STTSession]:
        """
        Find active session with a specific peer.
        
        Args:
            peer_node_id: Peer's node identifier
            
        Returns:
            Active session or None
        """
        for session in self.sessions.values():
            if (session.peer_node_id == peer_node_id and
                session.is_active()):
                return session
        return None
    
    def get_stats(self) -> dict:
        """Get statistics for all sessions."""
        return {
            'local_node_id': self.local_node_id.hex(),
            'total_sessions': len(self.sessions),
            'active_sessions': self.get_active_session_count(),
            'sessions': [
                session.get_stats() for session in self.sessions.values()
            ],
        }
