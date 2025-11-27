"""
STT Session management with STC-based key rotation.
"""

import time
from typing import Optional, Dict, TYPE_CHECKING

from ..crypto.stc_wrapper import STCWrapper
from ..utils.exceptions import STTSessionError

if TYPE_CHECKING:
    from .continuity import CryptoSessionContinuity


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
        self.session_key: Optional[bytes] = None
        self.created_at = time.time()
        self.last_activity = time.time()
        
        # Peer transport address (for sending)
        self.peer_addr: Optional[tuple] = None  # (ip, port)
        self.transport_type: Optional[str] = None  # 'udp' or 'websocket'
        
        # Statistics
        self.bytes_sent = 0
        self.bytes_received = 0
        self.frames_sent = 0
        self.frames_received = 0
        
        # Performance metrics
        self.rtt_samples = []  # Rolling window of RTT measurements
        self.max_rtt_samples = 100
        self.frame_send_times = {}  # frame_id -> send_timestamp
        self.encryption_time_total = 0.0
        self.decryption_time_total = 0.0
        self.encryption_ops = 0
        self.decryption_ops = 0
        
        # Throughput tracking
        self.throughput_window = []  # (timestamp, bytes) tuples
        self.throughput_window_size = 10  # seconds
        
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
    
    def record_frame_sent(self, size: int, frame_id: Optional[int] = None) -> None:
        """Record sent frame statistics and start RTT tracking."""
        self.frames_sent += 1
        self.bytes_sent += size
        
        # Track for throughput calculation
        current_time = time.time()
        self.throughput_window.append((current_time, size))
        
        # Clean old entries
        cutoff = current_time - self.throughput_window_size
        self.throughput_window = [(t, s) for t, s in self.throughput_window if t > cutoff]
        
        # Track frame send time for RTT calculation
        if frame_id is not None:
            self.frame_send_times[frame_id] = current_time
        
        self.update_activity()
    
    def record_frame_received(self, size: int, frame_id: Optional[int] = None) -> None:
        """Record received frame statistics and calculate RTT if applicable."""
        self.frames_received += 1
        self.bytes_received += size
        
        # Calculate RTT if this is a response to our frame
        if frame_id is not None and frame_id in self.frame_send_times:
            rtt = time.time() - self.frame_send_times[frame_id]
            self.rtt_samples.append(rtt)
            
            # Keep only recent samples
            if len(self.rtt_samples) > self.max_rtt_samples:
                self.rtt_samples = self.rtt_samples[-self.max_rtt_samples:]
            
            # Clean up send time
            del self.frame_send_times[frame_id]
        
        self.update_activity()
    
    def record_encryption(self, duration: float) -> None:
        """Record encryption operation timing."""
        self.encryption_time_total += duration
        self.encryption_ops += 1
    
    def record_decryption(self, duration: float) -> None:
        """Record decryption operation timing."""
        self.decryption_time_total += duration
        self.decryption_ops += 1
    
    def get_average_rtt(self) -> Optional[float]:
        """Get average RTT in seconds."""
        if not self.rtt_samples:
            return None
        return sum(self.rtt_samples) / len(self.rtt_samples)
    
    def get_current_throughput(self) -> float:
        """Get current throughput in bytes/second."""
        if not self.throughput_window:
            return 0.0
        
        current_time = time.time()
        cutoff = current_time - self.throughput_window_size
        recent = [(t, s) for t, s in self.throughput_window if t > cutoff]
        
        if not recent:
            return 0.0
        
        total_bytes = sum(s for _, s in recent)
        time_span = current_time - recent[0][0]
        
        if time_span == 0:
            return 0.0
        
        return total_bytes / time_span
    
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
        """Get comprehensive session statistics including performance metrics."""
        avg_rtt = self.get_average_rtt()
        throughput = self.get_current_throughput()
        
        stats = {
            'session_id': self.session_id.hex(),
            'peer_node_id': self.peer_node_id.hex(),
            'key_version': self.key_version,
            'is_active': self.is_active,
            'uptime': time.time() - self.created_at,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'frames_sent': self.frames_sent,
            'frames_received': self.frames_received,
            
            # Performance metrics
            'average_rtt_ms': round(avg_rtt * 1000, 2) if avg_rtt else None,
            'min_rtt_ms': round(min(self.rtt_samples) * 1000, 2) if self.rtt_samples else None,
            'max_rtt_ms': round(max(self.rtt_samples) * 1000, 2) if self.rtt_samples else None,
            'rtt_samples_count': len(self.rtt_samples),
            
            # Throughput
            'current_throughput_bps': round(throughput, 2),
            'current_throughput_mbps': round(throughput / 1_000_000, 2),
            
            # Encryption performance
            'avg_encryption_time_ms': round(
                (self.encryption_time_total / self.encryption_ops * 1000) if self.encryption_ops > 0 else 0, 3
            ),
            'avg_decryption_time_ms': round(
                (self.decryption_time_total / self.decryption_ops * 1000) if self.decryption_ops > 0 else 0, 3
            ),
            'encryption_ops': self.encryption_ops,
            'decryption_ops': self.decryption_ops,
        }
        
        return stats
    
    def get_statistics(self) -> Dict:
        """Get session statistics (alias for compatibility)."""
        return self.get_stats()
    
    def is_active_method(self) -> bool:
        """Check if session is active (method version)."""
        return self.is_active
    
    async def rotate_key(self, stc_wrapper: STCWrapper) -> None:
        """Rotate session key using STC.
        
        Args:
            stc_wrapper: STC wrapper for key derivation
        """
        # Generate rotation nonce
        import secrets
        rotation_nonce = secrets.token_bytes(32)
        
        # Derive new session key from current key + nonce
        if self.session_key:
            new_key = stc_wrapper.rotate_session_key(self.session_key, rotation_nonce)
            self.session_key = new_key
            self.key_version += 1
        else:
            # If no session key yet, derive one from session_id
            self.session_key = stc_wrapper.derive_session_key({
                'session_id': self.session_id.hex(),
                'peer_id': self.peer_node_id.hex()
            })
            self.key_version = 1


class SessionManager:
    """Manages multiple sessions."""
    
    def __init__(self, node_id: bytes, stc_wrapper: STCWrapper, continuity_manager: Optional['CryptoSessionContinuity'] = None):
        """
        Initialize session manager.
        
        Args:
            node_id: This node's identifier
            stc_wrapper: STC wrapper for crypto
            continuity_manager: Optional crypto session continuity
        """
        self.node_id = node_id
        self.stc_wrapper = stc_wrapper
        self.sessions: Dict[bytes, STTSession] = {}
        self.continuity_manager = continuity_manager
    
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
