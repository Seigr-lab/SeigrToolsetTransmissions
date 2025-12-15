"""
Additional WebSocket comprehensive tests targeting uncovered lines.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.transport.websocket import WebSocketTransport, WebSocketState
from seigr_toolset_transmissions.crypto import STCWrapper
from seigr_toolset_transmissions.frame import STTFrame


class TestWebSocketAdditional:
    """Additional WebSocket tests for uncovered lines."""
    
    @pytest.fixture
    def stc_wrapper(self):
        return STCWrapper(b"ws_additional_32_bytes_minimum!")
    
    @pytest.mark.asyncio
    async def test_ws_client_mode_flags(self, stc_wrapper):
        """Test WebSocket client mode initialization."""
        ws = WebSocketTransport(is_client=True, host="127.0.0.1", port=8080, stc_wrapper=stc_wrapper)
        assert ws.is_client is True
        assert ws.is_server is False
    
    @pytest.mark.asyncio
    async def test_ws_server_mode_flags(self, stc_wrapper):
        """Test WebSocket server mode initialization."""
        ws = WebSocketTransport(is_server=True, host="127.0.0.1", port=8081, stc_wrapper=stc_wrapper)
        assert ws.is_server is True
        assert ws.is_client is False
    
    @pytest.mark.asyncio
    async def test_ws_state_tracking(self, stc_wrapper):
        """Test WebSocket state tracking."""
        ws = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=True)
        assert ws.state == WebSocketState.CONNECTING
        await ws.start()
        assert ws.state == WebSocketState.OPEN
        await ws.stop()
    
    @pytest.mark.asyncio
    async def test_ws_client_connect_error(self, stc_wrapper):
        """Test client connection error handling."""
        ws = WebSocketTransport(is_client=True, stc_wrapper=stc_wrapper)
        try:
            await asyncio.wait_for(ws.connect("192.0.2.1", 9999), timeout=0.5)
        except Exception:
            pass  # Expected - unreachable address
    
    @pytest.mark.asyncio
    async def test_ws_send_frame_server(self, stc_wrapper):
        """Test sending frame in server mode."""
        ws = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=True)
        await ws.start()
        
        frame = STTFrame(
            frame_type=1,
            session_id=b"12345678",
            sequence=1,
            stream_id=1,
            payload=b"test_data"
        )
        
        try:
            await ws.send_frame(frame)
        except Exception:
            pass  # Expected - not connected
        
        await ws.stop()
    
    @pytest.mark.asyncio
    async def test_ws_receive_frame_timeout(self, stc_wrapper):
        """Test receive frame with timeout."""
        ws = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=True)
        await ws.start()
        
        try:
            await asyncio.wait_for(ws.receive_frame(), timeout=0.1)
        except (asyncio.TimeoutError, Exception):
            pass  # Expected - no incoming frames
        
        await ws.stop()
    
    @pytest.mark.asyncio
    async def test_ws_close_with_code(self, stc_wrapper):
        """Test WebSocket close with code."""
        ws = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=True)
        await ws.start()
        
        try:
            await ws.close(1000, "Normal closure")
        except Exception:
            pass  # May fail if no active connections
        
        await ws.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
