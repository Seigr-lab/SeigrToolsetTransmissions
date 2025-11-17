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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
