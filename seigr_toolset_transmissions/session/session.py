"""
Session management for STT secure connections.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Dict

from ..stream import StreamManager
from ..utils.constants import (
    STT_SESSION_STATE_INIT,
    STT_SESSION_STATE_HANDSHAKE,
    STT_SESSION_STATE_ACTIVE,
    STT_SESSION_STATE_KEY_ROTATING,
    STT_SESSION_STATE_CLOSING,
    STT_SESSION_STATE_CLOSED,
    STT_KEY_ROTATION_DATA_THRESHOLD,
    STT_KEY_ROTATION_TIME_THRESHOLD,
    STT_KEY_ROTATION_MESSAGE_THRESHOLD,
)
from ..utils.exceptions import STTSessionError, STTInvalidStateError
from ..utils.logging import get_logger


logger = get_logger(__name__)


@dataclass
class STTSession:
    """
    Represents a secure STT session between peers.
    """
    
    session_id: bytes
    peer_node_id: bytes
    local_node_id: bytes
    state: int = STT_SESSION_STATE_INIT
    
    # Key material (encrypted in production via STC)
    session_key: Optional[bytes] = None
    
    # Stream management
    stream_manager: StreamManager = field(init=False)
    
    # Sequence tracking
    send_sequence: int = 0
    recv_sequence: int = 0
    
    # Key rotation tracking
    bytes_transmitted: int = 0
    messages_transmitted: int = 0
    session_start_time: float = field(default_factory=time.time)
    last_key_rotation: float = field(default_factory=time.time)
    
    # Flow control
    send_credit: int = 0
    recv_credit: int = 0
    
    # Capabilities
    capabilities: int = 0
    
    # Resumption token
    resumption_token: Optional[bytes] = None
    
    def __post_init__(self) -> None:
        """Initialize session components."""
        if len(self.session_id) != 8:
            raise STTSessionError("Session ID must be 8 bytes")
        if len(self.peer_node_id) != 32:
            raise STTSessionError("Peer node ID must be 32 bytes")
        if len(self.local_node_id) != 32:
            raise STTSessionError("Local node ID must be 32 bytes")
        
        self.stream_manager = StreamManager(self.session_id)
    
    def next_send_sequence(self) -> int:
        """Get next send sequence number and increment."""
        seq = self.send_sequence
        self.send_sequence += 1
        return seq
    
    def verify_recv_sequence(self, sequence: int) -> bool:
        """
        Verify received sequence number.
        
        Args:
            sequence: Received sequence number
            
        Returns:
            True if valid, False otherwise
        """
        if sequence == self.recv_sequence:
            self.recv_sequence += 1
            return True
        
        logger.warning(
            f"Sequence mismatch: expected {self.recv_sequence}, got {sequence}"
        )
        return False
    
    def update_transmitted_stats(self, bytes_count: int) -> None:
        """
        Update transmission statistics.
        
        Args:
            bytes_count: Number of bytes transmitted
        """
        self.bytes_transmitted += bytes_count
        self.messages_transmitted += 1
    
    def should_rotate_keys(self) -> bool:
        """
        Check if key rotation is needed.
        
        Returns:
            True if rotation needed
        """
        if self.state != STT_SESSION_STATE_ACTIVE:
            return False
        
        # Check data threshold
        if self.bytes_transmitted >= STT_KEY_ROTATION_DATA_THRESHOLD:
            logger.info("Key rotation needed: data threshold reached")
            return True
        
        # Check time threshold
        time_since_rotation = time.time() - self.last_key_rotation
        if time_since_rotation >= STT_KEY_ROTATION_TIME_THRESHOLD:
            logger.info("Key rotation needed: time threshold reached")
            return True
        
        # Check message threshold
        if self.messages_transmitted >= STT_KEY_ROTATION_MESSAGE_THRESHOLD:
            logger.info("Key rotation needed: message threshold reached")
            return True
        
        return False
    
    async def rotate_keys(self, new_session_key: bytes) -> None:
        """
        Perform key rotation.
        
        Args:
            new_session_key: New session key material
        """
        if self.state != STT_SESSION_STATE_ACTIVE:
            raise STTInvalidStateError(
                f"Cannot rotate keys in state {self.state}"
            )
        
        old_state = self.state
        self.state = STT_SESSION_STATE_KEY_ROTATING
        
        try:
            # In production, use STC KDF to derive new keys
            self.session_key = new_session_key
            
            # Reset counters
            self.bytes_transmitted = 0
            self.messages_transmitted = 0
            self.last_key_rotation = time.time()
            
            logger.info(f"Session {self.session_id.hex()}: key rotation completed")
            
        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            raise STTSessionError(f"Key rotation failed: {e}")
        
        finally:
            if self.state == STT_SESSION_STATE_KEY_ROTATING:
                self.state = old_state
    
    async def close(self) -> None:
        """Close the session and all streams."""
        if self.state == STT_SESSION_STATE_CLOSED:
            return
        
        self.state = STT_SESSION_STATE_CLOSING
        
        # Close all streams
        await self.stream_manager.close_all_streams()
        
        # Clear sensitive data
        self.session_key = None
        self.resumption_token = None
        
        self.state = STT_SESSION_STATE_CLOSED
        
        logger.info(f"Session {self.session_id.hex()}: closed")
    
    def is_active(self) -> bool:
        """Check if session is active."""
        return self.state == STT_SESSION_STATE_ACTIVE
    
    def is_closed(self) -> bool:
        """Check if session is closed."""
        return self.state == STT_SESSION_STATE_CLOSED
    
    def get_stats(self) -> dict:
        """Get session statistics."""
        return {
            'session_id': self.session_id.hex(),
            'peer_node_id': self.peer_node_id.hex(),
            'state': self.state,
            'send_sequence': self.send_sequence,
            'recv_sequence': self.recv_sequence,
            'bytes_transmitted': self.bytes_transmitted,
            'messages_transmitted': self.messages_transmitted,
            'uptime': time.time() - self.session_start_time,
            'time_since_key_rotation': time.time() - self.last_key_rotation,
            'stream_stats': self.stream_manager.get_stats(),
        }
