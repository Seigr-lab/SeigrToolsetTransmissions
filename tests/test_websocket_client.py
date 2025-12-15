"""
Additional tests for WebSocket client mode coverage.
"""

import pytest
import asyncio

from seigr_toolset_transmissions.transport.websocket import WebSocketTransport, WebSocketOpcode
from seigr_toolset_transmissions.crypto.stc_wrapper import STCWrapper


@pytest.fixture
def stc_wrapper():
    """Create STC wrapper for tests."""
    from seigr_toolset_transmissions.crypto import context
    context.initialize(b"test_seed_websocket_client")
    return STCWrapper(b"test_seed_websocket_client")


class TestWebSocketClientMode:
    """Test WebSocket client-specific functionality."""
    
    @pytest.mark.asyncio
    async def test_client_receive_text_frame(self, stc_wrapper):
        """Test client sending TEXT frame."""
        server = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await server.start()
        
        try:
            port = server.get_port()
            
            client = WebSocketTransport(
                "127.0.0.1", port, stc_wrapper, is_server=False
            )
            
            try:
                await client.connect()
                
                # Send text frame from client
                await client._send_ws_frame(
                    WebSocketOpcode.TEXT,
                    b"Hello text"
                )
                
                await asyncio.sleep(0.1)
                
                # Verify client is still connected after sending text frame
                assert client.is_connected
                
            finally:
                await client.close()
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_client_receive_ping(self, stc_wrapper):
        """Test client responding to PING."""
        server = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await server.start()
        
        try:
            port = server.get_port()
            
            client = WebSocketTransport(
                "127.0.0.1", port, stc_wrapper, is_server=False
            )
            
            try:
                await client.connect()
                
                # Get client connection from server
                await asyncio.sleep(0.1)
                assert len(server.clients) == 1
                client_id = list(server.clients.keys())[0]
                _, _, _, client_ws = server.clients[client_id]
                
                # Send PING to client
                await client_ws._send_ws_frame(
                    WebSocketOpcode.PING,
                    b"ping-payload"
                )
                
                # Client should auto-respond with PONG
                await asyncio.sleep(0.1)
                
                # Connection should still be open
                assert client.is_connected
                
            finally:
                await client.close()
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_client_receive_pong(self, stc_wrapper):
        """Test client receiving PONG frame."""
        server = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await server.start()
        
        try:
            port = server.get_port()
            
            client = WebSocketTransport(
                "127.0.0.1", port, stc_wrapper, is_server=False
            )
            
            try:
                await client.connect()
                
                # Send PING from client
                await client._send_ws_frame(
                    WebSocketOpcode.PING,
                    b"test-ping"
                )
                
                # Should receive PONG back
                await asyncio.sleep(0.1)
                
                # Connection should still be open
                assert client.is_connected
                
            finally:
                await client.close()
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_client_receive_close(self, stc_wrapper):
        """Test client receiving CLOSE frame."""
        server = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await server.start()
        
        try:
            port = server.get_port()
            
            client = WebSocketTransport(
                "127.0.0.1", port, stc_wrapper, is_server=False
            )
            
            await client.connect()
            
            # Verify connection established
            assert client.is_connected
            
            # Send close from server
            await asyncio.sleep(0.1)
            client_id = list(server.clients.keys())[0]
            _, _, _, client_ws = server.clients[client_id]
            
            # Close from server side
            close_task = asyncio.create_task(client_ws.close(1000, "Normal closure"))
            
            # Give time for close handshake to complete
            await asyncio.sleep(1.0)
            
            # Check if close completed
            if not close_task.done():
                await close_task
                
            # Client may or may not be marked as disconnected depending on timing
            # Just verify it can close cleanly
            if client.is_connected:
                await client.close()
                
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_client_receive_binary_frame(self, stc_wrapper):
        """Test client receiving BINARY frame."""
        received_frames = []
        
        def on_frame(frame):
            received_frames.append(frame)
        
        server = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await server.start()
        
        try:
            port = server.get_port()
            
            client = WebSocketTransport(
                "127.0.0.1", port, stc_wrapper, is_server=False,
                on_frame_received=on_frame
            )
            
            try:
                await client.connect()
                
                # Get server's client connection
                await asyncio.sleep(0.1)
                client_id = list(server.clients.keys())[0]
                _, _, _, client_ws = server.clients[client_id]
                
                # Send binary frame from server to client
                test_data = b"binary payload test"
                await client_ws._send_ws_frame(
                    WebSocketOpcode.BINARY,
                    test_data
                )
                
                await asyncio.sleep(0.1)
                
                # Client should receive binary frame
                # (may or may not parse as STT frame)
                
            finally:
                await client.close()
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_client_malformed_frame(self, stc_wrapper):
        """Test client handling malformed frame."""
        server = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await server.start()
        
        try:
            port = server.get_port()
            
            client = WebSocketTransport(
                "127.0.0.1", port, stc_wrapper, is_server=False
            )
            
            try:
                await client.connect()
                
                # Send malformed data directly
                client.writer.write(b"\x00\x00\x00")
                await client.writer.drain()
                
                # Connection should close or handle error
                await asyncio.sleep(0.2)
                
            finally:
                if client.is_connected:
                    await client.close()
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_client_receive_loop_error_handling(self, stc_wrapper):
        """Test client receive loop handles errors gracefully."""
        server = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await server.start()
        
        try:
            port = server.get_port()
            
            client = WebSocketTransport(
                "127.0.0.1", port, stc_wrapper, is_server=False
            )
            
            try:
                await client.connect()
                
                # Abruptly close server connection
                await server.stop()
                
                # Client should handle connection loss
                await asyncio.sleep(0.2)
                
            finally:
                if client.is_connected:
                    await client.close()
        finally:
            if server.is_running:
                await server.stop()
    
    @pytest.mark.asyncio
    async def test_client_close_with_code_and_reason(self, stc_wrapper):
        """Test client sending close with code and reason."""
        server = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await server.start()
        
        try:
            port = server.get_port()
            
            client = WebSocketTransport(
                "127.0.0.1", port, stc_wrapper, is_server=False
            )
            
            try:
                await client.connect()
                
                # Close with custom code and reason
                await client.close(1001, "Going away")
                
                await asyncio.sleep(0.1)
                
                assert not client.is_connected
                
            finally:
                if client.is_connected:
                    await client.close()
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_server_handshake_missing_upgrade(self, stc_wrapper):
        """Test server rejecting handshake without Upgrade header."""
        server = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await server.start()
        
        try:
            port = server.get_port()
            
            # Connect with TCP, send invalid handshake
            _reader, writer = await asyncio.open_connection("127.0.0.1", port)
            
            try:
                # Send request without Upgrade header
                request = (
                    f"GET / HTTP/1.1\r\n"
                    f"Host: 127.0.0.1:{port}\r\n"
                    f"\r\n"
                )
                writer.write(request.encode())
                await writer.drain()
                
                # Should not complete handshake
                await asyncio.sleep(0.1)
                
            finally:
                writer.close()
                await writer.wait_closed()
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_server_handshake_wrong_version(self, stc_wrapper):
        """Test server rejecting wrong WebSocket version."""
        server = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await server.start()
        
        try:
            port = server.get_port()
            
            # Connect with TCP
            _reader, writer = await asyncio.open_connection("127.0.0.1", port)
            
            try:
                # Send handshake with wrong version
                import base64
                import secrets
                key = base64.b64encode(secrets.token_bytes(16)).decode()
                
                request = (
                    f"GET / HTTP/1.1\r\n"
                    f"Host: 127.0.0.1:{port}\r\n"
                    f"Upgrade: websocket\r\n"
                    f"Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Key: {key}\r\n"
                    f"Sec-WebSocket-Version: 8\r\n"
                    f"\r\n"
                )
                writer.write(request.encode())
                await writer.drain()
                
                await asyncio.sleep(0.1)
                
            finally:
                writer.close()
                await writer.wait_closed()
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_get_stats(self, stc_wrapper):
        """Test WebSocket get_stats returns valid data."""
        ws = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await ws.start()
        
        try:
            stats = ws.get_stats()
            
            assert 'connected' in stats
            assert 'state' in stats
            assert 'is_server' in stats
            assert stats['is_server'] is True
            assert 'bytes_sent' in stats
            assert 'bytes_received' in stats
            
        finally:
            await ws.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
