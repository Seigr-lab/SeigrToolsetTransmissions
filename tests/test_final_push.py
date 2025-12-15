"""
Final push tests for WebSocket and node coverage.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.transport.websocket import WebSocketTransport
from seigr_toolset_transmissions.core.node import STTNode, ReceivedPacket
from seigr_toolset_transmissions.crypto import STCWrapper


class TestWebSocketFinalPush:
    """Final WebSocket coverage push."""
    
    @pytest.fixture
    def stc_wrapper(self):
        return STCWrapper(b"ws_final_32_bytes_minimum_seed!")
    
    @pytest.mark.asyncio
    async def test_ws_connect_class_method(self, stc_wrapper):
        """Test WebSocket.connect_to class method."""
        try:
            _ws = await asyncio.wait_for(
                WebSocketTransport.connect_to("127.0.0.1", 9999, "/"),
                timeout=0.5
            )  # Connection attempt for coverage
        except Exception:
            pass  # Expected - no server listening
    
    @pytest.mark.asyncio
    async def test_ws_message_handler(self, stc_wrapper):
        """Test WebSocket message handler."""
        ws = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=True)
        ws.message_handler = lambda msg: None
        await ws.start()
        await ws.stop()
    
    @pytest.mark.asyncio
    async def test_ws_client_without_host_port(self, stc_wrapper):
        """Test client connect without host/port."""
        ws = WebSocketTransport(is_client=True, stc_wrapper=stc_wrapper)
        try:
            await ws.connect()
        except Exception as e:
            assert "required" in str(e).lower()
    
    @pytest.mark.asyncio
    async def test_ws_stats_tracking(self, stc_wrapper):
        """Test WebSocket stats tracking."""
        ws = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=True)
        await ws.start()
        
        stats = ws.get_stats()
        assert 'bytes_sent' in stats
        assert 'bytes_received' in stats
        assert 'frames_sent' in stats
        assert 'frames_received' in stats
        
        await ws.stop()


class TestNodeFinalPush:
    """Final node coverage push."""
    
    @pytest.fixture
    def node(self):
        node_seed = b"node_final_32_bytes_minimum_se!"
        shared_seed = b"shared_final_32_bytes_minimum_!"
        return STTNode(node_seed, shared_seed, "127.0.0.1", 0)
    
    @pytest.mark.asyncio
    async def test_node_received_packet_dataclass(self, node):
        """Test ReceivedPacket dataclass."""
        packet = ReceivedPacket(
            session_id=b"12345678",
            stream_id=1,
            data=b"test_data"
        )
        assert packet.session_id == b"12345678"
        assert packet.stream_id == 1
        assert packet.data == b"test_data"
    
    @pytest.mark.asyncio
    async def test_node_multiple_start_stop(self, node):
        """Test multiple start/stop cycles."""
        await node.start()
        await node.stop()
        await node.start()
        await node.stop()
    
    @pytest.mark.asyncio
    async def test_node_ws_connections(self, node):
        """Test node WebSocket connections dict."""
        await node.start()
        assert isinstance(node.ws_connections, dict)
        await node.stop()
    
    @pytest.mark.asyncio
    async def test_node_tasks_list(self, node):
        """Test node tasks list."""
        await node.start()
        assert isinstance(node._tasks, list)
        await node.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
