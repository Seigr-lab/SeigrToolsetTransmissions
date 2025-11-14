"""
STC-native handshake protocol for STT.

Simplified symmetric trust model with STC-based authentication.
"""

import time
import secrets
from typing import Optional, Tuple

from ..crypto.stc_wrapper import STCWrapper
from ..utils.serialization import serialize_stt, deserialize_stt
from ..utils.exceptions import STTHandshakeError


class STTHandshake:
    """
    Simplified STC-based handshake protocol.
    
    Protocol Flow:
    1. Initiator creates HELLO with node_id, nonce, and commitment
    2. Responder processes HELLO and creates RESPONSE with challenge
    3. Initiator processes RESPONSE and creates AUTH_PROOF
    4. Session established with derived session key
    """
    
    def __init__(self, node_id: bytes, stc_wrapper: STCWrapper, is_initiator: bool = True):
        """
        Initialize handshake.
        
        Args:
            node_id: This node's identifier (32 bytes)
            stc_wrapper: STC wrapper for cryptographic operations
            is_initiator: True if initiating handshake, False if responding
        """
        self.node_id = node_id
        self.stc_wrapper = stc_wrapper
        self.is_initiator = is_initiator
        
        # Handshake state
        self.session_id: Optional[bytes] = None
        self.our_nonce: Optional[bytes] = None
        self.peer_nonce: Optional[bytes] = None
        self.peer_node_id: Optional[bytes] = None
        self.session_key: Optional[bytes] = None
        self.completed = False
    
    def create_hello(self) -> bytes:
        """
        Create HELLO message to initiate handshake.
        
        Returns:
            Serialized HELLO message
        """
        # Generate fresh nonce
        self.our_nonce = secrets.token_bytes(32)
        
        # Create commitment: hash of (node_id + nonce)
        commitment = self.stc_wrapper.hash_data(
            self.node_id + self.our_nonce,
            {'purpose': 'hello_commitment'}
        )
        
        # Serialize HELLO message
        hello_msg = {
            'type': 'HELLO',
            'node_id': self.node_id,
            'nonce': self.our_nonce,
            'timestamp': int(time.time() * 1000),
            'commitment': commitment
        }
        
        return serialize_stt(hello_msg)
    
    def process_hello(self, hello_data: bytes) -> bytes:
        """
        Process HELLO message and create RESPONSE.
        
        Args:
            hello_data: Serialized HELLO message
            
        Returns:
            Serialized RESPONSE message
        """
        # Deserialize HELLO
        hello_msg = deserialize_stt(hello_data)
        
        # Extract peer info
        self.peer_node_id = hello_msg['node_id']
        self.peer_nonce = hello_msg['nonce']
        
        # Generate our nonce
        self.our_nonce = secrets.token_bytes(32)
        
        # Create challenge
        challenge = self.stc_wrapper.hash_data(
            self.peer_nonce + self.our_nonce,
            {'purpose': 'challenge'}
        )
        
        # Create RESPONSE message
        response_msg = {
            'type': 'RESPONSE',
            'node_id': self.node_id,
            'nonce': self.our_nonce,
            'challenge': challenge,
            'timestamp': int(time.time() * 1000)
        }
        
        return serialize_stt(response_msg)
    
    def process_response(self, response_data: bytes) -> bytes:
        """
        Process RESPONSE message and create AUTH_PROOF.
        
        Args:
            response_data: Serialized RESPONSE message
            
        Returns:
            Serialized AUTH_PROOF message
        """
        # Deserialize RESPONSE
        response_msg = deserialize_stt(response_data)
        
        # Extract peer info
        self.peer_node_id = response_msg['node_id']
        self.peer_nonce = response_msg['nonce']
        challenge = response_msg['challenge']
        
        # Derive session key
        self.session_key = self.stc_wrapper.derive_session_key({
            'initiator_nonce': self.our_nonce.hex(),
            'responder_nonce': self.peer_nonce.hex(),
            'initiator_node_id': self.node_id.hex(),
            'responder_node_id': self.peer_node_id.hex(),
            'purpose': 'session_key'
        })
        
        # Generate session ID from session key
        self.session_id = self.stc_wrapper.hash_data(
            self.session_key,
            {'purpose': 'session_id'}
        )[:8]  # Use first 8 bytes
        
        # Create auth proof
        auth_proof = self.stc_wrapper.hash_data(
            self.session_key + challenge,
            {'purpose': 'auth_proof'}
        )
        
        # Create AUTH_PROOF message
        proof_msg = {
            'type': 'AUTH_PROOF',
            'session_id': self.session_id,
            'proof': auth_proof,
            'timestamp': int(time.time() * 1000)
        }
        
        self.completed = True
        return serialize_stt(proof_msg)
    
    def verify_proof(self, proof_data: bytes) -> bool:
        """
        Verify AUTH_PROOF message and complete handshake.
        
        Args:
            proof_data: Serialized AUTH_PROOF message
            
        Returns:
            True if proof is valid
        """
        # Deserialize proof
        proof_msg = deserialize_stt(proof_data)
        
        # Derive session key (responder perspective)
        self.session_key = self.stc_wrapper.derive_session_key({
            'initiator_nonce': self.peer_nonce.hex(),
            'responder_nonce': self.our_nonce.hex(),
            'initiator_node_id': self.peer_node_id.hex(),
            'responder_node_id': self.node_id.hex(),
            'purpose': 'session_key'
        })
        
        # Generate expected session ID
        self.session_id = self.stc_wrapper.hash_data(
            self.session_key,
            {'purpose': 'session_id'}
        )[:8]
        
        # Verify session ID matches
        if self.session_id != proof_msg['session_id']:
            return False
        
        # Create expected challenge
        challenge = self.stc_wrapper.hash_data(
            self.peer_nonce + self.our_nonce,
            {'purpose': 'challenge'}
        )
        
        # Verify proof
        expected_proof = self.stc_wrapper.hash_data(
            self.session_key + challenge,
            {'purpose': 'auth_proof'}
        )
        
        if expected_proof == proof_msg['proof']:
            self.completed = True
            return True
        
        return False
    
    def get_session_id(self) -> Optional[bytes]:
        """Get established session ID."""
        return self.session_id if self.completed else None
    
    def get_session_key(self) -> Optional[bytes]:
        """Get derived session key."""
        return self.session_key if self.completed else None


class HandshakeManager:
    """
    Manages multiple concurrent handshakes.
    """
    
    def __init__(self, node_id: bytes, stc_wrapper: STCWrapper):
        """
        Initialize handshake manager.
        
        Args:
            node_id: This node's identifier
            stc_wrapper: STC wrapper for crypto operations
        """
        self.node_id = node_id
        self.stc_wrapper = stc_wrapper
        self.active_handshakes = {}
        self.completed_sessions = {}
    
    def initiate_handshake(self, peer_node_id: bytes) -> Tuple[bytes, STTHandshake]:
        """
        Initiate handshake with peer.
        
        Args:
            peer_node_id: Peer's node identifier
            
        Returns:
            Tuple of (hello_data, handshake_instance)
        """
        handshake = STTHandshake(
            node_id=self.node_id,
            stc_wrapper=self.stc_wrapper,
            is_initiator=True
        )
        
        hello_data = handshake.create_hello()
        self.active_handshakes[peer_node_id] = handshake
        
        return hello_data, handshake
    
    def handle_hello(self, hello_data: bytes) -> bytes:
        """
        Handle incoming HELLO message.
        
        Args:
            hello_data: Serialized HELLO message
            
        Returns:
            Serialized RESPONSE message
        """
        handshake = STTHandshake(
            node_id=self.node_id,
            stc_wrapper=self.stc_wrapper,
            is_initiator=False
        )
        
        response_data = handshake.process_hello(hello_data)
        self.active_handshakes[handshake.peer_node_id] = handshake
        
        return response_data
    
    def complete_handshake(self, peer_node_id: bytes, response_data: bytes) -> bytes:
        """
        Complete handshake after receiving RESPONSE.
        
        Args:
            peer_node_id: Peer's node identifier
            response_data: Serialized RESPONSE message
            
        Returns:
            Session ID
        """
        handshake = self.active_handshakes.get(peer_node_id)
        if not handshake:
            raise STTHandshakeError(f"No active handshake for {peer_node_id.hex()}")
        
        proof_data = handshake.process_response(response_data)
        session_id = handshake.get_session_id()
        
        if session_id:
            self.completed_sessions[session_id] = handshake
            del self.active_handshakes[peer_node_id]
        
        return session_id
    
    def get_session_id(self, peer_node_id: bytes) -> Optional[bytes]:
        """Get session ID for peer if handshake completed."""
        handshake = self.active_handshakes.get(peer_node_id)
        if handshake and handshake.completed:
            return handshake.get_session_id()
        return None

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
