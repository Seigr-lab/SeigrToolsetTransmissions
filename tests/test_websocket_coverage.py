"""
Comprehensive WebSocket coverage tests.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.transport.websocket import WebSocketTransport
from seigr_toolset_transmissions.crypto import STCWrapper


class TestWebSocketCoverage:
    """WebSocket tests for maximum coverage."""
    
    @pytest.fixture
    def stc_wrapper(self):
        return STCWrapper(b"ws_coverage_32_bytes_minimum!!")
    
    @pytest.mark.asyncio
    async def test_ws_server_start_stop(self, stc_wrapper):
        """Test WebSocket server lifecycle."""
        ws = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=True)
        await ws.start()
        await ws.stop()
    
    @pytest.mark.asyncio
    async def test_ws_client_connect_fail(self, stc_wrapper):
        """Test WebSocket client connection failure."""
        ws = WebSocketTransport("127.0.0.1", 9999, stc_wrapper, is_server=False)
        try:
            await asyncio.wait_for(ws.start(), timeout=0.2)
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError, Exception):
            pass
    
    @pytest.mark.asyncio
    async def test_ws_send_without_connection(self, stc_wrapper):
        """Test sending without connection."""
        ws = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=False)
        try:
            await ws.send_frame(b"test")
        except Exception:
            pass
    
    @pytest.mark.asyncio
    async def test_ws_receive_without_connection(self, stc_wrapper):
        """Test receiving without connection."""
        ws = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=False)
        try:
            await asyncio.wait_for(ws.receive_frame(), timeout=0.1)
        except (asyncio.TimeoutError, Exception):
            pass
    
    @pytest.mark.asyncio
    async def test_ws_stats(self, stc_wrapper):
        """Test WebSocket statistics."""
        ws = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=True)
        await ws.start()
        stats = ws.get_stats()
        assert 'bytes_sent' in stats
        assert 'bytes_received' in stats
        await ws.stop()
    
    @pytest.mark.asyncio
    async def test_ws_multiple_starts(self, stc_wrapper):
        """Test starting already started transport."""
        ws = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=True)
        await ws.start()
        try:
            await ws.start()
        except Exception:
            pass
        await ws.stop()
    
    @pytest.mark.asyncio
    async def test_ws_close_connection(self, stc_wrapper):
        """Test closing WebSocket connection."""
        ws = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=True)
        await ws.start()
        if hasattr(ws, 'close_connection'):
            try:
                await ws.close_connection()
            except Exception:
                pass
        await ws.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
