"""
Tests for STT session management with STC key rotation.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.session import STTSession as Session, SessionManager
from seigr_toolset_transmissions.crypto import STCWrapper
from seigr_toolset_transmissions.utils.exceptions import STTSessionError


class TestSession:
    """Test session management and key rotation."""
    
    @pytest.fixture
    def session_id(self):
        """Session ID for tests."""
        return b'\x01\x02\x03\x04\x05\x06\x07\x08'
    
    @pytest.fixture
    def peer_node_id(self):
        """Peer node ID."""
        return b'\xaa' * 32
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper for tests."""
        return STCWrapper(b"session_seed_32_bytes_minimum!")
    
    def test_create_session(self, session_id, peer_node_id, stc_wrapper):
        """Test creating a session."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        assert session.session_id == session_id
        assert session.peer_node_id == peer_node_id
        assert session.is_active is True
    
    def test_session_key_rotation(self, session_id, peer_node_id, stc_wrapper):
        """Test rotating session keys."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        # Get initial key version
        initial_version = session.key_version
        
        # Rotate keys
        session.rotate_keys(stc_wrapper)
        
        # Key version should increment
        assert session.key_version == initial_version + 1
    
    def test_session_key_rotation_updates_wrapper(self, session_id, peer_node_id):
        """Test key rotation updates STC wrapper."""
        stc_wrapper = STCWrapper(b"rotation_seed_32_bytes_minimum!")
        
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        # Create new wrapper for rotation
        new_wrapper = STCWrapper(b"new_seed_32_bytes_minimum!!!!!!!!")
        
        # Rotate with new wrapper
        session.rotate_keys(new_wrapper)
        
        assert session.key_version == 1
    
    def test_session_close(self, session_id, peer_node_id, stc_wrapper):
        """Test closing a session."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        assert session.is_active is True
        
        session.close()
        
        assert session.is_active is False
    
    def test_session_statistics(self, session_id, peer_node_id, stc_wrapper):
        """Test session statistics tracking."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        # Simulate traffic
        session.record_sent_bytes(1024)
        session.record_received_bytes(2048)
        
        stats = session.get_statistics()
        
        assert stats['bytes_sent'] == 1024
        assert stats['bytes_received'] == 2048
        assert stats['key_version'] >= 0
    
    def test_session_invalid_id_length(self, peer_node_id, stc_wrapper):
        """Test that invalid session ID length raises error."""
        with pytest.raises(STTSessionError):
            Session(
                session_id=b'\x00' * 7,  # Wrong length
                peer_node_id=peer_node_id,
                stc_wrapper=stc_wrapper,
            )
    
    def test_session_with_metadata(self, session_id, peer_node_id, stc_wrapper):
        """Test session with custom metadata."""
        metadata = {
            'connection_type': 'udp',
            'endpoint': '127.0.0.1:8000',
        }
        
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
            metadata=metadata,
        )
        
        assert session.metadata == metadata


class TestSessionManager:
    """Test session manager for multiple sessions."""
    
    @pytest.fixture
    def session_id(self):
        """Session ID for tests."""
        return b'\x01\x02\x03\x04\x05\x06\x07\x08'
    
    @pytest.fixture
    def peer_node_id(self):
        """Peer node ID."""
        return b'\xaa' * 32
    
    @pytest.fixture
    def node_id(self):
        """Node ID for manager."""
        return b'\x01' * 32
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper for tests."""
        return STCWrapper(b"manager_seed_32_bytes_minimum!!")
    
    @pytest.fixture
    def manager(self, node_id, stc_wrapper):
        """Create session manager."""
        return SessionManager(node_id=node_id, stc_wrapper=stc_wrapper)
    
    @pytest.mark.asyncio
    async def test_create_session(self, manager):
        """Test creating a session through manager."""
        session_id = b'\x01' * 8
        peer_node_id = b'\x02' * 32
        
        session = await manager.create_session(
            session_id=session_id,
            peer_node_id=peer_node_id,
        )
        
        assert session is not None
        assert session.session_id == session_id
        assert manager.has_session(session_id)
    
    @pytest.mark.asyncio
    async def test_get_session(self, manager):
        """Test getting a session."""
        session_id = b'\x02' * 8
        peer_node_id = b'\x03' * 32
        
        # Create session
        created = await manager.create_session(
            session_id=session_id,
            peer_node_id=peer_node_id,
        )
        
        # Get session
        retrieved = manager.get_session(session_id)
        
        assert retrieved is created
    
    @pytest.mark.asyncio
    async def test_close_session(self, manager):
        """Test closing a session through manager."""
        session_id = b'\x03' * 8
        peer_node_id = b'\x04' * 32
        
        # Create session
        await manager.create_session(
            session_id=session_id,
            peer_node_id=peer_node_id,
        )
        
        assert manager.has_session(session_id)
        
        # Close session
        await manager.close_session(session_id)
        
        # Session still exists but is closed
        assert manager.has_session(session_id)
        session = manager.get_session(session_id)
        assert session.is_closed()
        
        # Cleanup removes it
        removed = await manager.cleanup_closed_sessions()
        assert removed == 1
        assert not manager.has_session(session_id)
    
    @pytest.mark.asyncio
    async def test_rotate_all_keys(self, manager, stc_wrapper):
        """Test rotating keys for all sessions."""
        # Create multiple sessions
        session_ids = [b'\x04' * 8, b'\x05' * 8, b'\x06' * 8]
        peer_ids = [b'\x05' * 32, b'\x06' * 32, b'\x07' * 32]
        
        for sid, pid in zip(session_ids, peer_ids):
            await manager.create_session(session_id=sid, peer_node_id=pid)
        
        # Rotate all keys
        await manager.rotate_all_keys(stc_wrapper)
        
        # Verify all sessions have rotated keys
        for sid in session_ids:
            session = manager.get_session(sid)
            assert session.key_version >= 1
    
    @pytest.mark.asyncio
    async def test_list_sessions(self, manager):
        """Test listing all sessions."""
        # Create sessions
        session_ids = [b'\x07' * 8, b'\x08' * 8]
        peer_ids = [b'\x08' * 32, b'\x09' * 32]
        
        for sid, pid in zip(session_ids, peer_ids):
            await manager.create_session(session_id=sid, peer_node_id=pid)
        
        sessions = manager.list_sessions()
        
        assert len(sessions) == 2
        assert all(s.is_active for s in sessions)
    
    @pytest.mark.asyncio
    async def test_cleanup_inactive_sessions(self, manager):
        """Test cleaning up inactive sessions."""
        # Create and close session
        session_id = b'\x09' * 8
        peer_node_id = b'\x0a' * 32
        
        session = await manager.create_session(
            session_id=session_id,
            peer_node_id=peer_node_id,
        )
        
        # Close session
        session.close()
        
        # Cleanup
        removed = await manager.cleanup_inactive()
        
        assert removed == 1
        assert not manager.has_session(session_id)
    
    @pytest.mark.asyncio
    async def test_session_timeout(self, manager):
        """Test session timeout handling."""
        session_id = b'\x0a' * 8
        peer_node_id = b'\x0b' * 32
        
        # Create session with short timeout
        await manager.create_session(
            session_id=session_id,
            peer_node_id=peer_node_id,
        )
        
        # Simulate timeout
        session = manager.get_session(session_id)
        session._last_activity = 0  # Force old timestamp
        
        # Cleanup expired
        removed = await manager.cleanup_expired(max_idle=1)
        
        assert removed >= 1
    
    @pytest.mark.asyncio
    async def test_concurrent_session_creation(self, manager):
        """Test creating sessions concurrently."""
        async def create(idx):
            session_id = bytes([idx] * 8)
            peer_id = bytes([idx + 10] * 32)
            return await manager.create_session(session_id, peer_id)
        
        # Create 10 sessions concurrently
        sessions = await asyncio.gather(*[create(i) for i in range(10)])
        
        assert len(sessions) == 10
        assert all(s is not None for s in sessions)
        assert len(manager.list_sessions()) == 10
    
    def test_session_metadata(self, session_id, peer_node_id, stc_wrapper):
        """Test session metadata storage and retrieval."""
        metadata = {"type": "test", "priority": 1, "custom_data": [1, 2, 3]}
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
            metadata=metadata
        )
        
        assert session.metadata == metadata
        assert session.metadata["type"] == "test"
        assert session.metadata["priority"] == 1
    
    def test_session_statistics_tracking(self, session_id, peer_node_id, stc_wrapper):
        """Test session statistics are tracked correctly."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        # Initially zero
        assert session.frames_sent == 0
        assert session.frames_received == 0
        assert session.bytes_sent == 0
        assert session.bytes_received == 0
        
        # Record some activity
        session.record_frame_sent(100)
        session.record_frame_sent(200)
        session.record_frame_received(150)
        
        assert session.frames_sent == 2
        assert session.frames_received == 1
        assert session.bytes_sent == 300
        assert session.bytes_received == 150
    
    def test_session_activity_updates(self, session_id, peer_node_id, stc_wrapper):
        """Test session activity timestamp updates."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        initial_activity = session.last_activity
        
        # Wait a bit
        import time
        time.sleep(0.01)
        
        session.update_activity()
        
        assert session.last_activity > initial_activity
    
    def test_session_id_validation(self, peer_node_id, stc_wrapper):
        """Test session ID must be 8 bytes."""
        with pytest.raises(STTSessionError, match="must be 8 bytes"):
            Session(
                session_id=b'\x01\x02\x03',  # Too short
                peer_node_id=peer_node_id,
                stc_wrapper=stc_wrapper,
            )
        
        with pytest.raises(STTSessionError, match="must be 8 bytes"):
            Session(
                session_id=b'\x01' * 16,  # Too long
                peer_node_id=peer_node_id,
                stc_wrapper=stc_wrapper,
            )
    
    def test_session_key_version_increment(self, session_id, peer_node_id, stc_wrapper):
        """Test key version increments on rotation."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        assert session.key_version == 0
        session.rotate_keys(stc_wrapper)
        assert session.key_version == 1
        session.rotate_keys(stc_wrapper)
        assert session.key_version == 2
    
    def test_session_double_close(self, session_id, peer_node_id, stc_wrapper):
        """Test closing session twice is safe."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        session.close()
        assert session.is_closed()
        
        # Second close should be safe
        session.close()
        assert session.is_closed()
    
    @pytest.mark.asyncio
    async def test_manager_duplicate_session_id(self, manager):
        """Test creating session with duplicate ID raises error."""
        session_id = b'\xAA' * 8
        peer_id = b'\xBB' * 32
        
        await manager.create_session(session_id, peer_id)
        
        # Try to create again with same ID
        with pytest.raises(STTSessionError, match="already exists"):
            await manager.create_session(session_id, peer_id)
    
    @pytest.mark.asyncio
    async def test_manager_get_nonexistent_session(self, manager):
        """Test getting nonexistent session returns None."""
        session_id = b'\xCC' * 8
        
        session = manager.get_session(session_id)
        assert session is None
    
    @pytest.mark.asyncio
    async def test_manager_close_nonexistent_session(self, manager):
        """Test closing nonexistent session raises error."""
        session_id = b'\xDD' * 8
        
        with pytest.raises(STTSessionError, match="not found"):
            await manager.close_session(session_id)
    
    @pytest.mark.asyncio
    async def test_manager_session_count(self, manager):
        """Test session count tracking."""
        assert manager.session_count() == 0
        
        # Create 3 sessions
        for i in range(3):
            session_id = bytes([0xE0 + i] * 8)
            peer_id = bytes([0xF0 + i] * 32)
            await manager.create_session(session_id, peer_id)
        
        assert manager.session_count() == 3
        
        # Close one
        await manager.close_session(bytes([0xE0] * 8))
        await manager.cleanup_closed_sessions()
        
        assert manager.session_count() == 2
    
    def test_session_str_repr(self, session_id, peer_node_id, stc_wrapper):
        """Test session string representation."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        str_repr = str(session)
        assert session_id.hex() in str_repr or repr(session_id) in str_repr
    
    def test_session_capabilities(self, session_id, peer_node_id, stc_wrapper):
        """Test session capabilities field."""
        capabilities = 0b1011  # Some capability flags
        
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
            capabilities=capabilities
        )
        
        assert session.capabilities == capabilities
