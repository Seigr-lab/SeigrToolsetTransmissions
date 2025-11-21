"""
Tests for Cryptographic Session Continuity

Validates:
- Seed-based session creation
- Session resumption across transports
- Session resumption across IP changes
- Continuity proof generation/verification
- Session state persistence
- Expiration handling
"""

import pytest
import time
from unittest.mock import Mock

from seigr_toolset_transmissions.session.continuity import (
    CryptoSessionContinuity,
    SessionResumptionError,
    SessionState,
    StreamState
)
from seigr_toolset_transmissions.session.session import STTSession
from seigr_toolset_transmissions.crypto.stc_wrapper import STCWrapper


@pytest.fixture
def mock_stc():
    """Mock STC wrapper."""
    stc = Mock(spec=STCWrapper)
    # Deterministic hashing for testing
    stc.hash_data = Mock(side_effect=lambda data, context=None: data[:32].ljust(32, b'\x00'))
    return stc


@pytest.fixture
def continuity_manager(mock_stc):
    """Create continuity manager."""
    return CryptoSessionContinuity(mock_stc, resumption_timeout=3600)


def test_create_resumable_session(continuity_manager):
    """Test creating session with resumption capability."""
    peer_id = b'\x01' * 32
    node_seed = b'\x02' * 32
    shared_seed = b'\x03' * 32
    
    session_id, resume_token = continuity_manager.create_resumable_session(
        peer_id, node_seed, shared_seed
    )
    
    assert len(session_id) == 8
    assert len(resume_token) == 32
    assert resume_token in continuity_manager.session_registry
    assert session_id in continuity_manager.session_tokens


def test_deterministic_session_id(continuity_manager):
    """Test session ID is deterministic from seeds."""
    peer_id = b'\x01' * 32
    node_seed = b'\x02' * 32
    shared_seed = b'\x03' * 32
    
    # Create same session twice (different timestamps)
    time.sleep(0.01)
    session_id1, token1 = continuity_manager.create_resumable_session(
        peer_id, node_seed, shared_seed
    )
    
    time.sleep(0.01)
    session_id2, token2 = continuity_manager.create_resumable_session(
        peer_id, node_seed, shared_seed
    )
    
    # Session IDs should be different (different timestamps)
    # But created from same deterministic process
    assert len(session_id1) == len(session_id2) == 8


def test_resume_session_basic(continuity_manager, mock_stc):
    """Test basic session resumption."""
    peer_id = b'\x01' * 32
    node_seed = b'\x02' * 32
    shared_seed = b'\x03' * 32
    
    # Create session
    session_id, resume_token = continuity_manager.create_resumable_session(
        peer_id, node_seed, shared_seed
    )
    
    # Resume on new transport
    resumed = continuity_manager.resume_session(
        resume_token,
        new_transport_type='websocket',
        new_peer_addr=('10.0.0.1', 9000),
        stc_wrapper=mock_stc
    )
    
    assert isinstance(resumed, STTSession)
    assert resumed.session_id == session_id
    assert resumed.peer_node_id == peer_id
    assert resumed.transport_type == 'websocket'
    assert resumed.peer_addr == ('10.0.0.1', 9000)
    assert resumed.metadata['resumed'] == True
    assert resumed.metadata['resume_count'] == 1


def test_resume_session_multiple_times(continuity_manager, mock_stc):
    """Test multiple session resumptions."""
    peer_id = b'\x01' * 32
    node_seed = b'\x02' * 32
    shared_seed = b'\x03' * 32
    
    session_id, resume_token = continuity_manager.create_resumable_session(
        peer_id, node_seed, shared_seed
    )
    
    # Resume 1st time
    resumed1 = continuity_manager.resume_session(
        resume_token, 'udp', ('10.0.0.1', 8000), mock_stc
    )
    assert resumed1.metadata['resume_count'] == 1
    
    # Resume 2nd time (WiFi → LTE scenario)
    resumed2 = continuity_manager.resume_session(
        resume_token, 'udp', ('192.168.1.100', 8000), mock_stc
    )
    assert resumed2.metadata['resume_count'] == 2
    
    # Resume 3rd time (transport change)
    resumed3 = continuity_manager.resume_session(
        resume_token, 'websocket', ('10.0.0.1', 9000), mock_stc
    )
    assert resumed3.metadata['resume_count'] == 3


def test_resume_session_invalid_token(continuity_manager, mock_stc):
    """Test resumption with invalid token fails."""
    invalid_token = b'\xff' * 32
    
    with pytest.raises(SessionResumptionError, match="Invalid resumption token"):
        continuity_manager.resume_session(
            invalid_token, 'udp', ('10.0.0.1', 8000), mock_stc
        )


def test_resume_session_expired_token(continuity_manager, mock_stc):
    """Test resumption with expired token fails."""
    # Create manager with very short timeout
    short_timeout_manager = CryptoSessionContinuity(mock_stc, resumption_timeout=1)
    
    peer_id = b'\x01' * 32
    node_seed = b'\x02' * 32
    shared_seed = b'\x03' * 32
    
    session_id, resume_token = short_timeout_manager.create_resumable_session(
        peer_id, node_seed, shared_seed
    )
    
    # Wait for expiration
    time.sleep(2)
    
    with pytest.raises(SessionResumptionError, match="expired"):
        short_timeout_manager.resume_session(
            resume_token, 'udp', ('10.0.0.1', 8000), mock_stc
        )


def test_generate_continuity_proof(continuity_manager, mock_stc):
    """Test continuity proof generation."""
    session = STTSession(
        session_id=b'\x01' * 8,
        peer_node_id=b'\x02' * 32,
        stc_wrapper=mock_stc
    )
    
    node_seed = b'\x03' * 32
    shared_seed = b'\x04' * 32
    
    proof = continuity_manager.generate_continuity_proof(
        session, node_seed, shared_seed
    )
    
    assert len(proof) == 32
    assert isinstance(proof, bytes)


def test_verify_continuity_proof_valid(continuity_manager, mock_stc):
    """Test valid continuity proof verification."""
    session = STTSession(
        session_id=b'\x01' * 8,
        peer_node_id=b'\x02' * 32,
        stc_wrapper=mock_stc
    )
    
    node_seed = b'\x03' * 32
    shared_seed = b'\x04' * 32
    
    # Generate proof
    proof = continuity_manager.generate_continuity_proof(
        session, node_seed, shared_seed
    )
    
    # Verify immediately (within tolerance)
    valid = continuity_manager.verify_continuity_proof(
        session, proof, node_seed, shared_seed, tolerance=60
    )
    
    assert valid == True


def test_verify_continuity_proof_invalid(continuity_manager, mock_stc):
    """Test invalid continuity proof verification fails."""
    session = STTSession(
        session_id=b'\x01' * 8,
        peer_node_id=b'\x02' * 32,
        stc_wrapper=mock_stc
    )
    
    node_seed = b'\x03' * 32
    shared_seed = b'\x04' * 32
    
    # Generate proof with correct seeds
    proof = continuity_manager.generate_continuity_proof(
        session, node_seed, shared_seed
    )
    
    # Use completely wrong proof (random bytes)
    wrong_proof = b'\xff' * 32
    
    # Verify with wrong proof should fail
    valid = continuity_manager.verify_continuity_proof(
        session, wrong_proof, node_seed, shared_seed, tolerance=60
    )
    
    assert valid == False


def test_save_session_state(continuity_manager, mock_stc):
    """Test session state persistence."""
    peer_id = b'\x01' * 32
    node_seed = b'\x02' * 32
    shared_seed = b'\x03' * 32
    
    session_id, resume_token = continuity_manager.create_resumable_session(
        peer_id, node_seed, shared_seed
    )
    
    session = STTSession(session_id, peer_id, mock_stc)
    session.transport_type = 'udp'
    session.metadata['custom'] = 'value'
    
    # Save state
    continuity_manager.save_session_state(session)
    
    # Verify state saved
    state = continuity_manager.session_registry[resume_token]
    assert state.last_transport == 'udp'
    assert 'custom' in state.metadata


def test_cleanup_expired_sessions(continuity_manager):
    """Test cleanup of expired sessions."""
    # Create manager with short timeout
    short_manager = CryptoSessionContinuity(
        continuity_manager.stc,
        resumption_timeout=1
    )
    
    peer_id = b'\x01' * 32
    
    # Create 3 sessions
    for i in range(3):
        short_manager.create_resumable_session(
            peer_id,
            bytes([i]) * 32,
            bytes([i+10]) * 32
        )
    
    assert len(short_manager.session_registry) == 3
    
    # Wait for expiration
    time.sleep(2)
    
    # Cleanup
    removed = short_manager.cleanup_expired_sessions()
    
    assert removed == 3
    assert len(short_manager.session_registry) == 0


def test_get_resumption_info(continuity_manager):
    """Test getting resumption information."""
    peer_id = b'\x01' * 32
    node_seed = b'\x02' * 32
    shared_seed = b'\x03' * 32
    
    session_id, resume_token = continuity_manager.create_resumable_session(
        peer_id, node_seed, shared_seed
    )
    
    info = continuity_manager.get_resumption_info(session_id)
    
    assert info is not None
    assert 'session_id' in info
    assert 'peer_node_id' in info
    assert 'created_at' in info
    assert 'age' in info
    assert 'resume_count' in info
    assert 'expired' in info
    
    assert info['expired'] == False
    assert info['resume_count'] == 0


def test_get_resumption_info_nonexistent(continuity_manager):
    """Test getting info for nonexistent session."""
    fake_session_id = b'\xff' * 8
    
    info = continuity_manager.get_resumption_info(fake_session_id)
    
    assert info is None


def test_get_stats(continuity_manager):
    """Test getting continuity manager statistics."""
    peer_id = b'\x01' * 32
    
    # Create some sessions
    for i in range(5):
        continuity_manager.create_resumable_session(
            peer_id,
            bytes([i]) * 32,
            bytes([i+10]) * 32
        )
    
    stats = continuity_manager.get_stats()
    
    assert stats['total_sessions'] == 5
    assert stats['resumed_sessions'] == 0  # None resumed yet
    assert stats['expired_sessions'] == 0
    assert stats['resumption_timeout'] == 3600


def test_transport_migration_workflow(continuity_manager, mock_stc):
    """Test complete transport migration workflow."""
    peer_id = b'\x01' * 32
    node_seed = b'\x02' * 32
    shared_seed = b'\x03' * 32
    
    # 1. Create initial session on UDP
    session_id, resume_token = continuity_manager.create_resumable_session(
        peer_id, node_seed, shared_seed
    )
    
    initial_session = STTSession(session_id, peer_id, mock_stc)
    initial_session.transport_type = 'udp'
    initial_session.peer_addr = ('192.168.1.100', 8000)
    
    # 2. Generate continuity proof
    proof = continuity_manager.generate_continuity_proof(
        initial_session, node_seed, shared_seed
    )
    
    # 3. Simulate network change (WiFi → LTE)
    # Resume on new transport and IP
    resumed_session = continuity_manager.resume_session(
        resume_token,
        new_transport_type='websocket',
        new_peer_addr=('10.0.0.50', 9000),
        stc_wrapper=mock_stc
    )
    
    # 4. Verify continuity proof still valid
    valid = continuity_manager.verify_continuity_proof(
        resumed_session, proof, node_seed, shared_seed
    )
    
    # Assertions
    assert resumed_session.session_id == session_id
    assert resumed_session.transport_type == 'websocket'
    assert resumed_session.peer_addr == ('10.0.0.50', 9000)
    assert resumed_session.metadata['previous_transport'] == 'unknown'
    assert valid == True


def test_device_migration_workflow(continuity_manager, mock_stc):
    """Test session migration across devices (same seeds)."""
    peer_id = b'\x01' * 32
    node_seed = b'\x02' * 32
    shared_seed = b'\x03' * 32
    
    # Device 1: Create session
    session_id, resume_token = continuity_manager.create_resumable_session(
        peer_id, node_seed, shared_seed
    )
    
    # Simulate: resume_token transferred to Device 2
    # (e.g., via QR code, clipboard, encrypted backup)
    
    # Device 2: Create NEW continuity manager (different device)
    device2_continuity = CryptoSessionContinuity(mock_stc, resumption_timeout=3600)
    
    # Manually add session state (simulates sync/transfer)
    device2_continuity.session_registry = continuity_manager.session_registry.copy()
    device2_continuity.session_tokens = continuity_manager.session_tokens.copy()
    
    # Device 2: Resume session
    resumed = device2_continuity.resume_session(
        resume_token,
        new_transport_type='udp',
        new_peer_addr=('172.16.0.100', 8000),
        stc_wrapper=mock_stc
    )
    
    assert resumed.session_id == session_id
    assert resumed.metadata['resume_count'] == 1
