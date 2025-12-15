"""
Edge case tests for session/continuity.py to achieve 100% coverage.

Targets uncovered lines:
- Lines 334-335: save_session_state() when no resumption token
- Lines 339-340: save_session_state() when no registry entry
- Line 348: save_session_state() with stream_states update
- Line 393: get_resumption_info() when no registry entry for token
"""

import pytest
from seigr_toolset_transmissions.session.continuity import CryptoSessionContinuity
from seigr_toolset_transmissions.session.session import STTSession
from seigr_toolset_transmissions.crypto.stc_wrapper import STCWrapper


@pytest.fixture
def stc_wrapper():
    """Create STC wrapper for testing."""
    return STCWrapper(b'continuity_test_seed_32bytes!')


@pytest.fixture
def continuity_manager(stc_wrapper):
    """Create continuity manager."""
    return CryptoSessionContinuity(stc_wrapper, resumption_timeout=3600)


@pytest.fixture
def session(stc_wrapper):
    """Create a test session."""
    session_id = b'testses1'
    peer_node_id = b'peer_node_test_seed_32bytes!!'
    
    session = STTSession(session_id, peer_node_id, stc_wrapper)
    session.transport_type = 'udp'
    return session


class TestSaveSessionStateEdgeCases:
    """Test save_session_state() edge cases."""
    
    def test_save_state_no_resumption_token(self, continuity_manager, session):
        """Test save_session_state() when session has no resumption token (lines 334-335)."""
        # Session is not in continuity manager, so no token exists
        # This should log warning and return early
        continuity_manager.save_session_state(session)
        
        # Should not raise exception, just return silently
        assert session.session_id not in continuity_manager.session_tokens
    
    def test_save_state_no_registry_entry(self, continuity_manager, session):
        """Test save_session_state() when token exists but no registry entry (lines 339-340)."""
        # Create a token but don't register it
        fake_token = b'fake_token_12345'
        continuity_manager.session_tokens[session.session_id] = fake_token
        
        # Registry doesn't have this token
        assert fake_token not in continuity_manager.session_registry
        
        # Should log warning and return early (lines 339-340)
        continuity_manager.save_session_state(session)
        
        # Clean up
        del continuity_manager.session_tokens[session.session_id]
    
    def test_save_state_with_stream_states(self, continuity_manager, stc_wrapper):
        """Test save_session_state() with stream_states update (line 348)."""
        peer_id = b'peer_node_test_seed_32bytes!!'
        node_seed = b'node_seed_32bytes_for_testing!'
        shared_seed = b'shared_32bytes_for_test_usage!'
        
        # Create resumable session
        session_id, token = continuity_manager.create_resumable_session(
            peer_id, node_seed, shared_seed
        )
        
        # Create session
        session = STTSession(session_id, peer_id, stc_wrapper)
        session.transport_type = 'udp'
        
        # Define stream states to save
        stream_states = {
            1: {'last_sequence': 100, 'bytes_sent': 5000},
            2: {'last_sequence': 50, 'bytes_sent': 2500}
        }
        
        # Save state with stream_states (should hit line 348)
        continuity_manager.save_session_state(session, stream_states=stream_states)
        
        # Verify stream states were saved
        state = continuity_manager.session_registry[token]
        assert state.stream_states == stream_states


class TestGetResumptionInfoEdgeCases:
    """Test get_resumption_info() edge cases."""
    
    def test_get_resumption_info_no_registry_entry(self, continuity_manager, session):
        """Test get_resumption_info() when token exists but no registry entry (line 393)."""
        # Create a token mapping but don't create registry entry
        fake_token = b'fake_token_no_registry'
        continuity_manager.session_tokens[session.session_id] = fake_token
        
        # Registry doesn't have this token
        assert fake_token not in continuity_manager.session_registry
        
        # Should return None (line 393)
        info = continuity_manager.get_resumption_info(session.session_id)
        assert info is None
        
        # Clean up
        del continuity_manager.session_tokens[session.session_id]
    
    def test_get_resumption_info_valid(self, continuity_manager, stc_wrapper):
        """Test get_resumption_info() with valid session."""
        peer_id = b'peer_node_test_seed_32bytes!!'
        node_seed = b'node_seed_32bytes_for_testing!'
        shared_seed = b'shared_32bytes_for_test_usage!'
        
        # Create resumable session
        session_id, _token = continuity_manager.create_resumable_session(
            peer_id, node_seed, shared_seed
        )
        
        # Get resumption info
        info = continuity_manager.get_resumption_info(session_id)
        
        # Should return valid info
        assert info is not None
        assert info['session_id'] == session_id.hex()
        assert info['peer_node_id'] == peer_id.hex()
        assert 'age' in info
        assert 'resume_count' in info


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
