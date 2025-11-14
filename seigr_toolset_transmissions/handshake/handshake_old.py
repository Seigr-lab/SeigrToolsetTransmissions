"""
Handshake protocol for STT sessions.
"""

import struct
import secrets
from dataclasses import dataclass
from typing import Optional, Tuple

from ..utils.constants import (
    STT_VERSION,
    STT_HANDSHAKE_HELLO,
    STT_HANDSHAKE_HELLO_RESP,
    STT_HANDSHAKE_SESSION_INIT,
    STT_HANDSHAKE_AUTH_PROOF,
    STT_CAP_STREAMS,
    STT_CAP_KEY_ROTATION,
    STT_CAP_SESSION_RESUMPTION,
    STT_CAP_FLOW_CONTROL,
)
from ..utils.exceptions import STTHandshakeError


@dataclass
class HandshakeHello:
    """HELLO message structure."""
    
    version: int
    node_id: bytes  # 32 bytes - hash of public key
    ephemeral_public_key: bytes  # 32 bytes
    nonce: bytes  # 32 bytes
    capabilities: int
    
    def to_bytes(self) -> bytes:
        """Encode HELLO message."""
        if len(self.node_id) != 32:
            raise STTHandshakeError("Node ID must be 32 bytes")
        if len(self.ephemeral_public_key) != 32:
            raise STTHandshakeError("Ephemeral public key must be 32 bytes")
        if len(self.nonce) != 32:
            raise STTHandshakeError("Nonce must be 32 bytes")
        
        return struct.pack(
            '!B32s32s32sI',
            self.version,
            self.node_id,
            self.ephemeral_public_key,
            self.nonce,
            self.capabilities,
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'HandshakeHello':
        """Decode HELLO message."""
        if len(data) < 101:  # 1 + 32 + 32 + 32 + 4
            raise STTHandshakeError("Insufficient data for HELLO message")
        
        try:
            version, node_id, ephemeral_key, nonce, caps = struct.unpack(
                '!B32s32s32sI',
                data[:101]
            )
        except struct.error as e:
            raise STTHandshakeError(f"Failed to parse HELLO: {e}")
        
        return cls(
            version=version,
            node_id=node_id,
            ephemeral_public_key=ephemeral_key,
            nonce=nonce,
            capabilities=caps,
        )


@dataclass
class HandshakeHelloResponse:
    """HELLO_RESP message structure."""
    
    version: int
    node_id: bytes  # 32 bytes
    ephemeral_public_key: bytes  # 32 bytes
    nonce_reply: bytes  # 32 bytes
    chosen_capabilities: int
    
    def to_bytes(self) -> bytes:
        """Encode HELLO_RESP message."""
        if len(self.node_id) != 32:
            raise STTHandshakeError("Node ID must be 32 bytes")
        if len(self.ephemeral_public_key) != 32:
            raise STTHandshakeError("Ephemeral public key must be 32 bytes")
        if len(self.nonce_reply) != 32:
            raise STTHandshakeError("Nonce reply must be 32 bytes")
        
        return struct.pack(
            '!B32s32s32sI',
            self.version,
            self.node_id,
            self.ephemeral_public_key,
            self.nonce_reply,
            self.chosen_capabilities,
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'HandshakeHelloResponse':
        """Decode HELLO_RESP message."""
        if len(data) < 101:
            raise STTHandshakeError("Insufficient data for HELLO_RESP message")
        
        try:
            version, node_id, ephemeral_key, nonce_reply, caps = struct.unpack(
                '!B32s32s32sI',
                data[:101]
            )
        except struct.error as e:
            raise STTHandshakeError(f"Failed to parse HELLO_RESP: {e}")
        
        return cls(
            version=version,
            node_id=node_id,
            ephemeral_public_key=ephemeral_key,
            nonce_reply=nonce_reply,
            chosen_capabilities=caps,
        )


@dataclass
class SessionInit:
    """SESSION_INIT message structure."""
    
    session_id: bytes  # 8 bytes
    session_key_confirmation: bytes  # 32 bytes - HMAC of session data
    
    def to_bytes(self) -> bytes:
        """Encode SESSION_INIT message."""
        if len(self.session_id) != 8:
            raise STTHandshakeError("Session ID must be 8 bytes")
        if len(self.session_key_confirmation) != 32:
            raise STTHandshakeError("Session key confirmation must be 32 bytes")
        
        return self.session_id + self.session_key_confirmation
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'SessionInit':
        """Decode SESSION_INIT message."""
        if len(data) < 40:  # 8 + 32
            raise STTHandshakeError("Insufficient data for SESSION_INIT message")
        
        return cls(
            session_id=data[:8],
            session_key_confirmation=data[8:40],
        )


@dataclass
class AuthProof:
    """AUTH_PROOF message structure."""
    
    challenge_response: bytes  # 64 bytes - signed challenge
    peer_verification: bytes  # 32 bytes - HMAC proof
    
    def to_bytes(self) -> bytes:
        """Encode AUTH_PROOF message."""
        if len(self.challenge_response) != 64:
            raise STTHandshakeError("Challenge response must be 64 bytes")
        if len(self.peer_verification) != 32:
            raise STTHandshakeError("Peer verification must be 32 bytes")
        
        return self.challenge_response + self.peer_verification
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'AuthProof':
        """Decode AUTH_PROOF message."""
        if len(data) < 96:  # 64 + 32
            raise STTHandshakeError("Insufficient data for AUTH_PROOF message")
        
        return cls(
            challenge_response=data[:64],
            peer_verification=data[64:96],
        )


class HandshakeManager:
    """Manages the handshake process for establishing secure sessions."""
    
    def __init__(self, node_id: bytes, private_key: Optional[bytes] = None):
        """
        Initialize handshake manager.
        
        Args:
            node_id: This node's identifier (32 bytes)
            private_key: Optional long-term private key for authentication
        """
        if len(node_id) != 32:
            raise STTHandshakeError("Node ID must be 32 bytes")
        
        self.node_id = node_id
        self.private_key = private_key
        
        # Default capabilities
        self.capabilities = (
            STT_CAP_STREAMS |
            STT_CAP_KEY_ROTATION |
            STT_CAP_SESSION_RESUMPTION |
            STT_CAP_FLOW_CONTROL
        )
    
    def create_hello(self, ephemeral_public_key: bytes) -> HandshakeHello:
        """
        Create HELLO message.
        
        Args:
            ephemeral_public_key: Ephemeral public key (32 bytes)
            
        Returns:
            HandshakeHello message
        """
        nonce = secrets.token_bytes(32)
        
        return HandshakeHello(
            version=STT_VERSION,
            node_id=self.node_id,
            ephemeral_public_key=ephemeral_public_key,
            nonce=nonce,
            capabilities=self.capabilities,
        )
    
    def create_hello_response(
        self,
        hello: HandshakeHello,
        ephemeral_public_key: bytes,
    ) -> HandshakeHelloResponse:
        """
        Create HELLO_RESP message in response to HELLO.
        
        Args:
            hello: Received HELLO message
            ephemeral_public_key: Our ephemeral public key
            
        Returns:
            HandshakeHelloResponse message
        """
        if hello.version != STT_VERSION:
            raise STTHandshakeError(
                f"Version mismatch: expected {STT_VERSION}, got {hello.version}"
            )
        
        # Choose capabilities (intersection)
        chosen_caps = hello.capabilities & self.capabilities
        
        nonce_reply = secrets.token_bytes(32)
        
        return HandshakeHelloResponse(
            version=STT_VERSION,
            node_id=self.node_id,
            ephemeral_public_key=ephemeral_public_key,
            nonce_reply=nonce_reply,
            chosen_capabilities=chosen_caps,
        )
    
    def derive_session_id(
        self,
        hello: HandshakeHello,
        hello_resp: HandshakeHelloResponse,
    ) -> bytes:
        """
        Derive session ID from handshake data.
        
        Args:
            hello: HELLO message
            hello_resp: HELLO_RESP message
            
        Returns:
            8-byte session ID
        """
        # Combine handshake data
        combined = (
            hello.node_id +
            hello.ephemeral_public_key +
            hello.nonce +
            hello_resp.node_id +
            hello_resp.ephemeral_public_key +
            hello_resp.nonce_reply
        )
        
        # Hash and truncate to 8 bytes
        # In production, use STC KDF for proper derivation
        import hashlib
        session_hash = hashlib.sha256(combined).digest()
        return session_hash[:8]
