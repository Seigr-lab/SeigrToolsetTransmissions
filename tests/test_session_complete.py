"""Comprehensive session.py coverage tests."""

import pytest
import time
import secrets
from unittest.mock import Mock

from seigr_toolset_transmissions.session.session import (
    STTSession,
    SessionManager
)
from seigr_toolset_transmissions.crypto import STCWrapper
from seigr_toolset_transmissions.utils.exceptions import STTSessionError


class TestSessionMethods:
    """Test STTSession method coverage."""
    
    def test_is_closed_when_active(self):
        """Test is_closed returns False when active."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        session = STTSession(b'\x11' * 8, b'\x22' * 8, stc)
        
        assert session.is_active
        assert not session.is_closed()
    
    def test_is_closed_after_close(self):
        """Test is_closed returns True after close."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        session = STTSession(b'\x11' * 8, b'\x22' * 8, stc)
        
        session.close()
        assert not session.is_active
        assert session.is_closed()
    
    def test_get_statistics_alias(self):
        """Test get_statistics alias method."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        session = STTSession(b'\x11' * 8, b'\x22' * 8, stc)
        
        stats = session.get_statistics()
        assert 'session_id' in stats
        assert 'peer_node_id' in stats
        assert stats['is_active']
    
    def test_is_active_method(self):
        """Test is_active_method returns active status."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        session = STTSession(b'\x11' * 8, b'\x22' * 8, stc)
        
        assert session.is_active_method()
        
        session.close()
        assert not session.is_active_method()


class TestSessionKeyRotation:
    """Test async key rotation."""
    
    @pytest.mark.asyncio
    async def test_rotate_key_with_existing_key(self):
        """Test rotating existing session key."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        session = STTSession(b'\x11' * 8, b'\x22' * 8, stc)
        
        # Set initial session key
        session.session_key = b"initial_key_32_bytes_minimum_!!"
        initial_version = session.key_version
        
        # Mock the rotate method
        stc.rotate_session_key = Mock(return_value=b"rotated_key_32_bytes_minimum!")
        
        await session.rotate_key(stc)
        
        assert session.key_version == initial_version + 1
        assert stc.rotate_session_key.called
    
    @pytest.mark.asyncio
    async def test_rotate_key_without_existing_key(self):
        """Test rotating when no session key exists yet."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        session = STTSession(b'\x11' * 8, b'\x22' * 8, stc)
        
        # No session key initially
        assert session.session_key is None
        
        # Mock derive method
        stc.derive_session_key = Mock(return_value=b"derived_key_32_bytes_minimum!!")
        
        await session.rotate_key(stc)
        
        assert session.session_key is not None
        assert session.key_version == 1
        assert stc.derive_session_key.called


class TestSessionRecordingMethods:
    """Test session data recording methods."""
    
    def test_record_sent_bytes(self):
        """Test record_sent_bytes method."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        session = STTSession(b'\x11' * 8, b'\x22' * 8, stc)
        
        initial_bytes = session.bytes_sent
        session.record_sent_bytes(100)
        
        assert session.bytes_sent == initial_bytes + 100
    
    def test_record_received_bytes(self):
        """Test record_received_bytes method."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        session = STTSession(b'\x11' * 8, b'\x22' * 8, stc)
        
        initial_bytes = session.bytes_received
        session.record_received_bytes(200)
        
        assert session.bytes_received == initial_bytes + 200
    
    def test_record_frame_sent(self):
        """Test record_frame_sent updates both count and bytes."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        session = STTSession(b'\x11' * 8, b'\x22' * 8, stc)
        
        session.record_frame_sent(150)
        
        assert session.frames_sent == 1
        assert session.bytes_sent == 150
    
    def test_record_frame_received(self):
        """Test record_frame_received updates both count and bytes."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        session = STTSession(b'\x11' * 8, b'\x22' * 8, stc)
        
        session.record_frame_received(250)
        
        assert session.frames_received == 1
        assert session.bytes_received == 250


class TestSessionManagerOperations:
    """Test SessionManager operations."""
    
    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test creating a session."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = SessionManager(b'\xAA' * 8, stc)
        
        session_id = b'\x11' * 8
        peer_id = b'\x22' * 8
        
        session = await mgr.create_session(session_id, peer_id)
        
        assert session.session_id == session_id
        assert session.peer_node_id == peer_id
        assert mgr.has_session(session_id)
    
    def test_get_session(self):
        """Test getting existing session."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = SessionManager(b'\xAA' * 8, stc)
        
        session_id = b'\x11' * 8
        session = STTSession(session_id, b'\x22' * 8, stc)
        mgr.sessions[session_id] = session
        
        retrieved = mgr.get_session(session_id)
        assert retrieved is session
    
    def test_get_session_nonexistent(self):
        """Test getting nonexistent session returns None."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = SessionManager(b'\xAA' * 8, stc)
        
        result = mgr.get_session(b'\xFF' * 8)
        assert result is None
    
    def test_close_session(self):
        """Test closing a session."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = SessionManager(b'\xAA' * 8, stc)
        
        session_id = b'\x11' * 8
        session = STTSession(session_id, b'\x22' * 8, stc)
        mgr.sessions[session_id] = session
        
        mgr.close_session(session_id)
        
        assert not session.is_active
        assert not mgr.has_session(session_id)
    
    def test_close_nonexistent_session(self):
        """Test closing nonexistent session doesn't raise error."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = SessionManager(b'\xAA' * 8, stc)
        
        # Should not raise error
        mgr.close_session(b'\xFF' * 8)
    
    def test_list_sessions(self):
        """Test listing all session IDs."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = SessionManager(b'\xAA' * 8, stc)
        
        session_id1 = b'\x11' * 8
        session_id2 = b'\x22' * 8
        
        mgr.sessions[session_id1] = STTSession(session_id1, b'\x99' * 8, stc)
        mgr.sessions[session_id2] = STTSession(session_id2, b'\x88' * 8, stc)
        
        session_ids = mgr.list_sessions()
        
        assert len(session_ids) == 2
        assert session_id1 in session_ids
        assert session_id2 in session_ids


class TestSessionManagerCleanup:
    """Test SessionManager cleanup operations."""
    
    @pytest.mark.asyncio
    async def test_cleanup_inactive_sessions(self):
        """Test cleanup removes inactive sessions."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = SessionManager(b'\xAA' * 8, stc)
        
        # Create active and inactive sessions
        active_id = b'\x11' * 8
        inactive_id = b'\x22' * 8
        
        active_session = STTSession(active_id, b'\x99' * 8, stc)
        inactive_session = STTSession(inactive_id, b'\x88' * 8, stc)
        inactive_session.is_active = False
        
        mgr.sessions[active_id] = active_session
        mgr.sessions[inactive_id] = inactive_session
        
        removed = await mgr.cleanup_inactive(timeout=600)
        
        assert removed == 1
        assert mgr.has_session(active_id)
        assert not mgr.has_session(inactive_id)
    
    @pytest.mark.asyncio
    async def test_cleanup_inactive_by_timeout(self):
        """Test cleanup removes sessions by timeout."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = SessionManager(b'\xAA' * 8, stc)
        
        # Create session with old activity
        old_id = b'\x11' * 8
        old_session = STTSession(old_id, b'\x99' * 8, stc)
        old_session.last_activity = time.time() - 1000  # 1000 seconds ago
        
        mgr.sessions[old_id] = old_session
        
        removed = await mgr.cleanup_inactive(timeout=500)
        
        assert removed == 1
        assert not mgr.has_session(old_id)
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_alias(self):
        """Test cleanup_expired is alias for cleanup_inactive."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = SessionManager(b'\xAA' * 8, stc)
        
        # Create old session
        old_id = b'\x11' * 8
        old_session = STTSession(old_id, b'\x99' * 8, stc)
        old_session.last_activity = time.time() - 1000
        
        mgr.sessions[old_id] = old_session
        
        removed = await mgr.cleanup_expired(max_idle=500)
        
        assert removed == 1
        assert not mgr.has_session(old_id)


class TestSessionManagerKeyRotation:
    """Test SessionManager key rotation."""
    
    @pytest.mark.asyncio
    async def test_rotate_all_keys_for_active_sessions(self):
        """Test rotating keys for all active sessions."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        mgr = SessionManager(b'\xAA' * 8, stc)
        
        # Create active and inactive sessions
        active_id = b'\x11' * 8
        inactive_id = b'\x22' * 8
        
        active_session = STTSession(active_id, b'\x99' * 8, stc)
        inactive_session = STTSession(inactive_id, b'\x88' * 8, stc)
        inactive_session.is_active = False
        
        mgr.sessions[active_id] = active_session
        mgr.sessions[inactive_id] = inactive_session
        
        initial_version_active = active_session.key_version
        initial_version_inactive = inactive_session.key_version
        
        new_stc = STCWrapper(b"new_key_32_bytes_minimum_sized!!")
        await mgr.rotate_all_keys(new_stc)
        
        # Active session should have rotated
        assert active_session.key_version == initial_version_active + 1
        
        # Inactive session should not have rotated
        assert inactive_session.key_version == initial_version_inactive


class TestSessionConstruction:
    """Test session construction validation."""
    
    def test_session_invalid_id_length(self):
        """Test session raises error for invalid ID length."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        
        with pytest.raises(STTSessionError, match="Session ID must be 8 bytes"):
            STTSession(b'\x11' * 7, b'\x22' * 8, stc)
    
    def test_session_with_metadata(self):
        """Test session accepts metadata."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        metadata = {'role': 'client', 'version': '1.0'}
        
        session = STTSession(b'\x11' * 8, b'\x22' * 8, stc, metadata=metadata)
        
        assert session.metadata == metadata
        assert session.metadata['role'] == 'client'
    
    def test_session_default_metadata(self):
        """Test session creates empty metadata dict if not provided."""
        stc = STCWrapper(b"test_key_32_bytes_minimum_size!!")
        
        session = STTSession(b'\x11' * 8, b'\x22' * 8, stc)
        
        assert isinstance(session.metadata, dict)
        assert len(session.metadata) == 0
