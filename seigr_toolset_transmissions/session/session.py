"""
STT Session management with STC-based key rotation.
"""

import time
from typing import Optional, Dict

from ..crypto.stc_wrapper import STCWrapper
from ..utils.exceptions import STTSessionError


class STTSession:
    """
    STT session with cryptographic state and key rotation.
    """
    
    def __init__(self, session_id: bytes, peer_node_id: bytes, stc_wrapper: STCWrapper, metadata: Optional[Dict] = None):
        """
        Initialize session.
        
        Args:
            session_id: Unique session identifier (8 bytes)
            peer_node_id: Peer's node identifier
            stc_wrapper: STC wrapper for crypto operations
            metadata: Optional metadata dictionary
        """
        if len(session_id) != 8:
            raise STTSessionError(f"Session ID must be 8 bytes, got {len(session_id)}")
        
        self.session_id = session_id
        self.peer_node_id = peer_node_id
        self.stc_wrapper = stc_wrapper
        
        # Session state
        self.is_active = True
        self.key_version = 0
        self.created_at = time.time()
        self.last_activity = time.time()
        
        # Statistics
        self.bytes_sent = 0
        self.bytes_received = 0
        self.frames_sent = 0
        self.frames_received = 0
        
        # Metadata
        self.metadata: Dict = metadata if metadata is not None else {}
    
    def rotate_keys(self, stc_wrapper: STCWrapper) -> None:
        """
        Rotate session keys.
        
        Args:
            stc_wrapper: STC wrapper (may be updated context)
        """
        # Increment key version
        self.key_version += 1
        
        # Update wrapper if different
        if stc_wrapper is not self.stc_wrapper:
            self.stc_wrapper = stc_wrapper
        
        self.last_activity = time.time()
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()
    
    def record_frame_sent(self, size: int) -> None:
        """Record sent frame statistics."""
        self.frames_sent += 1
        self.bytes_sent += size
        self.update_activity()
    
    def record_frame_received(self, size: int) -> None:
        """Record received frame statistics."""
        self.frames_received += 1
        self.bytes_received += size
        self.update_activity()
    
    def record_sent_bytes(self, size: int) -> None:
        """Record sent bytes (alias for compatibility)."""
        self.bytes_sent += size
        self.update_activity()
    
    def record_received_bytes(self, size: int) -> None:
        """Record received bytes (alias for compatibility)."""
        self.bytes_received += size
        self.update_activity()
    
    def close(self) -> None:
        """Close session."""
        self.is_active = False
    
    def is_closed(self) -> bool:
        """Check if session is closed."""
        return not self.is_active
    
    def get_stats(self) -> Dict:
        """Get session statistics."""
        return {
            'session_id': self.session_id.hex(),
            'peer_node_id': self.peer_node_id.hex(),
            'key_version': self.key_version,
            'is_active': self.is_active,
            'uptime': time.time() - self.created_at,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'frames_sent': self.frames_sent,
            'frames_received': self.frames_received,
        }
    
    def get_statistics(self) -> Dict:
        """Get session statistics (alias for compatibility)."""
        return self.get_stats()
    
    def is_active_method(self) -> bool:
        """Check if session is active (method version)."""
        return self.is_active


class SessionManager:
    """Manages multiple sessions."""
    
    def __init__(self, node_id: bytes, stc_wrapper: STCWrapper):
        """
        Initialize session manager.
        
        Args:
            node_id: This node's identifier
            stc_wrapper: STC wrapper for crypto
        """
        self.node_id = node_id
        self.stc_wrapper = stc_wrapper
        self.sessions: Dict[bytes, STTSession] = {}
    
    async def create_session(self, session_id: bytes, peer_node_id: bytes) -> STTSession:
        """Create new session."""
        session = STTSession(session_id, peer_node_id, self.stc_wrapper)
        self.sessions[session_id] = session
        return session
    
    def get_session(self, session_id: bytes) -> Optional[STTSession]:
        """Get session by ID."""
        return self.sessions.get(session_id)
    
    def close_session(self, session_id: bytes) -> None:
        """Close and remove session."""
        session = self.sessions.get(session_id)
        if session:
            session.close()
            del self.sessions[session_id]
    
    def has_session(self, session_id: bytes) -> bool:
        """Check if session exists."""
        return session_id in self.sessions
    
    async def rotate_all_keys(self, stc_wrapper: STCWrapper) -> None:
        """Rotate keys for all active sessions."""
        for session in self.sessions.values():
            if session.is_active:
                session.rotate_keys(stc_wrapper)
    
    def list_sessions(self) -> list:
        """List all session IDs."""
        return list(self.sessions.keys())
    
    async def cleanup_inactive(self, timeout: float = 600) -> int:
        """
        Remove inactive sessions.
        
        Args:
            timeout: Inactivity timeout in seconds
            
        Returns:
            Number of sessions cleaned up
        """
        now = time.time()
        to_remove = []
        
        for session_id, session in self.sessions.items():
            if not session.is_active or (now - session.last_activity) > timeout:
                to_remove.append(session_id)
        
        for session_id in to_remove:
            self.close_session(session_id)
        
        return len(to_remove)
    
    async def cleanup_expired(self, max_idle: float) -> int:
        """
        Remove expired sessions based on idle time.
        
        Args:
            max_idle: Maximum idle time in seconds
            
        Returns:
            Number of sessions removed
        """
        return await self.cleanup_inactive(timeout=max_idle)
