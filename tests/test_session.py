"""
Tests for session management.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.session import STTSession, SessionManager
from seigr_toolset_transmissions.utils.constants import (
    STT_SESSION_STATE_INIT,
    STT_SESSION_STATE_ACTIVE,
    STT_SESSION_STATE_CLOSED,
)
from seigr_toolset_transmissions.utils.exceptions import STTSessionError


class TestSTTSession:
    """Test STT session."""
    
    def test_session_creation(self):
        """Test creating a session."""
        session_id = b'\x01' * 8
        peer_id = b'\x02' * 32
        local_id = b'\x03' * 32
        
        session = STTSession(
            session_id=session_id,
            peer_node_id=peer_id,
            local_node_id=local_id,
        )
        
        assert session.session_id == session_id
        assert session.peer_node_id == peer_id
        assert session.state == STT_SESSION_STATE_INIT
    
    def test_sequence_numbers(self):
        """Test sequence number handling."""
        session_id = b'\x04' * 8
        peer_id = b'\x05' * 32
        local_id = b'\x06' * 32
        
        session = STTSession(
            session_id=session_id,
            peer_node_id=peer_id,
            local_node_id=local_id,
        )
        
        # Test send sequence
        seq1 = session.next_send_sequence()
        seq2 = session.next_send_sequence()
        assert seq2 == seq1 + 1
        
        # Test receive sequence verification
        assert session.verify_recv_sequence(0)
        assert session.verify_recv_sequence(1)
        assert not session.verify_recv_sequence(0)  # Out of order
    
    def test_should_rotate_keys(self):
        """Test key rotation threshold detection."""
        session_id = b'\x07' * 8
        peer_id = b'\x08' * 32
        local_id = b'\x09' * 32
        
        session = STTSession(
            session_id=session_id,
            peer_node_id=peer_id,
            local_node_id=local_id,
            state=STT_SESSION_STATE_ACTIVE,
        )
        
        # Initially should not need rotation
        assert not session.should_rotate_keys()
        
        # Simulate large data transfer
        from seigr_toolset_transmissions.utils.constants import (
            STT_KEY_ROTATION_DATA_THRESHOLD
        )
        session.bytes_transmitted = STT_KEY_ROTATION_DATA_THRESHOLD + 1
        
        # Now should need rotation
        assert session.should_rotate_keys()
    
    @pytest.mark.asyncio
    async def test_session_close(self):
        """Test closing session."""
        session_id = b'\x0a' * 8
        peer_id = b'\x0b' * 32
        local_id = b'\x0c' * 32
        
        session = STTSession(
            session_id=session_id,
            peer_node_id=peer_id,
            local_node_id=local_id,
        )
        
        await session.close()
        
        assert session.state == STT_SESSION_STATE_CLOSED
        assert session.is_closed()
    
    def test_session_stats(self):
        """Test getting session statistics."""
        session_id = b'\x0d' * 8
        peer_id = b'\x0e' * 32
        local_id = b'\x0f' * 32
        
        session = STTSession(
            session_id=session_id,
            peer_node_id=peer_id,
            local_node_id=local_id,
        )
        
        stats = session.get_stats()
        
        assert 'session_id' in stats
        assert 'send_sequence' in stats
        assert 'stream_stats' in stats


class TestSessionManager:
    """Test session manager."""
    
    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test creating sessions."""
        local_id = b'\x10' * 32
        manager = SessionManager(local_id)
        
        session_id = b'\x11' * 8
        peer_id = b'\x12' * 32
        
        session = await manager.create_session(
            session_id=session_id,
            peer_node_id=peer_id,
        )
        
        assert session is not None
        assert session.session_id == session_id
    
    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test getting session by ID."""
        local_id = b'\x13' * 32
        manager = SessionManager(local_id)
        
        session_id = b'\x14' * 8
        peer_id = b'\x15' * 32
        
        session = await manager.create_session(
            session_id=session_id,
            peer_node_id=peer_id,
        )
        
        retrieved = await manager.get_session(session_id)
        
        assert retrieved is session
    
    @pytest.mark.asyncio
    async def test_close_all_sessions(self):
        """Test closing all sessions."""
        local_id = b'\x16' * 32
        manager = SessionManager(local_id)
        
        # Create multiple sessions
        session1 = await manager.create_session(
            session_id=b'\x17' * 8,
            peer_node_id=b'\x18' * 32,
        )
        session2 = await manager.create_session(
            session_id=b'\x19' * 8,
            peer_node_id=b'\x1a' * 32,
        )
        
        await manager.close_all_sessions()
        
        assert session1.is_closed()
        assert session2.is_closed()
    
    @pytest.mark.asyncio
    async def test_find_session_by_peer(self):
        """Test finding session by peer ID."""
        local_id = b'\x1b' * 32
        manager = SessionManager(local_id)
        
        peer_id = b'\x1c' * 32
        session = await manager.create_session(
            session_id=b'\x1d' * 8,
            peer_node_id=peer_id,
        )
        session.state = STT_SESSION_STATE_ACTIVE
        
        found = await manager.find_session_by_peer(peer_id)
        
        assert found is session
