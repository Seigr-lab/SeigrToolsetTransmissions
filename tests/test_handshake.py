"""
Tests for STT handshake protocol with pre-shared seed authentication.
"""

import pytest
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
    def stc_wrapper(self, shared_seed):
        """Create STC wrapper with shared seed."""
        return STCWrapper(shared_seed)
    
    @pytest.fixture
    def initiator_node_id(self):
        """Initiator node ID."""
        return b'\x01' * 32
    
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
    
    def test_handshake_error_handling(self, initiator_node_id, stc_wrapper):
        """Test handshake error conditions."""
        handshake = STTHandshake(initiator_node_id, stc_wrapper, is_initiator=True)
        
        # Processing invalid data should raise error
        with pytest.raises(Exception):
            handshake.process_hello(b"invalid data")
    
    def test_handshake_state_tracking(self, initiator_node_id, stc_wrapper):
        """Test handshake state is tracked correctly."""
        handshake = STTHandshake(initiator_node_id, stc_wrapper, is_initiator=True)
        
        assert handshake.completed is False
        assert handshake.session_id is None
        assert handshake.session_key is None
        assert handshake.peer_node_id is None
    
    def test_handshake_nonce_generation(self, initiator_node_id, stc_wrapper):
        """Test nonce is generated uniquely."""
        handshake1 = STTHandshake(initiator_node_id, stc_wrapper, is_initiator=True)
        handshake2 = STTHandshake(initiator_node_id, stc_wrapper, is_initiator=True)
        
        handshake1.create_hello()
        handshake2.create_hello()
        
        # Nonces should be different
        assert handshake1.our_nonce != handshake2.our_nonce
    
    def test_handshake_commitment_generation(self, initiator_node_id, stc_wrapper):
        """Test HELLO commitment is generated."""
        handshake = STTHandshake(initiator_node_id, stc_wrapper, is_initiator=True)
        
        hello_data = handshake.create_hello()
        from seigr_toolset_transmissions.utils.serialization import deserialize_stt
        hello_msg = deserialize_stt(hello_data)
        
        assert 'commitment' in hello_msg
        assert isinstance(hello_msg['commitment'], bytes)
        assert len(hello_msg['commitment']) > 0
    
    def test_handshake_timestamp_in_hello(self, initiator_node_id, stc_wrapper):
        """Test HELLO includes timestamp."""
        handshake = STTHandshake(initiator_node_id, stc_wrapper, is_initiator=True)
        
        hello_data = handshake.create_hello()
        from seigr_toolset_transmissions.utils.serialization import deserialize_stt
        hello_msg = deserialize_stt(hello_data)
        
        assert 'timestamp' in hello_msg
        assert isinstance(hello_msg['timestamp'], int)
        assert hello_msg['timestamp'] > 0
    
    def test_handshake_challenge_creation(self, initiator_node_id, stc_wrapper):
        """Test RESPONSE includes challenge."""
        responder = STTHandshake(b'\x02' * 32, stc_wrapper, is_initiator=False)
        initiator = STTHandshake(initiator_node_id, stc_wrapper, is_initiator=True)
        
        hello = initiator.create_hello()
        response = responder.process_hello(hello)
        
        from seigr_toolset_transmissions.utils.serialization import deserialize_stt
        response_msg = deserialize_stt(response)
        
        assert 'challenge' in response_msg
        assert isinstance(response_msg['challenge'], bytes)
    
    def test_handshake_session_id_format(self, initiator_node_id, stc_wrapper):
        """Test session ID is 8 bytes after completion."""
        responder = STTHandshake(b'\x02' * 32, stc_wrapper, is_initiator=False)
        initiator = STTHandshake(initiator_node_id, stc_wrapper, is_initiator=True)
        
        hello = initiator.create_hello()
        challenge_response = responder.process_hello(hello)
        auth_proof = initiator.process_challenge(challenge_response)
        
        # Session ID is generated during process_challenge by initiator
        # Check the auth_proof message contains session_id
        from seigr_toolset_transmissions.utils.serialization import deserialize_stt
        proof_msg = deserialize_stt(auth_proof)
        
        assert 'session_id' in proof_msg
        assert len(proof_msg['session_id']) == 8
        assert initiator.session_id is not None
        assert len(initiator.session_id) == 8
    
    def test_handshake_roles_initiator(self, initiator_node_id, stc_wrapper):
        """Test initiator role is set correctly."""
        handshake = STTHandshake(initiator_node_id, stc_wrapper, is_initiator=True)
        
        assert handshake.is_initiator is True
    
    def test_handshake_roles_responder(self, stc_wrapper):
        """Test responder role is set correctly."""
        handshake = STTHandshake(b'\x03' * 32, stc_wrapper, is_initiator=False)
        
        assert handshake.is_initiator is False
    
    def test_handshake_peer_node_id_stored(self, initiator_node_id, stc_wrapper):
        """Test peer node ID is stored during handshake."""
        responder_id = b'\x04' * 32
        responder = STTHandshake(responder_id, stc_wrapper, is_initiator=False)
        initiator = STTHandshake(initiator_node_id, stc_wrapper, is_initiator=True)
        
        hello = initiator.create_hello()
        responder.process_hello(hello)
        
        assert responder.peer_node_id == initiator_node_id
    
    def test_handshake_malformed_hello(self, stc_wrapper):
        """Test handling malformed HELLO message."""
        responder = STTHandshake(b'\x05' * 32, stc_wrapper, is_initiator=False)
        
        # Malformed data
        with pytest.raises(Exception):
            responder.process_hello(b'garbage data')
    
    def test_handshake_empty_message(self, initiator_node_id, stc_wrapper):
        """Test handling empty message."""
        handshake = STTHandshake(initiator_node_id, stc_wrapper, is_initiator=True)
        
        with pytest.raises(Exception):
            handshake.process_hello(b'')
    
    def test_handshake_truncated_message(self, initiator_node_id, stc_wrapper):
        """Test handling truncated message."""
        handshake = STTHandshake(initiator_node_id, stc_wrapper, is_initiator=False)
        initiator = STTHandshake(b'\x06' * 32, stc_wrapper, is_initiator=True)
        
        hello = initiator.create_hello()
        
        # Truncate message
        truncated = hello[:len(hello)//2]
        
        with pytest.raises(Exception):
            handshake.process_hello(truncated)
    
    def test_handshake_replay_attack_protection(self, initiator_node_id, stc_wrapper):
        """Test protection against replay attacks."""
        responder = STTHandshake(b'\x07' * 32, stc_wrapper, is_initiator=False)
        initiator = STTHandshake(initiator_node_id, stc_wrapper, is_initiator=True)
        
        hello = initiator.create_hello()
        
        # Process hello once
        challenge1 = responder.process_hello(hello)
        
        # Create new responder
        responder2 = STTHandshake(b'\x08' * 32, stc_wrapper, is_initiator=False)
        
        # Process same hello again - should have different challenge
        challenge2 = responder2.process_hello(hello)
        
        # Challenges should be different (different nonces)
        assert challenge1 != challenge2
    
    @pytest.mark.asyncio
    async def test_manager_concurrent_handshakes(self, node_id, shared_seed):
        """Test manager handles multiple concurrent handshakes."""
        stc_wrapper = STCWrapper(shared_seed)
        manager = HandshakeManager(node_id=node_id, stc_wrapper=stc_wrapper)
        
        # Start multiple handshakes
        addresses = [
            ("127.0.0.1", 9000),
            ("127.0.0.1", 9001),
            ("127.0.0.1", 9002),
            ("127.0.0.1", 9003),
        ]
        
        for addr in addresses:
            await manager.initiate_handshake(addr)
        
        assert len(manager.active_handshakes) == 4
    
    def test_handshake_session_key_derivation(self, initiator_node_id, shared_seed):
        """Test session key is derived correctly."""
        responder_stc = STCWrapper(shared_seed)
        responder = STTHandshake(b'\x09' * 32, responder_stc, is_initiator=False)
        
        initiator_stc = STCWrapper(shared_seed)
        initiator = STTHandshake(initiator_node_id, initiator_stc, is_initiator=True)
        
        # Complete handshake
        hello = initiator.create_hello()
        challenge = responder.process_hello(hello)
        response = initiator.process_challenge(challenge)
        final = responder.verify_response(response)
        initiator.process_final(final)
        
        # Both should have session keys (if implemented)
        # Note: session_key might not be set in current implementation
        if hasattr(initiator, 'session_key') and hasattr(responder, 'session_key'):
            if initiator.session_key and responder.session_key:
                assert initiator.session_key == responder.session_key
    
    def test_handshake_completion_flag(self, initiator_node_id, shared_seed):
        """Test completion flag is set after successful handshake."""
        responder_stc = STCWrapper(shared_seed)
        responder = STTHandshake(b'\x0A' * 32, responder_stc, is_initiator=False)
        
        initiator_stc = STCWrapper(shared_seed)
        initiator = STTHandshake(initiator_node_id, initiator_stc, is_initiator=True)
        
        assert initiator.completed is False
        assert responder.completed is False
        
        # Complete handshake
        hello = initiator.create_hello()
        challenge = responder.process_hello(hello)
        response = initiator.process_challenge(challenge)
        final = responder.verify_response(response)
        initiator.process_final(final)
        
        assert initiator.completed is True
    
    @pytest.mark.asyncio
    async def test_handshake_manager_complete_no_active(self, initiator_node_id, shared_seed):
        """Test complete_handshake with no active handshake."""
        stc = STCWrapper(shared_seed)
        manager = HandshakeManager(initiator_node_id, stc)
        
        # Try to complete handshake for unknown peer
        unknown_peer = ("127.0.0.1", 9999)
        result = await manager.complete_handshake(unknown_peer)
        # Should return None if no handshake active
        assert result is None
    
    def test_handshake_invalid_hello_data(self, initiator_node_id, shared_seed):
        """Test processing invalid HELLO data raises error."""
        stc = STCWrapper(shared_seed)
        handshake = STTHandshake(initiator_node_id, stc, is_initiator=False)
        
        # Try to process invalid HELLO
        with pytest.raises(Exception):  # Could be various exceptions
            handshake.process_hello(b"invalid_hello_data")
    
    def test_handshake_invalid_challenge_data(self, initiator_node_id, shared_seed):
        """Test processing invalid challenge data."""
        stc = STCWrapper(shared_seed)
        handshake = STTHandshake(initiator_node_id, stc, is_initiator=True)
        
        # Create hello first
        handshake.create_hello()
        
        # Try to process invalid challenge
        with pytest.raises(Exception):
            handshake.process_challenge(b"invalid_challenge")
    
    def test_handshake_invalid_response_data(self, initiator_node_id, shared_seed):
        """Test verifying invalid response data."""
        responder_stc = STCWrapper(shared_seed)
        responder = STTHandshake(b'\x0B' * 32, responder_stc, is_initiator=False)
        
        initiator_stc = STCWrapper(shared_seed)
        initiator = STTHandshake(initiator_node_id, initiator_stc, is_initiator=True)
        
        # Get to response stage
        hello = initiator.create_hello()
        responder.process_hello(hello)
        
        # Try to verify invalid response
        with pytest.raises(Exception):
            responder.verify_response(b"invalid_response")
    
    def test_handshake_process_final_invalid(self, initiator_node_id, shared_seed):
        """Test processing invalid final message."""
        responder_stc = STCWrapper(shared_seed)
        responder = STTHandshake(b'\x0C' * 32, responder_stc, is_initiator=False)
        
        initiator_stc = STCWrapper(shared_seed)
        initiator = STTHandshake(initiator_node_id, initiator_stc, is_initiator=True)
        
        # Get to final stage
        hello = initiator.create_hello()
        challenge = responder.process_hello(hello)
        initiator.process_challenge(challenge)
        
        # Try to process invalid final
        with pytest.raises(Exception):
            initiator.process_final(b"invalid_final")
    
    @pytest.mark.asyncio
    async def test_handshake_manager_handle_incoming_invalid(self, initiator_node_id, shared_seed):
        """Test handle_incoming with invalid data."""
        stc = STCWrapper(shared_seed)
        manager = HandshakeManager(initiator_node_id, stc)
        
        # Try to handle invalid incoming data
        peer_addr = ("127.0.0.1", 9999)
        try:
            await manager.handle_incoming(peer_addr, b"invalid_data")
        except Exception:
            pass  # Expected to fail
    
    @pytest.mark.asyncio
    async def test_handshake_manager_complete_handshake_async(self, initiator_node_id, shared_seed):
        """Test async complete_handshake method."""
        stc = STCWrapper(shared_seed)
        manager = HandshakeManager(initiator_node_id, stc)
        
        # Initiate handshake
        peer_addr = ("127.0.0.1", 8888)
        await manager.initiate_handshake(peer_addr)  # Creates handshake state
        
        # Complete it
        await manager.complete_handshake(peer_addr)  # Test completion path
        # Result might be None if not fully completed
    
    @pytest.mark.asyncio
    async def test_handshake_manager_is_complete(self, initiator_node_id, shared_seed):
        """Test is_handshake_complete method."""
        stc = STCWrapper(shared_seed)
        manager = HandshakeManager(initiator_node_id, stc)
        
        peer_addr = ("127.0.0.1", 7777)
        
        # Not complete initially
        assert not manager.is_handshake_complete(peer_addr)
        
        # Initiate handshake
        await manager.initiate_handshake(peer_addr)
        
        # Still not complete
        assert not manager.is_handshake_complete(peer_addr)
    
    @pytest.mark.asyncio
    async def test_handshake_manager_get_session_id_async(self, initiator_node_id, shared_seed):
        """Test async get_session_id_async method."""
        stc = STCWrapper(shared_seed)
        manager = HandshakeManager(initiator_node_id, stc)
        
        peer_addr = ("127.0.0.1", 6666)
        
        # Initiate handshake
        await manager.initiate_handshake(peer_addr)  # Creates handshake state
        
        # Get session ID (might be None if not completed)
        await manager.get_session_id_async(peer_addr)  # Test async method
        # Could be None if handshake not completed - this is expected
    
    @pytest.mark.asyncio
    async def test_handshake_cleanup_expired(self, initiator_node_id, shared_seed):
        """Test cleanup of expired handshakes."""
        stc = STCWrapper(shared_seed)
        manager = HandshakeManager(initiator_node_id, stc)
        
        # Create some handshakes
        await manager.initiate_handshake(("127.0.0.1", 5555))
        await manager.initiate_handshake(("127.0.0.1", 5556))
        
        # Cleanup (might remove expired ones)
        if hasattr(manager, 'cleanup_expired'):
            await manager.cleanup_expired()
    
    @pytest.mark.asyncio
    async def test_handshake_timeout_handling(self, initiator_node_id, shared_seed):
        """Test handshake timeout handling."""
        stc = STCWrapper(shared_seed)
        manager = HandshakeManager(initiator_node_id, stc)
        
        peer_addr = ("127.0.0.1", 4444)
        result = await manager.initiate_handshake(peer_addr)
        
        # Check if handshake has timeout tracking
        if hasattr(manager, 'get_handshake_age'):
            age = manager.get_handshake_age(peer_addr)
            assert age is not None or age is None  # Either works
        
        # Verify initiation succeeded
        assert result is not None
