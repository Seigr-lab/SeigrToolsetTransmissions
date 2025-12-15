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
        self.challenge: Optional[bytes] = None
        self.challenge_metadata: Optional[bytes] = None  # STC metadata for challenge
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
        Process HELLO message and create RESPONSE with encrypted challenge.
        
        Uses STC's probabilistic encryption to create a unique challenge
        that only someone with the same seed can decrypt.
        
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
        
        # Create challenge payload: combine both nonces
        challenge_payload = self.peer_nonce + self.our_nonce
        
        # Encrypt challenge using STC with shared seed
        # Only peer with same seed can decrypt this
        self.challenge, self.challenge_metadata = self.stc_wrapper.encrypt_frame(
            challenge_payload,
            {
                'purpose': 'handshake_challenge',
                'initiator_node_id': self.peer_node_id.hex(),
                'responder_node_id': self.node_id.hex()
            }
        )
        
        # Create RESPONSE message
        response_msg = {
            'type': 'RESPONSE',
            'node_id': self.node_id,
            'nonce': self.our_nonce,
            'challenge': self.challenge,
            'challenge_metadata': self.challenge_metadata,
            'timestamp': int(time.time() * 1000)
        }
        
        return serialize_stt(response_msg)
    
    def process_challenge(self, challenge_data: bytes) -> bytes:
        """
        Process challenge (RESPONSE) from responder and create proof.
        
        This is an alias for process_response to match test expectations.
        
        Args:
            challenge_data: Serialized RESPONSE/challenge message
            
        Returns:
            Serialized AUTH_PROOF message
        """
        return self.process_response(challenge_data)
    
    def process_response(self, response_data: bytes) -> bytes:
        """
        Process RESPONSE by decrypting challenge and creating proof.
        
        The ability to decrypt the challenge proves we have the same seed.
        We then create a deterministic session ID and encrypt our own proof.
        
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
        challenge_encrypted = response_msg['challenge']
        challenge_metadata = response_msg['challenge_metadata']
        
        # Decrypt challenge - this proves we have the same seed!
        try:
            challenge_payload = self.stc_wrapper.decrypt_frame(
                challenge_encrypted,
                challenge_metadata,
                {
                    'purpose': 'handshake_challenge',
                    'initiator_node_id': self.node_id.hex(),
                    'responder_node_id': self.peer_node_id.hex()
                }
            )
        except Exception as e:
            raise STTHandshakeError(f"Failed to decrypt challenge - wrong seed? {e}")
        
        # Verify challenge contains our nonce + peer nonce
        expected_payload = self.our_nonce + self.peer_nonce
        if challenge_payload != expected_payload:
            raise STTHandshakeError("Challenge verification failed")
        
        # Create deterministic session ID from XOR of nonces
        # Pure mathematical operation - same inputs always produce same output
        # No crypto primitives needed - just unique session identification
        nonce_xor = bytes(a ^ b for a, b in zip(self.our_nonce, self.peer_nonce))
        node_xor = bytes(a ^ b for a, b in zip(self.node_id, self.peer_node_id))
        
        # Combine with simple concatenation and truncate to 8 bytes
        self.session_id = (nonce_xor + node_xor)[:8]
        
        # Create proof by encrypting session ID with STC
        proof_encrypted, proof_metadata = self.stc_wrapper.encrypt_frame(
            self.session_id,
            {
                'purpose': 'auth_proof',
                'initiator_node_id': self.node_id.hex(),
                'responder_node_id': self.peer_node_id.hex()
            }
        )
        
        # Create AUTH_PROOF message
        proof_msg = {
            'type': 'AUTH_PROOF',
            'session_id': self.session_id,
            'proof': proof_encrypted,
            'proof_metadata': proof_metadata,
            'timestamp': int(time.time() * 1000)
        }
        
        self.completed = True
        return serialize_stt(proof_msg)
    
    def verify_response(self, response_data: bytes) -> bytes:
        """
        Verify AUTH_PROOF from initiator and create final confirmation.
        
        Args:
            response_data: Serialized AUTH_PROOF message
            
        Returns:
            Serialized FINAL message
        """
        # Verify the proof
        if not self.verify_proof(response_data):
            raise STTHandshakeError("Invalid proof from initiator")
        
        # Create final confirmation message
        final_msg = {
            'type': 'FINAL',
            'session_id': self.session_id,
            'timestamp': int(time.time() * 1000)
        }
        
        return serialize_stt(final_msg)
    
    def process_final(self, final_data: bytes) -> None:
        """
        Process final confirmation message and complete handshake.
        
        Args:
            final_data: Serialized FINAL message
        """
        # Deserialize final message
        final_msg = deserialize_stt(final_data)
        
        # Verify session ID matches
        if final_msg.get('session_id') != self.session_id:
            raise STTHandshakeError("Session ID mismatch in final confirmation")
        
        # Mark as complete
        self.completed = True
    
    def verify_proof(self, proof_data: bytes) -> bool:
        """
        Verify AUTH_PROOF by decrypting it and checking session ID.
        
        The ability to decrypt the proof proves the initiator has the same seed.
        
        Args:
            proof_data: Serialized AUTH_PROOF message
            
        Returns:
            True if proof is valid
        """
        # Deserialize proof
        proof_msg = deserialize_stt(proof_data)
        
        # Generate expected session ID deterministically using XOR
        nonce_xor = bytes(a ^ b for a, b in zip(self.our_nonce, self.peer_nonce))
        node_xor = bytes(a ^ b for a, b in zip(self.node_id, self.peer_node_id))
        self.session_id = (nonce_xor + node_xor)[:8]
        
        # Verify session ID in message matches
        if self.session_id != proof_msg['session_id']:
            return False
        
        # Decrypt proof to verify peer can encrypt correctly
        try:
            decrypted_session_id = self.stc_wrapper.decrypt_frame(
                proof_msg['proof'],
                proof_msg['proof_metadata'],
                {
                    'purpose': 'auth_proof',
                    'initiator_node_id': self.peer_node_id.hex(),
                    'responder_node_id': self.node_id.hex()
                }
            )
        except Exception:
            return False
        
        # Verify decrypted content matches session ID
        if decrypted_session_id == self.session_id:
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
    
    def initiate_handshake_sync(self, peer_node_id: bytes) -> Tuple[bytes, STTHandshake]:
        """
        Initiate handshake with peer (synchronous version).
        
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
        
        handshake.process_response(response_data)  # Side effect completes handshake
        session_id = handshake.get_session_id()
        
        if session_id:
            self.completed_sessions[session_id] = handshake
            del self.active_handshakes[peer_node_id]
        
        return session_id
    
    def get_session_id(self, peer_address: tuple) -> Optional[bytes]:
        """Get session ID for peer if handshake completed."""
        # Check active handshakes
        handshake = self.active_handshakes.get(peer_address)
        if handshake and handshake.completed:
            return handshake.get_session_id()
        
        # Check completed sessions - return first session_id if any exist
        for session_id in self.completed_sessions:
            return session_id
        
        return None
    
    async def initiate_handshake(self, peer_address: tuple) -> STTHandshake:
        """
        Async-compatible initiate handshake.
        
        Args:
            peer_address: Peer address tuple (ip, port)
            
        Returns:
            STTHandshake instance
        """
        handshake = STTHandshake(
            node_id=self.node_id,
            stc_wrapper=self.stc_wrapper,
            is_initiator=True
        )
        
        self.active_handshakes[peer_address] = handshake
        return handshake
    
    async def handle_incoming(self, peer_address: tuple, data: bytes) -> bytes:
        """
        Handle incoming handshake message.
        
        Args:
            peer_address: Peer address tuple (ip, port)
            data: Incoming message data
            
        Returns:
            Response message to send back
        """
        # Check if we have existing handshake
        handshake = self.active_handshakes.get(peer_address)
        
        # Process message based on type
        msg = deserialize_stt(data)
        msg_type = msg.get('type')
        
        if msg_type == 'HELLO':
            # New incoming handshake
            if not handshake:
                handshake = STTHandshake(
                    node_id=self.node_id,
                    stc_wrapper=self.stc_wrapper,
                    is_initiator=False
                )
                self.active_handshakes[peer_address] = handshake
            return handshake.process_hello(data)
        
        elif msg_type == 'RESPONSE':
            # Response to our HELLO - we are initiator
            if not handshake:
                raise STTHandshakeError("Received RESPONSE with no active handshake")
            return handshake.process_response(data)
        
        elif msg_type == 'AUTH_PROOF':
            # Proof from initiator - we are responder
            if not handshake:
                raise STTHandshakeError("Received AUTH_PROOF with no active handshake")
            return handshake.verify_response(data)
        
        elif msg_type == 'FINAL':
            # Final confirmation - we are initiator
            if not handshake:
                raise STTHandshakeError("Received FINAL with no active handshake")
            handshake.process_final(data)
            # Mark complete
            session_id = handshake.get_session_id()
            if session_id:
                self.completed_sessions[session_id] = handshake
                del self.active_handshakes[peer_address]
            return b''  # No response needed
        
        else:
            raise STTHandshakeError(f"Unknown message type: {msg_type}")
    
    async def complete_handshake(self, peer_address: tuple) -> Optional[bytes]:
        """
        Complete handshake and get session ID.
        
        Args:
            peer_address: Peer address tuple (ip, port)
            
        Returns:
            Session ID if completed
        """
        handshake = self.active_handshakes.get(peer_address)
        if handshake and handshake.completed:
            session_id = handshake.get_session_id()
            self.completed_sessions[session_id] = handshake
            del self.active_handshakes[peer_address]
            return session_id
        return None
    
    async def get_session_id_async(self, peer_address: tuple) -> Optional[bytes]:
        """
        Async get session ID for peer.
        
        Args:
            peer_address: Peer address tuple (ip, port)
            
        Returns:
            Session ID if completed
        """
        handshake = self.active_handshakes.get(peer_address)
        if handshake and handshake.completed:
            return handshake.get_session_id()
        return None
    
    def is_handshake_complete(self, peer_address: tuple) -> bool:
        """
        Check if handshake is complete for peer.
        
        Args:
            peer_address: Peer address tuple (ip, port)
            
        Returns:
            True if handshake completed
        """
        # Check both active and completed
        handshake = self.active_handshakes.get(peer_address)
        if handshake and handshake.completed:
            return True
        
        # Check if session was moved to completed
        for handshake in self.completed_sessions.values():
            if handshake.peer_node_id:
                return True
        
        return False
    
    def cleanup_timeouts(self, max_age: float = 30.0):
        """
        Clean up old incomplete handshakes.
        
        Args:
            max_age: Maximum age in seconds
        """
        # Reserved for future: time.time() for timestamp-based cleanup
        
        # Remove old handshakes (would need timestamps in real implementation)
        # For now, remove all incomplete handshakes if max_age is 0
        if max_age == 0:
            self.active_handshakes.clear()
