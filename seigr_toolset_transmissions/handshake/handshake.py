"""
STC-native handshake protocol for STT.

Since STC does not provide key agreement (X25519) or digital signatures (Ed25519),
STT uses a symmetric trust model with pre-shared seeds for authentication.
"""

import time
import secrets
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from enum import IntEnum

from ..crypto.stc_wrapper import STCWrapper
from ..utils.serialization import serialize_stt, deserialize_stt
from ..utils.exceptions import STTHandshakeError


class HandshakeState(IntEnum):
    """Handshake state machine states."""
    INIT = 0
    HELLO_SENT = 1
    HELLO_RECEIVED = 2
    RESPONSE_SENT = 3
    RESPONSE_RECEIVED = 4
    COMPLETED = 5
    FAILED = 6


@dataclass
class HandshakeHello:
    """HELLO message structure."""
    node_id: bytes
    nonce: bytes
    timestamp: int
    capabilities: list
    commitment: bytes  # Proof of knowing shared seed


@dataclass
class HandshakeResponse:
    """HELLO_RESP message structure."""
    node_id: bytes
    nonce: bytes
    challenge: bytes  # Challenge for mutual authentication


class STTHandshake:
    """
    STC-native handshake protocol using pre-shared seeds.
    
    Protocol Flow:
    1. HELLO: Node sends node_id, nonce, commitment
    2. HELLO_RESP: Peer responds with node_id, nonce, challenge
    3. AUTH_PROOF: Node proves it can derive same session key
    4. Session established with derived session key
    
    Security: Relies on pre-shared seed for mutual authentication.
    No key agreement protocol (since STC lacks X25519/ECDH).
    """
    
    def __init__(self, stc_wrapper: STCWrapper, shared_seed: bytes,
                 node_id: bytes):
        """
        Initialize handshake.
        
        Args:
            stc_wrapper: STC wrapper for cryptographic operations
            shared_seed: Pre-shared seed for authentication
            node_id: This node's identifier
        """
        self.stc = stc_wrapper
        self.node_id = node_id
        
        # Create shared context from pre-shared seed
        from interfaces.api import stc_api
        self.shared_context = stc_api.initialize(shared_seed)
        
        # Handshake state
        self.state = HandshakeState.INIT
        self.our_nonce = None
        self.peer_nonce = None
        self.peer_node_id = None
        self.session_key = None
    
    def initiate_handshake(self) -> bytes:
        """
        Initiate handshake by creating HELLO message.
        
        Returns:
            Serialized HELLO message
            
        Raises:
            STTHandshakeError: If state is invalid
        """
        if self.state != HandshakeState.INIT:
            raise STTHandshakeError(
                f"Cannot initiate from state {self.state.name}"
            )
        
        # Generate fresh nonce
        self.our_nonce = secrets.token_bytes(32)
        timestamp = int(time.time() * 1000)
        
        # Create commitment to prove we know shared seed
        commitment = self.shared_context.hash(
            self.our_nonce + self.node_id,
            context_data={'purpose': 'hello_commitment', 'timestamp': timestamp}
        )
        
        # Build HELLO message
        hello_msg = {
            'type': 'HELLO',
            'node_id': self.node_id.hex(),
            'nonce': self.our_nonce.hex(),
            'timestamp': timestamp,
            'capabilities': ['tcp', 'udp', 'streaming', 'dht', 'websocket'],
            'commitment': commitment.hex()
        }
        
        self.state = HandshakeState.HELLO_SENT
        
        return serialize_stt(hello_msg)
    
    def handle_hello(self, hello_bytes: bytes) -> bytes:
        """
        Handle received HELLO message and create HELLO_RESP.
        
        Args:
            hello_bytes: Serialized HELLO message
            
        Returns:
            Serialized HELLO_RESP message
            
        Raises:
            STTHandshakeError: If verification fails
        """
        if self.state not in (HandshakeState.INIT, HandshakeState.HELLO_SENT):
            raise STTHandshakeError(
                f"Cannot handle HELLO from state {self.state.name}"
            )
        
        # Parse HELLO
        try:
            hello = deserialize_stt(hello_bytes)
        except Exception as e:
            raise STTHandshakeError(f"Failed to parse HELLO: {e}")
        
        if hello.get('type') != 'HELLO':
            raise STTHandshakeError(f"Expected HELLO, got {hello.get('type')}")
        
        # Verify commitment
        peer_nonce = bytes.fromhex(hello['nonce'])
        peer_node_id = bytes.fromhex(hello['node_id'])
        timestamp = hello['timestamp']
        
        expected_commitment = self.shared_context.hash(
            peer_nonce + peer_node_id,
            context_data={'purpose': 'hello_commitment', 'timestamp': timestamp}
        )
        
        received_commitment = bytes.fromhex(hello['commitment'])
        
        if expected_commitment != received_commitment:
            self.state = HandshakeState.FAILED
            raise STTHandshakeError("Invalid commitment - authentication failed")
        
        # Store peer info
        self.peer_nonce = peer_nonce
        self.peer_node_id = peer_node_id
        
        # Generate our nonce if we haven't already
        if self.our_nonce is None:
            self.our_nonce = secrets.token_bytes(32)
        
        # Derive session key
        self.session_key = self.shared_context.derive_key(
            context_data={
                'nonce_a': hello['nonce'],
                'nonce_b': self.our_nonce.hex(),
                'timestamp': timestamp,
                'node_a': hello['node_id'],
                'node_b': self.node_id.hex(),
                'purpose': 'session_key'
            },
            key_size=32
        )
        
        # Create challenge for peer to prove they derived same key
        challenge = self.shared_context.hash(
            self.session_key + peer_nonce,
            context_data={'purpose': 'auth_challenge'}
        )
        
        # Build HELLO_RESP
        response_msg = {
            'type': 'HELLO_RESP',
            'node_id': self.node_id.hex(),
            'nonce': self.our_nonce.hex(),
            'challenge': challenge.hex()
        }
        
        self.state = HandshakeState.RESPONSE_SENT
        
        return serialize_stt(response_msg)
    
    def handle_response(self, response_bytes: bytes) -> Tuple[bytes, bytes]:
        """
        Handle HELLO_RESP and complete handshake.
        
        Args:
            response_bytes: Serialized HELLO_RESP message
            
        Returns:
            Tuple of (session_key, peer_node_id)
            
        Raises:
            STTHandshakeError: If verification fails
        """
        if self.state != HandshakeState.HELLO_SENT:
            raise STTHandshakeError(
                f"Cannot handle RESPONSE from state {self.state.name}"
            )
        
        # Parse HELLO_RESP
        try:
            response = deserialize_stt(response_bytes)
        except Exception as e:
            raise STTHandshakeError(f"Failed to parse HELLO_RESP: {e}")
        
        if response.get('type') != 'HELLO_RESP':
            raise STTHandshakeError(
                f"Expected HELLO_RESP, got {response.get('type')}"
            )
        
        # Extract peer info
        self.peer_nonce = bytes.fromhex(response['nonce'])
        self.peer_node_id = bytes.fromhex(response['node_id'])
        
        # Derive session key (same derivation as peer)
        self.session_key = self.shared_context.derive_key(
            context_data={
                'nonce_a': self.our_nonce.hex(),
                'nonce_b': response['nonce'],
                'timestamp': int(time.time() * 1000),
                'node_a': self.node_id.hex(),
                'node_b': response['node_id'],
                'purpose': 'session_key'
            },
            key_size=32
        )
        
        # Verify challenge
        expected_challenge = self.shared_context.hash(
            self.session_key + self.our_nonce,
            context_data={'purpose': 'auth_challenge'}
        )
        
        received_challenge = bytes.fromhex(response['challenge'])
        
        if expected_challenge != received_challenge:
            self.state = HandshakeState.FAILED
            raise STTHandshakeError("Challenge verification failed")
        
        self.state = HandshakeState.COMPLETED
        
        return self.session_key, self.peer_node_id
    
    def get_session_key(self) -> Optional[bytes]:
        """
        Get derived session key.
        
        Returns:
            Session key if handshake completed, None otherwise
        """
        if self.state == HandshakeState.COMPLETED:
            return self.session_key
        return None
    
    def get_peer_node_id(self) -> Optional[bytes]:
        """
        Get peer's node ID.
        
        Returns:
            Peer node ID if available, None otherwise
        """
        return self.peer_node_id
    
    def reset(self):
        """Reset handshake state for retry."""
        self.state = HandshakeState.INIT
        self.our_nonce = None
        self.peer_nonce = None
        self.peer_node_id = None
        self.session_key = None


class HandshakeManager:
    """
    Manager for multiple concurrent handshakes.
    
    Tracks handshake sessions with different peers.
    """
    
    def __init__(self, stc_wrapper: STCWrapper, shared_seed: bytes,
                 node_id: bytes):
        """
        Initialize handshake manager.
        
        Args:
            stc_wrapper: STC wrapper instance
            shared_seed: Pre-shared seed for authentication
            node_id: This node's identifier
        """
        self.stc_wrapper = stc_wrapper
        self.shared_seed = shared_seed
        self.node_id = node_id
        self.handshakes = {}  # peer_addr -> STTHandshake
    
    def create_handshake(self, peer_addr: str) -> STTHandshake:
        """
        Create new handshake session for peer.
        
        Args:
            peer_addr: Peer address (for tracking)
            
        Returns:
            New STTHandshake instance
        """
        handshake = STTHandshake(self.stc_wrapper, self.shared_seed, self.node_id)
        self.handshakes[peer_addr] = handshake
        return handshake
    
    def get_handshake(self, peer_addr: str) -> Optional[STTHandshake]:
        """Get existing handshake session."""
        return self.handshakes.get(peer_addr)
    
    def remove_handshake(self, peer_addr: str):
        """Remove completed or failed handshake."""
        self.handshakes.pop(peer_addr, None)
