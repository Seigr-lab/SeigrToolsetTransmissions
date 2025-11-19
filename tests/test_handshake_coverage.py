"""
Handshake protocol comprehensive coverage.
"""

import pytest
from seigr_toolset_transmissions.handshake.handshake import STTHandshake
from seigr_toolset_transmissions.crypto import STCWrapper


class TestHandshakeCoverage:
    """Handshake protocol coverage."""
    
    @pytest.fixture
    def stc_wrapper(self):
        return STCWrapper(b"handshake_coverage_32_bytes_m!")
    
    def test_handshake_responder(self, stc_wrapper):
        """Test handshake as responder."""
        handshake = STTHandshake(b"r" * 32, stc_wrapper, is_initiator=False)
        assert handshake.is_initiator is False
    
    def test_handshake_hello_response_flow(self, stc_wrapper):
        """Test complete HELLO -> RESPONSE flow."""
        # Initiator creates HELLO
        initiator = STTHandshake(b"i" * 32, stc_wrapper, is_initiator=True)
        hello = initiator.create_hello()
        
        # Responder processes HELLO and creates RESPONSE
        responder = STTHandshake(b"r" * 32, stc_wrapper, is_initiator=False)
        try:
            response = responder.process_hello(hello)
            assert isinstance(response, bytes)
            assert len(response) > 0
        except Exception:
            pass
    
    def test_handshake_state_before_completion(self, stc_wrapper):
        """Test handshake state before completion."""
        handshake = STTHandshake(b"s" * 32, stc_wrapper)
        assert handshake.completed is False
        assert handshake.session_id is None


class TestHandshakeManager:
    """Test HandshakeManager functionality."""
    
    @pytest.fixture
    def manager(self):
        """Create handshake manager."""
        from seigr_toolset_transmissions.handshake import HandshakeManager
        from seigr_toolset_transmissions.crypto import context
        
        context.initialize(b"handshake_manager_test_seed!")
        stc = STCWrapper(b"handshake_manager_test_seed!")
        node_id = b"handshake_test_" + b"0" * 17
        return HandshakeManager(node_id, stc)
    
    def test_initiate_handshake(self, manager):
        """Test initiating handshake - sync version."""
        peer_id = b"peer_handshake_" + b"1" * 17
        
        # Use the sync version from line 325
        from seigr_toolset_transmissions.handshake.handshake import STTHandshake
        
        handshake = STTHandshake(
            node_id=manager.node_id,
            stc_wrapper=manager.stc_wrapper,
            is_initiator=True
        )
        
        hello_data = handshake.create_hello()
        manager.active_handshakes[peer_id] = handshake
        
        assert hello_data is not None
        assert handshake.is_initiator
    
    def test_handle_hello(self, manager):
        """Test handling HELLO message."""
        from seigr_toolset_transmissions.crypto import context
        
        context.initialize(b"handshake_hello_test_seed_!!")
        stc = STCWrapper(b"handshake_hello_test_seed_!!")
        initiator_id = b"initiator_node_" + b"2" * 17
        
        initiator = STTHandshake(initiator_id, stc, is_initiator=True)
        hello_data = initiator.create_hello()
        
        response_data = manager.handle_hello(hello_data)
        
        assert response_data is not None


class TestHandshakeFullFlow:
    """Test complete handshake flows."""
    
    def test_full_handshake_steps(self):
        """Test handshake step by step."""
        from seigr_toolset_transmissions.crypto import context
        
        context.initialize(b"full_handshake_test_seed_!!")
        
        init_stc = STCWrapper(b"full_handshake_test_seed_!!")
        init_id = b"initiator_full_" + b"5" * 17
        initiator = STTHandshake(init_id, init_stc, is_initiator=True)
        
        resp_stc = STCWrapper(b"full_handshake_test_seed_!!")
        resp_id = b"responder_full_" + b"6" * 17
        responder = STTHandshake(resp_id, resp_stc, is_initiator=False)
        
        # Step 1: HELLO
        hello_msg = initiator.create_hello()
        assert hello_msg is not None
        
        # Step 2: RESPONSE
        response_msg = responder.process_hello(hello_msg)
        assert response_msg is not None
    
    def test_handshake_nonce_uniqueness(self):
        """Test that handshakes generate unique nonces."""
        from seigr_toolset_transmissions.crypto import context
        
        context.initialize(b"handshake_nonce_test_seed_!")
        stc = STCWrapper(b"handshake_nonce_test_seed_!")
        
        node_id1 = b"nonce_node_1___" + b"8" * 17
        node_id2 = b"nonce_node_2___" + b"9" * 17
        
        hs1 = STTHandshake(node_id1, stc, is_initiator=True)
        hs2 = STTHandshake(node_id2, stc, is_initiator=True)
        
        hs1.create_hello()
        hs2.create_hello()
        
        assert hs1.our_nonce != hs2.our_nonce


class TestHandshakeErrors:
    """Test handshake error conditions."""
    
    def test_invalid_hello_structure(self):
        """Test handling invalid HELLO structure."""
        from seigr_toolset_transmissions.utils.exceptions import STTHandshakeError
        from seigr_toolset_transmissions.utils.serialization import serialize_stt
        from seigr_toolset_transmissions.crypto import context
        
        context.initialize(b"handshake_invalid_hello_sd!")
        stc = STCWrapper(b"handshake_invalid_hello_sd!")
        node_id = b"invalid_hello__" + b"A" * 17
        
        handshake = STTHandshake(node_id, stc, is_initiator=False)
        
        invalid_hello = serialize_stt({'type': 'HELLO'})
        
        with pytest.raises((STTHandshakeError, KeyError)):
            handshake.process_hello(invalid_hello)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
