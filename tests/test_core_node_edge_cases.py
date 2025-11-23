"""
Edge case tests for core/node.py to achieve 100% coverage.
Tests broadcast/multicast functionality and exception paths.
"""

import pytest
import asyncio
import os
from pathlib import Path
from seigr_toolset_transmissions.core.node import STTNode, ReceivedPacket
from seigr_toolset_transmissions.frame.frame import STTFrame
from seigr_toolset_transmissions.utils.constants import (
    STT_SESSION_STATE_ACTIVE,
    STT_FRAME_TYPE_DATA
)


@pytest.fixture
def node_seed():
    """Generate node seed."""
    return os.urandom(32)


@pytest.fixture
def shared_seed():
    """Generate shared seed."""
    return os.urandom(32)


@pytest.fixture
def temp_chamber_path(tmp_path):
    """Create temporary chamber directory."""
    return tmp_path / "test_chamber"


class TestBroadcastMulticast:
    """Test broadcast and multicast functionality."""
    
    @pytest.mark.asyncio
    async def test_broadcast_no_sessions(self, node_seed, shared_seed, temp_chamber_path):
        """Test broadcast with no active sessions (lines 382-383)."""
        node = STTNode(node_seed, shared_seed, "127.0.0.1", 0, temp_chamber_path)
        await node.start()
        
        try:
            # Broadcast should log warning and return
            await node.send_to_all(b'test_data', stream_id=0)
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_broadcast_with_sessions(self, node_seed, shared_seed, temp_chamber_path):
        """Test broadcast to active sessions (lines 385-392)."""
        node = STTNode(node_seed, shared_seed, "127.0.0.1", 0, temp_chamber_path)
        await node.start()
        
        try:
            # Create some sessions
            session1 = await node.session_manager.create_session(
                session_id=b'bcast001',
                peer_node_id=b'peer0001',
                capabilities=0
            )
            session1.state = STT_SESSION_STATE_ACTIVE
            session1.peer_addr = ('127.0.0.1', 9001)
            
            session2 = await node.session_manager.create_session(
                session_id=b'bcast002',
                peer_node_id=b'peer0002',
                capabilities=0
            )
            session2.state = STT_SESSION_STATE_ACTIVE
            session2.peer_addr = ('127.0.0.1', 9002)
            
            # Broadcast to all
            await node.send_to_all(b'broadcast_message', stream_id=0)
            
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_send_to_sessions_empty_list(self, node_seed, shared_seed, temp_chamber_path):
        """Test multicast with empty session list (lines 405-406)."""
        node = STTNode(node_seed, shared_seed, "127.0.0.1", 0, temp_chamber_path)
        await node.start()
        
        try:
            # Empty list should log warning and return
            await node.send_to_sessions([], b'test_data', stream_id=0)
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_send_to_sessions_nonexistent(self, node_seed, shared_seed, temp_chamber_path):
        """Test multicast with nonexistent session (line 416)."""
        node = STTNode(node_seed, shared_seed, "127.0.0.1", 0, temp_chamber_path)
        await node.start()
        
        try:
            # Should log warning for session not found
            await node.send_to_sessions([b'nosess99'], b'test_data', stream_id=0)
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_send_to_sessions_valid(self, node_seed, shared_seed, temp_chamber_path):
        """Test multicast to valid sessions (lines 408-417)."""
        node = STTNode(node_seed, shared_seed, "127.0.0.1", 0, temp_chamber_path)
        await node.start()
        
        try:
            # Create sessions
            session1 = await node.session_manager.create_session(
                session_id=b'mcast001',
                peer_node_id=b'peer1001',
                capabilities=0
            )
            session1.state = STT_SESSION_STATE_ACTIVE
            session1.peer_addr = ('127.0.0.1', 9101)
            
            session2 = await node.session_manager.create_session(
                session_id=b'mcast002',
                peer_node_id=b'peer1002',
                capabilities=0
            )
            session2.state = STT_SESSION_STATE_ACTIVE
            session2.peer_addr = ('127.0.0.1', 9102)
            
            # Multicast to specific sessions
            await node.send_to_sessions(
                [session1.session_id, session2.session_id],
                b'multicast_message',
                stream_id=0
            )
            
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_send_to_session_with_encryption(self, node_seed, shared_seed, temp_chamber_path):
        """Test _send_to_session with session key (lines 429-435)."""
        node = STTNode(node_seed, shared_seed, "127.0.0.1", 0, temp_chamber_path)
        await node.start()
        
        try:
            # Create session with key
            session = await node.session_manager.create_session(
                session_id=b'encrsess',
                peer_node_id=b'peerencr',
                capabilities=0
            )
            session.state = STT_SESSION_STATE_ACTIVE
            session.peer_addr = ('127.0.0.1', 9201)
            session.session_key = b'0' * 32  # Set encryption key
            
            # Send should encrypt
            await node._send_to_session(session, b'encrypted_data', stream_id=0)
            
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_send_to_session_no_transport_address(self, node_seed, shared_seed, temp_chamber_path):
        """Test _send_to_session without peer_addr (lines 441-442)."""
        node = STTNode(node_seed, shared_seed, "127.0.0.1", 0, temp_chamber_path)
        await node.start()
        
        try:
            # Create session WITHOUT peer_addr
            session = await node.session_manager.create_session(
                session_id=b'noaddr01',
                peer_node_id=b'peernoad',
                capabilities=0
            )
            session.state = STT_SESSION_STATE_ACTIVE
            # Deliberately don't set peer_addr
            
            # Should log warning
            await node._send_to_session(session, b'test_data', stream_id=0)
            
        finally:
            await node.stop()
    
    @pytest.mark.asyncio
    async def test_send_to_session_exception(self, node_seed, shared_seed, temp_chamber_path):
        """Test _send_to_session exception handling (line 445)."""
        node = STTNode(node_seed, shared_seed, "127.0.0.1", 0, temp_chamber_path)
        await node.start()
        
        try:
            # Create session with invalid data that causes exception
            session = await node.session_manager.create_session(
                session_id=b'except01',
                peer_node_id=b'peerexcp',
                capabilities=0
            )
            session.state = STT_SESSION_STATE_ACTIVE
            session.peer_addr = ('127.0.0.1', 9301)
            
            # This might cause exception in frame creation
            # Exception should be caught and logged
            await node._send_to_session(session, b'test', stream_id=0)
            
        finally:
            await node.stop()


class TestReceivePath:
    """Test receive functionality."""
    
    @pytest.mark.asyncio
    async def test_receive_timeout_loop(self, node_seed, shared_seed, temp_chamber_path):
        """Test receive() timeout handling (lines 362-363)."""
        node = STTNode(node_seed, shared_seed, "127.0.0.1", 0, temp_chamber_path)
        await node.start()
        
        try:
            # Receive should handle timeout and continue
            receive_task = asyncio.create_task(self._consume_receive(node))
            
            await asyncio.sleep(0.2)  # Let it timeout a few times
            
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass
        finally:
            await node.stop()
    
    async def _consume_receive(self, node):
        """Helper to consume receive iterator."""
        count = 0
        async for packet in node.receive():
            count += 1
            if count > 5:
                break
    
    @pytest.mark.asyncio
    async def test_receive_yields_packet(self, node_seed, shared_seed, temp_chamber_path):
        """Test receive() yields packets (lines 367-368)."""
        node = STTNode(node_seed, shared_seed, "127.0.0.1", 0, temp_chamber_path)
        await node.start()
        
        try:
            # Create session
            session = await node.session_manager.create_session(
                session_id=b'recvtest',
                peer_node_id=b'peerrecv',
                capabilities=0
            )
            session.state = STT_SESSION_STATE_ACTIVE
            
            # Add packet
            packet = ReceivedPacket(
                session_id=session.session_id,
                stream_id=1,
                data=b'receive_test_data'
            )
            await node._recv_queue.put(packet)
            
            # Receive should yield it
            async for received in node.receive():
                assert received.data == b'receive_test_data'
                break
        finally:
            await node.stop()


class TestDataFrameHandling:
    """Test data frame handling."""
    
    @pytest.mark.asyncio
    async def test_data_frame_decryption(self, node_seed, shared_seed, temp_chamber_path):
        """Test data frame decryption (line 342)."""
        node = STTNode(node_seed, shared_seed, "127.0.0.1", 0, temp_chamber_path)
        await node.start()
        
        try:
            # Create session
            session = await node.session_manager.create_session(
                session_id=b'decrsess',
                peer_node_id=b'peerdecr',
                capabilities=0
            )
            session.state = STT_SESSION_STATE_ACTIVE
            session.session_key = b'0' * 32
            
            # Create encrypted frame
            frame = STTFrame(
                frame_type=STT_FRAME_TYPE_DATA,
                session_id=session.session_id,
                sequence=0,
                stream_id=1,
                payload=b'plain_payload'
            )
            
            # Encrypt it
            frame.encrypt_payload(node.stc)
            assert frame._is_encrypted
            
            # Handle should decrypt
            await node._handle_data_frame(frame, ('127.0.0.1', 8888))
            
            # Check packet was queued with decrypted data
            packet = await asyncio.wait_for(node._recv_queue.get(), timeout=1.0)
            assert packet.data == b'plain_payload'
            
        finally:
            await node.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
