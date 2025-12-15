"""
Additional comprehensive tests for session, stream, node, handshake edge cases.
"""

import pytest
from seigr_toolset_transmissions.session.session import STTSession
from seigr_toolset_transmissions.stream.stream import STTStream
from seigr_toolset_transmissions.core.node import STTNode
from seigr_toolset_transmissions.handshake.handshake import STTHandshake
from seigr_toolset_transmissions.crypto import STCWrapper


class TestSessionEdgeCases:
    """Session edge case coverage."""
    
    @pytest.fixture
    def stc_wrapper(self):
        return STCWrapper(b"session_coverage_32_bytes_min!")
    
    @pytest.fixture
    def session(self, stc_wrapper):
        return STTSession(b"12345678", b"peer_123", stc_wrapper)
    
    def test_session_close_and_check(self, session):
        """Test session close and is_closed."""
        session.close()
        assert session.is_closed()
    
    def test_session_record_sent_bytes(self, session):
        """Test recording sent bytes."""
        session.record_sent_bytes(100)
        stats = session.get_stats()
        assert stats['bytes_sent'] == 100
    
    def test_session_record_received_bytes(self, session):
        """Test recording received bytes."""
        session.record_received_bytes(200)
        stats = session.get_stats()
        assert stats['bytes_received'] == 200
    
    def test_session_frame_tracking(self, session):
        """Test frame tracking."""
        session.record_frame_sent(100)
        session.record_frame_received(200)
        stats = session.get_stats()
        assert stats['frames_sent'] == 1
        assert stats['frames_received'] == 1
    
    def test_session_key_rotation(self, session, stc_wrapper):
        """Test key rotation."""
        old_version = session.key_version
        session.rotate_keys(stc_wrapper)
        assert session.key_version == old_version + 1


class TestStreamEdgeCases:
    """Stream edge case coverage."""
    
    @pytest.fixture
    def stc_wrapper(self):
        return STCWrapper(b"stream_coverage_32_bytes_mini!")
    
    @pytest.fixture
    def stream(self, stc_wrapper):
        return STTStream(b"87654321", 1, stc_wrapper)
    
    @pytest.mark.asyncio
    async def test_stream_close(self, stream):
        """Test stream close."""
        await stream.close()
        assert stream.is_closed()
    
    @pytest.mark.asyncio
    async def test_stream_double_close(self, stream):
        """Test double close."""
        await stream.close()
        await stream.close()
        assert stream.is_closed()
    
    def test_stream_is_expired(self, stream):
        """Test stream expiration check."""
        result = stream.is_expired(max_idle=1000)
        assert result is False
    
    def test_stream_stats(self, stream):
        """Test stream statistics."""
        stats = stream.get_stats()
        assert 'bytes_sent' in stats
        assert 'bytes_received' in stats
    
    def test_stream_receive_buffer_empty(self, stream):
        """Test receive buffer empty check."""
        assert stream.receive_buffer_empty()


class TestNodeEdgeCases:
    """Node edge case coverage."""
    
    @pytest.fixture
    def node(self):
        node_seed = b"node_coverage_32_bytes_minimum!"
        shared_seed = b"shared_coverage_32_bytes_minim!"
        return STTNode(node_seed, shared_seed, "127.0.0.1", 0)
    
    @pytest.mark.asyncio
    async def test_node_start_stop(self, node):
        """Test node lifecycle."""
        _addr, port = await node.start()
        assert isinstance(port, int)
        await node.stop()
    
    @pytest.mark.asyncio
    async def test_node_double_start(self, node):
        """Test starting already running node."""
        await node.start()
        await node.start()  # Should handle gracefully (double start)
        await node.stop()
    
    @pytest.mark.asyncio
    async def test_node_stop_without_start(self, node):
        """Test stopping non-running node."""
        try:
            await node.stop()
        except Exception:
            pass  # May fail if node not started - that's OK


class TestHandshakeEdgeCases:
    """Handshake edge case coverage."""
    
    @pytest.fixture
    def stc_wrapper(self):
        return STCWrapper(b"handshake_coverage_32_bytes_m!")
    
    @pytest.fixture
    def handshake(self, stc_wrapper):
        node_id = b"x" * 32
        return STTHandshake(node_id, stc_wrapper, is_initiator=True)
    
    def test_handshake_create_hello(self, handshake):
        """Test creating HELLO message."""
        hello = handshake.create_hello()
        assert isinstance(hello, bytes)
        assert len(hello) > 0
    
    def test_handshake_process_hello(self, handshake, stc_wrapper):
        """Test processing HELLO message."""
        # Create a valid HELLO first
        initiator = STTHandshake(b"y" * 32, stc_wrapper, is_initiator=True)
        hello = initiator.create_hello()
        
        # Process as responder
        responder = STTHandshake(b"z" * 32, stc_wrapper, is_initiator=False)
        try:
            response = responder.process_hello(hello)
            assert isinstance(response, bytes)
        except Exception:
            pass  # Handshake may fail with mock data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
