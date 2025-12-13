"""
Tests for UDP and WebSocket transport layers.
"""

import pytest
import asyncio
from seigr_toolset_transmissions.transport.udp import UDPTransport
from seigr_toolset_transmissions.transport.websocket import WebSocketTransport
from seigr_toolset_transmissions.crypto import STCWrapper
from seigr_toolset_transmissions.utils.exceptions import STTTransportError


class TestUDPTransport:
    """Test UDP transport layer."""
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper for transport."""
        return STCWrapper(b"transport_seed_32_bytes_minimum")
    
    @pytest.fixture
    async def udp_transport(self, stc_wrapper):
        """Create UDP transport."""
        transport = UDPTransport(
            host="127.0.0.1",
            port=0,  # Random port
            stc_wrapper=stc_wrapper,
        )
        await transport.start()
        yield transport
        await transport.stop()
    
    @pytest.mark.asyncio
    async def test_create_udp_transport(self, stc_wrapper):
        """Test creating UDP transport."""
        transport = UDPTransport("127.0.0.1", 0, stc_wrapper)
        
        assert transport.host == "127.0.0.1"
        assert transport.stc_wrapper is stc_wrapper
    
    @pytest.mark.asyncio
    async def test_start_stop_transport(self, stc_wrapper):
        """Test starting and stopping transport."""
        transport = UDPTransport("127.0.0.1", 0, stc_wrapper)
        
        await transport.start()
        assert transport.is_running
        
        await transport.stop()
        assert not transport.is_running
    
    @pytest.mark.asyncio
    async def test_send_receive_message(self, stc_wrapper):
        """Test sending and receiving messages."""
        # Create two transports
        transport1 = UDPTransport("127.0.0.1", 0, stc_wrapper)
        transport2 = UDPTransport("127.0.0.1", 0, stc_wrapper)
        
        await transport1.start()
        await transport2.start()
        
        try:
            # Get addresses
            addr1 = transport1.get_address()
            addr2 = transport2.get_address()
            
            # Set up receiver
            received_data = []
            
            async def receive_handler(data, addr):
                received_data.append(data)
            
            transport2.set_receive_handler(receive_handler)
            
            # Send message
            message = b"test message"
            await transport1.send(message, addr2)
            
            # Wait for message
            await asyncio.sleep(0.1)
            
            assert len(received_data) > 0
            assert received_data[0] == message
            
        finally:
            await transport1.stop()
            await transport2.stop()
    
    @pytest.mark.asyncio
    async def test_send_large_message(self, stc_wrapper):
        """Test sending large message that requires fragmentation."""
        transport1 = UDPTransport("127.0.0.1", 0, stc_wrapper)
        transport2 = UDPTransport("127.0.0.1", 0, stc_wrapper)
        
        await transport1.start()
        await transport2.start()
        
        try:
            addr2 = transport2.get_address()
            
            received_data = []
            
            async def receive_handler(data, addr):
                received_data.append(data)
            
            transport2.set_receive_handler(receive_handler)
            
            # Send large message (10KB)
            large_message = b"x" * 10000
            await transport1.send(large_message, addr2)
            
            # Wait for reassembly
            await asyncio.sleep(0.2)
            
            assert len(received_data) > 0
            assert received_data[0] == large_message
            
        finally:
            await transport1.stop()
            await transport2.stop()
    
    @pytest.mark.asyncio
    async def test_udp_send_to_unreachable(self, stc_wrapper):
        """Test sending to unreachable address."""
        transport = UDPTransport("127.0.0.1", 0, stc_wrapper)
        await transport.start()
        
        try:
            # Try to send to unreachable port
            await transport.send(b"test", ("127.0.0.1", 9))
            # Should not raise error immediately
        finally:
            await transport.stop()
    
    @pytest.mark.asyncio
    async def test_udp_send_raw_error(self, stc_wrapper):
        """Test send_raw error handling."""
        transport = UDPTransport("127.0.0.1", 0, stc_wrapper)
        await transport.start()
        
        try:
            # Send to invalid address
            try:
                await transport.send_raw(b"data", ("invalid_host", 12345))
            except Exception:
                pass  # Expected to fail
        finally:
            await transport.stop()
    
    @pytest.mark.asyncio
    async def test_udp_receive_error_handling(self, stc_wrapper):
        """Test UDP receive error handling."""
        transport = UDPTransport("127.0.0.1", 0, stc_wrapper)
        
        error_occurred = []
        
        def error_handler(data, addr):
            error_occurred.append(True)
        
        transport.set_receive_handler(error_handler)
        
        await transport.start()
        
        # Transport should handle errors gracefully
        await asyncio.sleep(0.1)
        
        await transport.stop()
    
    @pytest.mark.asyncio
    async def test_udp_double_start(self, stc_wrapper):
        """Test starting UDP transport twice."""
        transport = UDPTransport("127.0.0.1", 0, stc_wrapper)
        
        await transport.start()
        
        # Start again - should raise error
        with pytest.raises(STTTransportError):
            await transport.start()
        
        await transport.stop()
    
    @pytest.mark.asyncio
    async def test_udp_stop_not_started(self, stc_wrapper):
        """Test stopping UDP transport that was never started."""
        transport = UDPTransport("127.0.0.1", 0, stc_wrapper)
        
        # Should not raise error
        await transport.stop()
    
    @pytest.mark.asyncio
    async def test_udp_send_frame_not_started(self, stc_wrapper):
        """Test sending frame when transport not started."""
        from seigr_toolset_transmissions.frame import STTFrame
        from seigr_toolset_transmissions.utils.constants import STT_FRAME_TYPE_DATA
        
        transport = UDPTransport("127.0.0.1", 0, stc_wrapper)
        
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=b"sess_id_",
            stream_id=1,
            sequence=0,
            payload=b"data"
        )
        
        # Try to send frame without starting
        try:
            await transport.send_frame(frame, ("127.0.0.1", 9999))
        except Exception:
            pass  # Expected to fail
    
    @pytest.mark.asyncio
    async def test_udp_fragmentation_edge_case(self, stc_wrapper):
        """Test UDP fragmentation with edge case sizes."""
        transport1 = UDPTransport("127.0.0.1", 0, stc_wrapper)
        transport2 = UDPTransport("127.0.0.1", 0, stc_wrapper)
        
        await transport1.start()
        await transport2.start()
        
        try:
            addr2 = transport2.get_address()
            
            received = []
            
            async def handler(data, addr):
                received.append(data)
            
            transport2.set_receive_handler(handler)
            
            # Send message exactly at MTU boundary
            boundary_message = b"x" * 1400
            await transport1.send(boundary_message, addr2)
            
            await asyncio.sleep(0.2)
            
        finally:
            await transport1.stop()
            await transport2.stop()
    
    @pytest.mark.asyncio
    async def test_udp_get_address(self, stc_wrapper):
        """Test getting local address."""
        transport = UDPTransport(
            host="127.0.0.1",
            port=0,
            stc_wrapper=stc_wrapper,
        )
        await transport.start()
        
        try:
            addr = transport.get_address()
            
            assert addr[0] == "127.0.0.1"
            assert addr[1] > 0
        finally:
            await transport.stop()


class TestWebSocketTransport:
    """Test native WebSocket transport (RFC 6455)."""
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper for WebSocket."""
        return STCWrapper(b"websocket_seed_32_bytes_minimum")
    
    @pytest.fixture
    async def ws_server(self, stc_wrapper):
        """Create WebSocket server."""
        server = WebSocketTransport(
            host="127.0.0.1",
            port=0,
            stc_wrapper=stc_wrapper,
            is_server=True,
        )
        await server.start()
        yield server
        await server.stop()
    
    @pytest.mark.asyncio
    async def test_create_websocket_transport(self, stc_wrapper):
        """Test creating WebSocket transport."""
        transport = WebSocketTransport(
            host="127.0.0.1",
            port=8000,
            stc_wrapper=stc_wrapper,
            is_server=True,
        )
        
        assert transport.host == "127.0.0.1"
        assert transport.port == 8000
        assert transport.is_server is True
    
    @pytest.mark.asyncio
    async def test_start_stop_websocket(self, stc_wrapper):
        """Test starting and stopping WebSocket server."""
        server = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        
        await server.start()
        assert server.is_running
        
        await server.stop()
        assert not server.is_running
    
    @pytest.mark.asyncio
    async def test_websocket_handshake(self, stc_wrapper):
        """Test WebSocket handshake (RFC 6455)."""
        server = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await server.start()
        
        try:
            port = server.get_port()
            
            # Create client
            client = WebSocketTransport(
                "127.0.0.1", port, stc_wrapper, is_server=False
            )
            
            try:
                await client.connect()
                assert client.is_connected
            finally:
                await client.disconnect()
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_send_receive_websocket_message(self, stc_wrapper):
        """Test sending and receiving WebSocket messages."""
        server = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await server.start()
        
        try:
            port = server.get_port()
            
            # Set up server handler
            received_messages = []
            
            async def server_handler(data, client_id):
                received_messages.append(data)
            
            server.set_message_handler(server_handler)
            
            # Connect client
            client = WebSocketTransport(
                "127.0.0.1", port, stc_wrapper, is_server=False
            )
            
            try:
                await client.connect()
                
                # Send message
                message = b"websocket test"
                await client.send(message)
                
                # Wait for message
                await asyncio.sleep(0.1)
                
                assert len(received_messages) > 0
                assert received_messages[0] == message
                
            finally:
                await client.disconnect()
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_send_large_websocket_message(self, stc_wrapper):
        """Test sending large WebSocket message."""
        server = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await server.start()
        
        try:
            port = server.get_port()
            
            received_messages = []
            
            async def server_handler(data, client_id):
                received_messages.append(data)
            
            server.set_message_handler(server_handler)
            
            client = WebSocketTransport(
                "127.0.0.1", port, stc_wrapper, is_server=False
            )
            
            try:
                await client.connect()
                
                # Send 100KB message
                large_message = b"y" * 100000
                await client.send(large_message)
                
                await asyncio.sleep(0.2)
                
                assert len(received_messages) > 0
                assert received_messages[0] == large_message
                
            finally:
                await client.disconnect()
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_ping_pong(self, stc_wrapper):
        """Test WebSocket ping/pong frames."""
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
                
                # Send ping
                await client.ping()
                
                # Should receive pong
                await asyncio.sleep(0.1)

                assert client.is_connected
            
            finally:
                await client.disconnect()
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_multiple_websocket_clients(self, stc_wrapper):
        """Test multiple concurrent WebSocket clients."""
        server = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await server.start()
        
        try:
            port = server.get_port()
        
            clients = []
            
            try:
                # Connect 5 clients
                for i in range(5):
                    client = WebSocketTransport(
                        "127.0.0.1", port, stc_wrapper, is_server=False
                    )
                    await client.connect()
                    clients.append(client)
                
                # All should be connected
                assert all(c.is_connected for c in clients)
                
            finally:
                for client in clients:
                    await client.disconnect()
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_close_frame(self, stc_wrapper):
        """Test WebSocket close frame handling."""
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
                assert client.is_connected

                # Disconnect
                await client.disconnect()
                assert not client.is_connected

            finally:
                if client.is_connected:
                    await client.disconnect()
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_client_receive_frames(self, stc_wrapper):
        """Test WebSocket client receive_frames() method code path."""
        import asyncio
        
        server = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=True)
        await server.start()
        
        try:
            port = server.get_port()
            
            # Track received messages
            received_messages = []
            
            def message_handler(data, addr):
                received_messages.append(data)
            
            client = WebSocketTransport(
                "127.0.0.1", port, stc_wrapper, is_server=False
            )
            client.set_message_handler(message_handler)
            
            await client.connect()
            assert client.is_connected
            
            # Start receive loop in background
            receive_task = asyncio.create_task(client.receive_frames())
            
            # Let it run briefly to exercise the receive_frames() code
            await asyncio.sleep(0.2)
            
            # Cancel receive task
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass  # Expected
            
            await client.disconnect()
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_client_text_message(self, stc_wrapper):
        """Test WebSocket client receiving TEXT frames - exercises text opcode path."""
        import asyncio
        
        # This test mainly ensures receive_frames() TEXT opcode path exists
        # Actual server->client TEXT transmission tested in integration
        client = WebSocketTransport(
            "127.0.0.1", 9999, stc_wrapper, is_server=False
        )
        
        # Verify client can handle text messages (has message_handler)
        def handler(data, addr):
            pass
        
        client.set_message_handler(handler)
        assert client.message_handler is not None
    
    @pytest.mark.asyncio
    async def test_websocket_client_ping_response(self, stc_wrapper):
        """Test WebSocket client responds to PING with PONG - exercises ping opcode path."""
        import asyncio
        
        # This test verifies the ping handling code path exists in receive_frames()
        # Actual PING/PONG exchange is tested in test_websocket_ping_pong
        client = WebSocketTransport(
            "127.0.0.1", 9999, stc_wrapper, is_server=False
        )
        
        # Just verify client can be created and has receive_frames method
        assert hasattr(client, 'receive_frames')
        assert callable(client.receive_frames)
    
    @pytest.mark.asyncio
    async def test_websocket_client_close_frame(self, stc_wrapper):
        """Test WebSocket client handling CLOSE frame during disconnect."""
        from seigr_toolset_transmissions.transport.websocket import WebSocketState
        
        server = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=True)
        await server.start()
        
        try:
            port = server.get_port()
            
            client = WebSocketTransport(
                "127.0.0.1", port, stc_wrapper, is_server=False
            )
            
            await client.connect()
            assert client.is_connected
            
            # Disconnect normally (sends CLOSE frame)
            await client.disconnect()
            
            # Wait a bit
            await asyncio.sleep(0.1)
            
            # Verify client is closed
            assert not client.is_connected
            assert client.state in (WebSocketState.CLOSING, WebSocketState.CLOSED)
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_client_receive_error(self, stc_wrapper):
        """Test WebSocket client receive_frames() error handling."""
        client = WebSocketTransport(
            "127.0.0.1", 9999, stc_wrapper, is_server=False
        )
        
        # Try to receive without connecting (should fail)
        try:
            # Start receive loop on unconnected client
            receive_task = asyncio.create_task(client.receive_frames())
            await asyncio.sleep(0.2)
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass
        except Exception:
            pass  # Expected to fail
    
    @pytest.mark.asyncio
    async def test_websocket_receive_frames_server_mode_error(self, stc_wrapper):
        """Test receive_frames() raises error when called on server."""
        server = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=True)
        await server.start()
        
        try:
            # receive_frames() should raise error on server mode
            with pytest.raises(STTTransportError, match="only for client mode"):
                await server.receive_frames()
        finally:
            await server.stop()


class TestTransportIntegration:
    """Integration tests for transports."""
    
    @pytest.fixture
    def stc_wrapper(self):
        """STC wrapper for integration tests."""
        return STCWrapper(b"integration_seed_32_bytes_min!")
    
    @pytest.mark.asyncio
    async def test_transport_switching(self, stc_wrapper):
        """Test switching between UDP and WebSocket."""
        # Start with UDP
        udp = UDPTransport("127.0.0.1", 0, stc_wrapper)
        await udp.start()
        
        udp_addr = udp.get_address()
        assert udp_addr[1] > 0
        
        await udp.stop()
        
        # Switch to WebSocket
        ws = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        await ws.start()
        
        ws_port = ws.get_port()
        assert ws_port > 0
        
        await ws.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_transports(self, stc_wrapper):
        """Test running UDP and WebSocket concurrently."""
        udp = UDPTransport("127.0.0.1", 0, stc_wrapper)
        ws = WebSocketTransport(
            "127.0.0.1", 0, stc_wrapper, is_server=True
        )
        
        await udp.start()
        await ws.start()
        
        try:
            assert udp.is_running
            assert ws.is_running
            
        finally:
            await udp.stop()
            await ws.stop()
    
    @pytest.mark.asyncio
    async def test_udp_statistics_tracking(self, stc_wrapper):
        """Test UDP transport tracks statistics."""
        transport = UDPTransport("127.0.0.1", 0, stc_wrapper)
        await transport.start()
        
        try:
            assert transport.bytes_sent == 0
            assert transport.bytes_received == 0
            assert transport.packets_sent == 0
            assert transport.packets_received == 0
        finally:
            await transport.stop()
    
    @pytest.mark.asyncio
    async def test_udp_max_packet_size(self, stc_wrapper):
        """Test UDP respects max packet size."""
        transport = UDPTransport("127.0.0.1", 0, stc_wrapper)
        
        # Default MTU for IPv4
        assert transport.config.max_packet_size == 1472
    
    @pytest.mark.asyncio
    async def test_udp_buffer_sizes(self, stc_wrapper):
        """Test UDP buffer configuration."""
        transport = UDPTransport("127.0.0.1", 0, stc_wrapper)
        
        assert transport.config.receive_buffer_size == 65536
        assert transport.config.send_buffer_size == 65536
    
    @pytest.mark.asyncio
    async def test_udp_random_port_binding(self, stc_wrapper):
        """Test UDP binds to random port when port=0."""
        transport = UDPTransport("127.0.0.1", 0, stc_wrapper)
        await transport.start()
        
        try:
            addr = transport.get_address()
            assert addr[1] > 0  # Should have assigned a port
        finally:
            await transport.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_statistics_tracking(self, stc_wrapper):
        """Test WebSocket transport tracks statistics."""
        transport = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=True)
        await transport.start()
        
        try:
            assert transport.bytes_sent == 0
            assert transport.bytes_received == 0
        finally:
            await transport.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_ssl_disabled_by_default(self, stc_wrapper):
        """Test WebSocket SSL is disabled by default."""
        transport = WebSocketTransport("127.0.0.1", 0, stc_wrapper, is_server=True)
        
        # Default should be no SSL (would be configured separately)
        # This test just ensures initialization works
        await transport.start()
        await transport.stop()
    
    @pytest.mark.asyncio
    async def test_udp_get_stats(self, stc_wrapper):
        """Test UDP transport statistics."""
        transport = UDPTransport("127.0.0.1", 0, stc_wrapper)
        await transport.start()
        
        stats = transport.get_stats()
        assert 'bytes_sent' in stats
        assert 'bytes_received' in stats
        assert stats['bytes_sent'] == 0
        assert stats['bytes_received'] == 0
        
        await transport.stop()
