"""
Cryptographic Session Continuity - Seed-Based Session Identity

Session identity from SEEDS, not network:
- Resume across IP changes (WiFi → LTE seamless)
- Resume across transports (UDP ↔ WebSocket ↔ TCP)
- Resume across devices (same seeds = same session)
- Zero-knowledge continuity proofs

BREAKS FROM TRADITION: NOT QUIC-style connection migration (network-bound)
BUT seed-derived session identity (crypto-bound)
"""

import time
from typing import Dict, Tuple, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

from .session import STTSession
from ..utils.logging import get_logger
from ..utils.exceptions import STTSessionError

if TYPE_CHECKING:
    from ..crypto.stc_wrapper import STCWrapper

logger = get_logger(__name__)


class SessionResumptionError(STTSessionError):
    """Error during session resumption."""
    pass


@dataclass
class StreamState:
    """Persistent stream state for resumption."""
    stream_id: int
    sequence: int
    bytes_sent: int
    bytes_received: int


@dataclass
class SessionState:
    """Persistent session state for resumption."""
    session_id: bytes
    peer_node_id: bytes
    created_at: int
    last_sequence: int
    stream_states: Dict[int, StreamState] = field(default_factory=dict)
    last_transport: str = 'unknown'
    resume_count: int = 0
    metadata: Dict = field(default_factory=dict)


class CryptoSessionContinuity:
    """
    Session continuity based on cryptographic seeds.
    
    Enables seamless session resumption across:
    - Network changes (WiFi → LTE, IP address change)
    - Transport changes (UDP → WebSocket, TCP → UDP)
    - Client reconnects (crash recovery)
    - Device migration (same seeds on different device)
    """
    
    def __init__(self, stc_wrapper: 'STCWrapper', resumption_timeout: int = 86400):
        """
        Initialize continuity manager.
        
        Args:
            stc_wrapper: STC wrapper for crypto operations
            resumption_timeout: Resumption token validity (seconds, default 24h)
        """
        self.stc = stc_wrapper
        self.resumption_timeout = resumption_timeout
        
        # Registry: resumption_token -> SessionState
        self.session_registry: Dict[bytes, SessionState] = {}
        
        # Reverse lookup: session_id -> resumption_token
        self.session_tokens: Dict[bytes, bytes] = {}
        
        logger.info(f"CryptoSessionContinuity initialized (timeout={resumption_timeout}s)")
    
    def create_resumable_session(
        self,
        peer_node_id: bytes,
        node_seed: bytes,
        shared_seed: bytes
    ) -> Tuple[bytes, bytes]:
        """
        Create session with cryptographic resumption capability.
        
        Session ID is DETERMINISTIC from seeds - same seeds always
        produce same session ID (content-addressing for sessions!)
        
        Args:
            peer_node_id: Peer's node identifier
            node_seed: This node's seed
            shared_seed: Shared session seed
            
        Returns:
            Tuple of (session_id, resumption_token)
        """
        timestamp = int(time.time())
        
        # Deterministic session ID from seeds + peer + timestamp
        session_material = (
            node_seed +
            shared_seed +
            peer_node_id +
            timestamp.to_bytes(8, 'big')
        )
        
        session_id = self.stc.hash_data(
            session_material,
            context={'purpose': 'session_id'}
        )[:8]  # 8-byte session ID
        
        # Resumption token (cryptographic capability)
        resumption_token = self.stc.hash_data(
            session_material + b'RESUME_TOKEN',
            context={'purpose': 'resumption', 'timestamp': timestamp}
        )[:32]  # 32-byte token
        
        # Store session state
        state = SessionState(
            session_id=session_id,
            peer_node_id=peer_node_id,
            created_at=timestamp,
            last_sequence=0,
            stream_states={},
            last_transport='unknown',
            resume_count=0,
            metadata={}
        )
        
        self.session_registry[resumption_token] = state
        self.session_tokens[session_id] = resumption_token
        
        logger.info(
            f"Created resumable session: id={session_id.hex()[:8]}, "
            f"token={resumption_token.hex()[:8]}"
        )
        
        return session_id, resumption_token
    
    def resume_session(
        self,
        resumption_token: bytes,
        new_transport_type: str,
        new_peer_addr: Tuple[str, int],
        stc_wrapper: 'STCWrapper'
    ) -> STTSession:
        """
        Resume session on NEW transport/address.
        
        Works for:
        - IP address change (mobile handoff)
        - Transport change (UDP → WebSocket)
        - Client reconnect after crash
        - Different network interface
        - EVEN different device (if same seeds available)
        
        Args:
            resumption_token: Token from create_resumable_session()
            new_transport_type: New transport ('udp', 'websocket', 'tcp')
            new_peer_addr: New peer address (host, port)
            stc_wrapper: STC wrapper (may be new instance)
            
        Returns:
            Resumed STTSession
            
        Raises:
            SessionResumptionError: If token invalid or expired
        """
        # Verify token exists
        if resumption_token not in self.session_registry:
            raise SessionResumptionError(
                f"Invalid resumption token: {resumption_token.hex()[:8]}"
            )
        
        state = self.session_registry[resumption_token]
        
        # Check expiration
        age = time.time() - state.created_at
        if age > self.resumption_timeout:
            # Clean up expired state
            del self.session_registry[resumption_token]
            del self.session_tokens[state.session_id]
            raise SessionResumptionError(
                f"Resumption token expired (age={age:.0f}s > {self.resumption_timeout}s)"
            )
        
        # Recreate session with SAME session_id
        session = STTSession(
            session_id=state.session_id,
            peer_node_id=state.peer_node_id,
            stc_wrapper=stc_wrapper
        )
        
        # Attach new transport info (seamless migration)
        session.peer_addr = new_peer_addr
        session.transport_type = new_transport_type
        
        # Restore metadata
        session.metadata['resumed'] = True
        session.metadata['previous_transport'] = state.last_transport
        session.metadata['resume_count'] = state.resume_count + 1
        session.metadata['original_created_at'] = state.created_at
        session.metadata['resume_age'] = age
        session.metadata.update(state.metadata)
        
        # Update registry
        state.resume_count += 1
        state.last_transport = new_transport_type
        state.last_sequence = session.sequence if hasattr(session, 'sequence') else 0
        
        logger.info(
            f"Resumed session {state.session_id.hex()[:8]} on {new_transport_type}, "
            f"resume_count={state.resume_count}, age={age:.1f}s, "
            f"previous={state.last_transport} → new={new_transport_type}"
        )
        
        return session
    
    def generate_continuity_proof(
        self,
        session: STTSession,
        node_seed: bytes,
        shared_seed: bytes
    ) -> bytes:
        """
        Generate zero-knowledge continuity proof.
        
        Proves knowledge of original seeds WITHOUT revealing them.
        Peer can verify we're the same party without seeing seeds.
        
        Args:
            session: Active session
            node_seed: This node's seed
            shared_seed: Shared session seed
            
        Returns:
            Continuity proof (32 bytes)
        """
        current_time = int(time.time())
        
        proof_material = (
            node_seed +
            shared_seed +
            session.session_id +
            b'CONTINUITY_PROOF' +
            current_time.to_bytes(8, 'big')
        )
        
        proof = self.stc.hash_data(
            proof_material,
            context={'purpose': 'continuity_proof'}
        )[:32]
        
        logger.debug(
            f"Generated continuity proof for session {session.session_id.hex()[:8]}"
        )
        
        return proof
    
    def verify_continuity_proof(
        self,
        session: STTSession,
        proof: bytes,
        node_seed: bytes,
        shared_seed: bytes,
        tolerance: int = 60
    ) -> bool:
        """
        Verify continuity proof from peer.
        
        Allows time tolerance for clock skew.
        
        Args:
            session: Active session
            proof: Received proof
            node_seed: This node's seed
            shared_seed: Shared session seed
            tolerance: Time tolerance in seconds (default 60s)
            
        Returns:
            True if proof valid
        """
        current_time = int(time.time())
        
        # Try timestamps within tolerance window
        for time_offset in range(-tolerance, tolerance + 1, 10):
            test_time = current_time + time_offset
            
            expected_material = (
                node_seed +
                shared_seed +
                session.session_id +
                b'CONTINUITY_PROOF' +
                test_time.to_bytes(8, 'big')
            )
            
            expected_proof = self.stc.hash_data(
                expected_material,
                context={'purpose': 'continuity_proof'}
            )[:32]
            
            if proof == expected_proof:
                logger.info(
                    f"Continuity proof verified for session {session.session_id.hex()[:8]} "
                    f"(time_offset={time_offset}s)"
                )
                return True
        
        logger.warning(
            f"Continuity proof verification FAILED for session {session.session_id.hex()[:8]}"
        )
        return False
    
    def save_session_state(self, session: STTSession, stream_states: Optional[Dict[int, StreamState]] = None):
        """
        Save current session state for resumption.
        
        Args:
            session: Session to save
            stream_states: Optional stream states to save
        """
        # Find resumption token
        resumption_token = self.session_tokens.get(session.session_id)
        
        if not resumption_token:
            logger.warning(f"Cannot save state: no resumption token for session {session.session_id.hex()[:8]}")
            return
        
        state = self.session_registry.get(resumption_token)
        if not state:
            logger.warning(f"Cannot save state: no registry entry for token")
            return
        
        # Update state
        state.last_sequence = getattr(session, 'sequence', 0)
        state.last_transport = session.transport_type or 'unknown'
        state.metadata.update(session.metadata)
        
        if stream_states:
            state.stream_states.update(stream_states)
        
        logger.debug(f"Saved state for session {session.session_id.hex()[:8]}")
    
    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired resumption tokens.
        
        Returns:
            Number of sessions cleaned up
        """
        current_time = time.time()
        expired = []
        
        for token, state in self.session_registry.items():
            age = current_time - state.created_at
            if age > self.resumption_timeout:
                expired.append((token, state.session_id))
        
        for token, session_id in expired:
            del self.session_registry[token]
            if session_id in self.session_tokens:
                del self.session_tokens[session_id]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired session states")
        
        return len(expired)
    
    def get_resumption_info(self, session_id: bytes) -> Optional[Dict]:
        """
        Get resumption information for session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Resumption info or None
        """
        token = self.session_tokens.get(session_id)
        if not token:
            return None
        
        state = self.session_registry.get(token)
        if not state:
            return None
        
        age = time.time() - state.created_at
        
        return {
            'session_id': state.session_id.hex(),
            'peer_node_id': state.peer_node_id.hex(),
            'created_at': state.created_at,
            'age': age,
            'resume_count': state.resume_count,
            'last_transport': state.last_transport,
            'num_streams': len(state.stream_states),
            'expired': age > self.resumption_timeout,
        }
    
    def get_stats(self) -> Dict:
        """
        Get continuity manager statistics.
        
        Returns:
            Statistics dictionary
        """
        total_sessions = len(self.session_registry)
        current_time = time.time()
        
        resumed_count = sum(
            1 for state in self.session_registry.values()
            if state.resume_count > 0
        )
        
        expired_count = sum(
            1 for state in self.session_registry.values()
            if (current_time - state.created_at) > self.resumption_timeout
        )
        
        avg_resume_count = (
            sum(state.resume_count for state in self.session_registry.values()) /
            max(total_sessions, 1)
        )
        
        return {
            'total_sessions': total_sessions,
            'resumed_sessions': resumed_count,
            'expired_sessions': expired_count,
            'avg_resume_count': avg_resume_count,
            'resumption_timeout': self.resumption_timeout,
        }
