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
    async def test_get_local_address(self, udp_transport):
        """Test getting local address."""
        addr = udp_transport.get_address()
        
        assert addr[0] == "127.0.0.1"
        assert addr[1] > 0


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
    async def test_websocket_handshake(self, stc_wrapper, ws_server):
        """Test WebSocket handshake (RFC 6455)."""
        port = ws_server.get_port()
        
        # Create client
        client = WebSocketTransport(
            "127.0.0.1", port, stc_wrapper, is_server=False
        )
        
        try:
            await client.connect()
            assert client.is_connected
        finally:
            await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_send_receive_websocket_message(self, stc_wrapper, ws_server):
        """Test sending and receiving WebSocket messages."""
        port = ws_server.get_port()
        
        # Set up server handler
        received_messages = []
        
        async def server_handler(data, client_id):
            received_messages.append(data)
        
        ws_server.set_message_handler(server_handler)
        
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
    
    @pytest.mark.asyncio
    async def test_send_large_websocket_message(self, stc_wrapper, ws_server):
        """Test sending large WebSocket message."""
        port = ws_server.get_port()
        
        received_messages = []
        
        async def server_handler(data, client_id):
            received_messages.append(data)
        
        ws_server.set_message_handler(server_handler)
        
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
    
    @pytest.mark.asyncio
    async def test_websocket_ping_pong(self, stc_wrapper, ws_server):
        """Test WebSocket ping/pong frames."""
        port = ws_server.get_port()
        
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
    
    @pytest.mark.asyncio
    async def test_multiple_websocket_clients(self, stc_wrapper, ws_server):
        """Test multiple WebSocket clients."""
        port = ws_server.get_port()
        
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
    
    @pytest.mark.asyncio
    async def test_websocket_close_frame(self, stc_wrapper, ws_server):
        """Test WebSocket close frame handling."""
        port = ws_server.get_port()
        
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
