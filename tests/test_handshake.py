"""
Tests for handshake protocol.
"""

import pytest
from seigr_toolset_transmissions.handshake import (
    HandshakeHello,
    HandshakeHelloResponse,
    HandshakeManager,
)
from seigr_toolset_transmissions.utils.constants import STT_VERSION
from seigr_toolset_transmissions.utils.exceptions import STTHandshakeError


class TestHandshake:
    """Test handshake protocol."""
    
    def test_hello_creation(self):
        """Test creating HELLO message."""
        node_id = b'\x01' * 32
        ephemeral_key = b'\x02' * 32
        nonce = b'\x03' * 32
        
        hello = HandshakeHello(
            version=STT_VERSION,
            node_id=node_id,
            ephemeral_public_key=ephemeral_key,
            nonce=nonce,
            capabilities=0xFF,
        )
        
        assert hello.version == STT_VERSION
        assert hello.node_id == node_id
    
    def test_hello_encoding_decoding(self):
        """Test HELLO message encoding and decoding."""
        node_id = b'\xaa' * 32
        ephemeral_key = b'\xbb' * 32
        nonce = b'\xcc' * 32
        
        original = HandshakeHello(
            version=STT_VERSION,
            node_id=node_id,
            ephemeral_public_key=ephemeral_key,
            nonce=nonce,
            capabilities=0x0F,
        )
        
        encoded = original.to_bytes()
        decoded = HandshakeHello.from_bytes(encoded)
        
        assert decoded.version == original.version
        assert decoded.node_id == original.node_id
        assert decoded.ephemeral_public_key == original.ephemeral_public_key
        assert decoded.nonce == original.nonce
        assert decoded.capabilities == original.capabilities
    
    def test_hello_response_encoding_decoding(self):
        """Test HELLO_RESP message encoding and decoding."""
        node_id = b'\x11' * 32
        ephemeral_key = b'\x22' * 32
        nonce_reply = b'\x33' * 32
        
        original = HandshakeHelloResponse(
            version=STT_VERSION,
            node_id=node_id,
            ephemeral_public_key=ephemeral_key,
            nonce_reply=nonce_reply,
            chosen_capabilities=0x03,
        )
        
        encoded = original.to_bytes()
        decoded = HandshakeHelloResponse.from_bytes(encoded)
        
        assert decoded.version == original.version
        assert decoded.node_id == original.node_id
        assert decoded.chosen_capabilities == original.chosen_capabilities
    
    def test_handshake_manager_creation(self):
        """Test creating handshake manager."""
        node_id = b'\xff' * 32
        
        manager = HandshakeManager(node_id)
        
        assert manager.node_id == node_id
        assert manager.capabilities > 0
    
    def test_handshake_manager_create_hello(self):
        """Test handshake manager creating HELLO."""
        node_id = b'\x99' * 32
        ephemeral_key = b'\x88' * 32
        
        manager = HandshakeManager(node_id)
        hello = manager.create_hello(ephemeral_key)
        
        assert hello.version == STT_VERSION
        assert hello.node_id == node_id
        assert hello.ephemeral_public_key == ephemeral_key
        assert len(hello.nonce) == 32
    
    def test_handshake_manager_create_hello_response(self):
        """Test handshake manager creating HELLO_RESP."""
        node_id = b'\x77' * 32
        ephemeral_key = b'\x66' * 32
        
        manager = HandshakeManager(node_id)
        
        # Create incoming HELLO
        hello = HandshakeHello(
            version=STT_VERSION,
            node_id=b'\x55' * 32,
            ephemeral_public_key=b'\x44' * 32,
            nonce=b'\x33' * 32,
            capabilities=0xFF,
        )
        
        # Create response
        response = manager.create_hello_response(hello, ephemeral_key)
        
        assert response.version == STT_VERSION
        assert response.node_id == node_id
        assert response.chosen_capabilities <= hello.capabilities
    
    def test_derive_session_id(self):
        """Test session ID derivation."""
        manager = HandshakeManager(b'\x00' * 32)
        
        hello = HandshakeHello(
            version=STT_VERSION,
            node_id=b'\x01' * 32,
            ephemeral_public_key=b'\x02' * 32,
            nonce=b'\x03' * 32,
            capabilities=0,
        )
        
        hello_resp = HandshakeHelloResponse(
            version=STT_VERSION,
            node_id=b'\x04' * 32,
            ephemeral_public_key=b'\x05' * 32,
            nonce_reply=b'\x06' * 32,
            chosen_capabilities=0,
        )
        
        session_id = manager.derive_session_id(hello, hello_resp)
        
        assert isinstance(session_id, bytes)
        assert len(session_id) == 8
