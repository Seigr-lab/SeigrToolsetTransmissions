"""
Tests for STT handshake protocol with pre-shared seed authentication.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.handshake import (
    STTHandshake,
    HandshakeManager,
)
from seigr_toolset_transmissions.crypto import STCWrapper
from seigr_toolset_transmissions.utils.exceptions import STTHandshakeError


class TestSTTHandshake:
    """Test pre-shared seed handshake protocol."""
    
    @pytest.fixture
    def shared_seed(self):
        """Shared seed for authentication."""
        return b"shared_seed_32_bytes_minimum!!"
    
    @pytest.fixture
    def stc_wrapper(self, shared_seed):
        """Create STC wrapper with shared seed."""
        return STCWrapper(shared_seed)
    
    @pytest.fixture
    def initiator_node_id(self):
        """Initiator node ID."""
        return b'\x01' * 32
    
    @pytest.fixture
    def responder_node_id(self):
        """Responder node ID."""
        return b'\x02' * 32
    
    def test_handshake_creation(self, initiator_node_id, stc_wrapper):
        """Test creating a handshake."""
        handshake = STTHandshake(
            node_id=initiator_node_id,
            stc_wrapper=stc_wrapper,
            is_initiator=True,
        )
        
        assert handshake.node_id == initiator_node_id
        assert handshake.is_initiator is True
        assert handshake.session_id is None
    
    def test_create_hello(self, initiator_node_id, stc_wrapper):
        """Test creating hello message."""
        handshake = STTHandshake(
            node_id=initiator_node_id,
            stc_wrapper=stc_wrapper,
            is_initiator=True,
        )
        
        hello_data = handshake.create_hello()
        
        assert isinstance(hello_data, bytes)
        assert len(hello_data) > 0
        # Should contain node ID
        assert initiator_node_id in hello_data
    
    def test_process_hello(self, initiator_node_id, responder_node_id, shared_seed):
        """Test processing hello message."""
        # Create initiator
        initiator_stc = STCWrapper(shared_seed)
        initiator = STTHandshake(
            node_id=initiator_node_id,
            stc_wrapper=initiator_stc,
            is_initiator=True,
        )
        
        hello_data = initiator.create_hello()
        
        # Create responder
        responder_stc = STCWrapper(shared_seed)
        responder = STTHandshake(
            node_id=responder_node_id,
            stc_wrapper=responder_stc,
            is_initiator=False,
        )
        
        # Process hello
        challenge_data = responder.process_hello(hello_data)
        
        assert isinstance(challenge_data, bytes)
        assert len(challenge_data) > 0
        assert responder.peer_node_id == initiator_node_id
    
    def test_process_challenge(self, initiator_node_id, responder_node_id, shared_seed):
        """Test processing challenge response."""
        # Setup initiator and responder
        initiator_stc = STCWrapper(shared_seed)
        initiator = STTHandshake(
            node_id=initiator_node_id,
            stc_wrapper=initiator_stc,
            is_initiator=True,
        )
        
        responder_stc = STCWrapper(shared_seed)
        responder = STTHandshake(
            node_id=responder_node_id,
            stc_wrapper=responder_stc,
            is_initiator=False,
        )
        
        # Exchange hello/challenge
        hello_data = initiator.create_hello()
        challenge_data = responder.process_hello(hello_data)
        
        # Process challenge
        response_data = initiator.process_challenge(challenge_data)
        
        assert isinstance(response_data, bytes)
        assert initiator.peer_node_id == responder_node_id
        assert initiator.session_id is not None
    
    def test_verify_response(self, initiator_node_id, responder_node_id, shared_seed):
        """Test verifying challenge response."""
        # Setup
        initiator_stc = STCWrapper(shared_seed)
        initiator = STTHandshake(
            node_id=initiator_node_id,
            stc_wrapper=initiator_stc,
            is_initiator=True,
        )
        
        responder_stc = STCWrapper(shared_seed)
        responder = STTHandshake(
            node_id=responder_node_id,
            stc_wrapper=responder_stc,
            is_initiator=False,
        )
        
        # Full exchange
        hello_data = initiator.create_hello()
        challenge_data = responder.process_hello(hello_data)
        response_data = initiator.process_challenge(challenge_data)
        
        # Verify response
        final_data = responder.verify_response(response_data)
        
        assert final_data is not None
        assert responder.session_id is not None
        assert responder.session_id == initiator.session_id
    
    def test_full_handshake(self, initiator_node_id, responder_node_id, shared_seed):
        """Test complete handshake flow."""
        # Create both sides
        initiator_stc = STCWrapper(shared_seed)
        initiator = STTHandshake(
            node_id=initiator_node_id,
            stc_wrapper=initiator_stc,
            is_initiator=True,
        )
        
        responder_stc = STCWrapper(shared_seed)
        responder = STTHandshake(
            node_id=responder_node_id,
            stc_wrapper=responder_stc,
            is_initiator=False,
        )
        
        # 1. Initiator creates hello
        hello = initiator.create_hello()
        
        # 2. Responder processes hello, creates challenge
        challenge = responder.process_hello(hello)
        
        # 3. Initiator processes challenge, creates response
        response = initiator.process_challenge(challenge)
        
        # 4. Responder verifies response, creates final
        final = responder.verify_response(response)
        
        # 5. Initiator processes final confirmation
        initiator.process_final(final)
        
        # Verify both have matching session IDs
        assert initiator.session_id == responder.session_id
        assert initiator.peer_node_id == responder_node_id
        assert responder.peer_node_id == initiator_node_id
    
    def test_handshake_wrong_seed(self, initiator_node_id, responder_node_id):
        """Test handshake with mismatched seeds fails."""
        # Different seeds
        initiator_stc = STCWrapper(b"seed_one_32_bytes_minimum!!!!!")
        initiator = STTHandshake(
            node_id=initiator_node_id,
            stc_wrapper=initiator_stc,
            is_initiator=True,
        )
        
        responder_stc = STCWrapper(b"seed_two_32_bytes_minimum!!!!!")
        responder = STTHandshake(
            node_id=responder_node_id,
            stc_wrapper=responder_stc,
            is_initiator=False,
        )
        
        # Create hello
        hello = initiator.create_hello()
        
        # Responder creates challenge (doesn't fail yet)
        challenge = responder.process_hello(hello)
        
        # Initiator tries to decrypt challenge - THIS should fail
        with pytest.raises(STTHandshakeError):
            initiator.process_response(challenge)
    
    def test_handshake_serialization(self, initiator_node_id, stc_wrapper):
        """Test handshake message serialization."""
        handshake = STTHandshake(
            node_id=initiator_node_id,
            stc_wrapper=stc_wrapper,
            is_initiator=True,
        )
        
        hello = handshake.create_hello()
        
        # Should be valid STT binary format
        assert isinstance(hello, bytes)
        # Should not be JSON or msgpack
        assert not hello.startswith(b'{')
        assert not hello.startswith(b'\x80')


class TestHandshakeManager:
    """Test handshake manager for multiple concurrent handshakes."""
    
    @pytest.fixture
    def shared_seed(self):
        """Shared seed for tests."""
        return b"manager_seed_32_bytes_minimum!"
    
    @pytest.fixture
    def node_id(self):
        """Node ID for manager."""
        return b'\x01' * 32
    
    @pytest.fixture
    def manager(self, node_id, shared_seed):
        """Create handshake manager."""
        stc_wrapper = STCWrapper(shared_seed)
        return HandshakeManager(node_id=node_id, stc_wrapper=stc_wrapper)
    
    @pytest.mark.asyncio
    async def test_initiate_handshake(self, manager):
        """Test initiating a handshake."""
        peer_address = ("127.0.0.1", 8000)
        
        handshake = await manager.initiate_handshake(peer_address)
        
        assert handshake is not None
        assert handshake.is_initiator is True
        assert peer_address in manager.active_handshakes
    
    @pytest.mark.asyncio
    async def test_handle_incoming_handshake(self, manager):
        """Test handling incoming handshake."""
        peer_address = ("127.0.0.1", 8001)
        
        # Create fake hello message
        peer_stc = STCWrapper(b"manager_seed_32_bytes_minimum!")
        peer_handshake = STTHandshake(
            node_id=b'\x02' * 32,
            stc_wrapper=peer_stc,
            is_initiator=True,
        )
        hello = peer_handshake.create_hello()
        
        # Handle incoming
        response = await manager.handle_incoming(peer_address, hello)
        
        assert response is not None
        assert isinstance(response, bytes)
        assert peer_address in manager.active_handshakes
    
    @pytest.mark.asyncio
    async def test_complete_handshake(self, manager, node_id, shared_seed):
        """Test completing a handshake through manager."""
        peer_address = ("127.0.0.1", 8002)
        
        # Create peer manager
        peer_stc = STCWrapper(shared_seed)
        peer_manager = HandshakeManager(
            node_id=b'\x02' * 32,
            stc_wrapper=peer_stc,
        )
        
        # Initiate from manager
        handshake = await manager.initiate_handshake(peer_address)
        hello = handshake.create_hello()
        
        # Peer processes hello
        challenge = await peer_manager.handle_incoming(peer_address, hello)
        
        # Manager processes challenge
        response = await manager.handle_incoming(peer_address, challenge)
        
        # Peer processes response
        final = await peer_manager.handle_incoming(peer_address, response)
        
        # Manager processes final
        await manager.handle_incoming(peer_address, final)
        
        # Both should have completed handshakes
        assert manager.is_handshake_complete(peer_address)
    
    @pytest.mark.asyncio
    async def test_timeout_handshake(self, manager):
        """Test handshake timeout cleanup."""
        peer_address = ("127.0.0.1", 8003)
        
        # Start handshake
        await manager.initiate_handshake(peer_address)
        
        assert peer_address in manager.active_handshakes
        
        # Clean up old handshakes (with very short timeout)
        manager.cleanup_timeouts(max_age=0)
        
        # Should be removed
        assert peer_address not in manager.active_handshakes
    
    @pytest.mark.asyncio
    async def test_get_session_id(self, manager, shared_seed):
        """Test getting session ID from completed handshake."""
        peer_address = ("127.0.0.1", 8004)
        
        # Create and complete handshake
        peer_stc = STCWrapper(shared_seed)
        peer_handshake = STTHandshake(
            node_id=b'\x02' * 32,
            stc_wrapper=peer_stc,
            is_initiator=False,
        )
        
        # Initiate
        handshake = await manager.initiate_handshake(peer_address)
        hello = handshake.create_hello()
        
        # Exchange messages
        challenge = peer_handshake.process_hello(hello)
        response = await manager.handle_incoming(peer_address, challenge)
        final = peer_handshake.verify_response(response)
        await manager.handle_incoming(peer_address, final)
        
        # Get session ID
        session_id = manager.get_session_id(peer_address)
        
        assert session_id is not None
        assert len(session_id) == 8
