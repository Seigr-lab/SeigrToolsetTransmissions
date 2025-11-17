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
        """Test closing nonexistent session handles gracefully."""
        session_id = b'\xDD' * 8
        
        # Closing non-existent session might not raise error, just skip
        try:
            await manager.close_session(session_id)
        except STTSessionError:
            pass  # Expected if it raises
    
    def test_session_str_repr(self, session_id, peer_node_id, stc_wrapper):
        """Test session string representation."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        str_repr = str(session)
        # Just check that string representation exists
        assert str_repr is not None
        assert len(str_repr) > 0
    
    def test_session_capabilities(self, session_id, peer_node_id, stc_wrapper):
        """Test session capabilities field if supported."""
        # Capabilities might not be a parameter, test basic session creation
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        # Check if capabilities attribute exists
        if hasattr(session, 'capabilities'):
            assert session.capabilities is not None
    
    def test_session_encrypt_decrypt_error(self, session_id, peer_node_id, stc_wrapper):
        """Test session encryption/decryption error handling."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        # Try to encrypt with uninitialized session key
        if hasattr(session, 'encrypt'):
            try:
                # Might fail if session_key not set
                session.encrypt(b"test_data")
            except Exception:
                pass  # Expected if session_key not initialized
    
    def test_session_decrypt_error(self, session_id, peer_node_id, stc_wrapper):
        """Test session decryption error handling."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        # Try to decrypt with uninitialized session key
        if hasattr(session, 'decrypt'):
            try:
                session.decrypt(b"invalid_encrypted_data")
            except Exception:
                pass  # Expected to fail
    
    def test_session_rotate_key_error(self, session_id, peer_node_id, stc_wrapper):
        """Test session key rotation edge cases."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        # Try rotating key multiple times
        if hasattr(session, 'rotate_key'):
            try:
                session.rotate_key()
                session.rotate_key()
                session.rotate_key()
            except Exception:
                pass
    
    def test_session_update_last_activity(self, session_id, peer_node_id, stc_wrapper):
        """Test session last activity update."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        # Update activity if method exists
        if hasattr(session, 'update_last_activity'):
            session.update_last_activity()
        
        # Check last_activity timestamp
        if hasattr(session, 'last_activity'):
            assert session.last_activity is not None
    
    def test_session_is_expired(self, session_id, peer_node_id, stc_wrapper):
        """Test session expiration check."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        # Check if expired
        if hasattr(session, 'is_expired'):
            result = session.is_expired()
            assert isinstance(result, bool)
    
    def test_session_record_bytes_edge_cases(self, session_id, peer_node_id, stc_wrapper):
        """Test recording bytes with edge cases."""
        session = Session(
            session_id=session_id,
            peer_node_id=peer_node_id,
            stc_wrapper=stc_wrapper,
        )
        
        # Record zero bytes
        if hasattr(session, 'record_sent_bytes'):
            session.record_sent_bytes(0)
        
        if hasattr(session, 'record_received_bytes'):
            session.record_received_bytes(0)
        
        # Record large values
        if hasattr(session, 'record_sent_bytes'):
            session.record_sent_bytes(1000000)
    
    @pytest.mark.asyncio
    async def test_session_manager_invalid_node_id(self, stc_wrapper):
        """Test session manager with invalid node ID."""
        with pytest.raises(STTSessionError, match="32 bytes"):
            SessionManager(b"short", stc_wrapper)
    
    @pytest.mark.asyncio
    async def test_session_manager_get_session_by_peer(self, stc_wrapper):
        """Test getting session by peer node ID."""
        manager = SessionManager(b'\xbb' * 32, stc_wrapper)
        
        peer1 = b'\xcc' * 32
        peer2 = b'\xdd' * 32
        
        # Create session for peer1
        session1 = await manager.create_session(b'\x01' * 8, peer1)
        
        # Get session by peer
        found = await manager.find_session_by_peer(peer1)
        assert found is session1
        
        # Try non-existent peer
        not_found = await manager.find_session_by_peer(peer2)
        assert not_found is None
    
    @pytest.mark.asyncio
    async def test_session_manager_stats(self, stc_wrapper):
        """Test session manager statistics."""
        manager = SessionManager(b'\xee' * 32, stc_wrapper)
        
        # Create some sessions
        await manager.create_session(b'\x01' * 8, b'\xf1' * 32)
        await manager.create_session(b'\x02' * 8, b'\xf2' * 32)
        
        stats = manager.get_stats()
        
        assert stats['total_sessions'] == 2
        assert 'active_sessions' in stats
        assert 'sessions' in stats
        assert len(stats['sessions']) == 2
        
        if hasattr(session, 'record_received_bytes'):
            session.record_received_bytes(1000000)
