"""
Tests for core Transport classes.
"""

import pytest
import asyncio

from seigr_toolset_transmissions.core.transport import (
    TCPTransport,
    TransportAddress,
)
from seigr_toolset_transmissions.utils.exceptions import STTTransportError


class TestTransportAddress:
    """Test TransportAddress dataclass."""
    
    def test_create_address(self):
        """Test creating transport address."""
        addr = TransportAddress(host="192.168.1.1", port=8080)
        
        assert addr.host == "192.168.1.1"
        assert addr.port == 8080
        assert str(addr) == "192.168.1.1:8080"
    
    def test_address_string_representation(self):
        """Test address string formatting."""
        addr = TransportAddress("127.0.0.1", 443)
        assert str(addr) == "127.0.0.1:443"


class TestTCPTransport:
    """Test TCP transport implementation."""
    
    @pytest.mark.asyncio
    async def test_create_tcp_transport(self):
        """Test creating TCP transport."""
        transport = TCPTransport(host="127.0.0.1", port=0)
        
        assert transport.host == "127.0.0.1"
        assert transport.port == 0
        assert transport.server is None
        assert len(transport.connections) == 0
    
    @pytest.mark.asyncio
    async def test_tcp_start_stop(self):
        """Test starting and stopping TCP server."""
        transport = TCPTransport(host="127.0.0.1", port=0)
        
        connections_received = []
        
        async def on_connection(reader, writer):
            connections_received.append((reader, writer))
        
        # Start server
        await transport.start(on_connection)
        assert transport.server is not None
        
        # Stop server
        await transport.stop()
        assert len(transport.connections) == 0
    
    @pytest.mark.asyncio
    async def test_tcp_client_connection(self):
        """Test TCP client connecting to server."""
        server_transport = TCPTransport(host="127.0.0.1", port=0)
        
        server_connections = []
        
        async def on_server_connection(reader, writer):
            server_connections.append((reader, writer))
            # Read data
            data = await reader.read(1024)
            # Echo back
            writer.write(data)
            await writer.drain()
        
        # Start server
        await server_transport.start(on_server_connection)
        
        # Get server port
        server_addr = server_transport.server.sockets[0].getsockname()
        server_port = server_addr[1]
        
        # Create client transport
        client_transport = TCPTransport()
        
        # Connect client to server
        reader, writer = await client_transport.connect("127.0.0.1", server_port)
        
        # Send data
        test_data = b"Hello TCP"
        writer.write(test_data)
        await writer.drain()
        
        # Read echo
        response = await reader.read(1024)
        assert response == test_data
        
        # Cleanup
        writer.close()
        await writer.wait_closed()
        
        await server_transport.stop()
        await client_transport.stop()
    
    @pytest.mark.asyncio
    async def test_tcp_multiple_connections(self):
        """Test handling multiple simultaneous connections."""
        transport = TCPTransport(host="127.0.0.1", port=0)
        
        connections = []
        
        async def on_connection(reader, writer):
            connections.append((reader, writer))
            # Keep connection open
            await asyncio.sleep(0.5)
        
        await transport.start(on_connection)
        
        server_addr = transport.server.sockets[0].getsockname()
        server_port = server_addr[1]
        
        # Create multiple client connections
        clients = []
        for _i in range(3):
            r, w = await asyncio.open_connection("127.0.0.1", server_port)
            clients.append((r, w))
        
        # Give time for server to accept connections
        await asyncio.sleep(0.1)
        
        # Should have 3 connections
        assert len(transport.connections) >= 3
        
        # Cleanup
        for r, w in clients:
            w.close()
            await w.wait_closed()
        
        await transport.stop()
    
    @pytest.mark.asyncio
    async def test_tcp_connection_error_handling(self):
        """Test error handling during connection."""
        transport = TCPTransport()
        
        # Try to connect to non-existent server
        with pytest.raises(STTTransportError, match="Failed to connect"):
            await transport.connect("127.0.0.1", 9999)
    
    @pytest.mark.asyncio
    async def test_tcp_server_closes_connections_on_stop(self):
        """Test that stopping server closes all connections."""
        transport = TCPTransport(host="127.0.0.1", port=0)
        
        async def on_connection(reader, writer):
            # Keep connection alive
            try:
                while True:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                pass  # Connection handler cancelled
        
        await transport.start(on_connection)
        
        server_addr = transport.server.sockets[0].getsockname()
        server_port = server_addr[1]
        
        # Create client connection
        _r, w = await asyncio.open_connection("127.0.0.1", server_port)
        
        await asyncio.sleep(0.1)
        
        # Stop transport
        await transport.stop()
        
        # Connections should be closed
        assert len(transport.connections) == 0
        
        # Cleanup client
        w.close()
        await w.wait_closed()
    
    @pytest.mark.asyncio
    async def test_tcp_callback_exception_handling(self):
        """Test that exceptions in callback don't crash server."""
        transport = TCPTransport(host="127.0.0.1", port=0)
        
        async def on_connection_with_error(reader, writer):
            raise Exception("Test error in callback")
        
        await transport.start(on_connection_with_error)
        
        server_addr = transport.server.sockets[0].getsockname()
        server_port = server_addr[1]
        
        # Connect - should not crash server
        _r, w = await asyncio.open_connection("127.0.0.1", server_port)
        
        # Give time for error to be handled
        await asyncio.sleep(0.1)
        
        # Server should still be running
        assert transport.server is not None
        
        # Cleanup
        w.close()
        await w.wait_closed()
        await transport.stop()
    
    @pytest.mark.asyncio
    async def test_tcp_default_port(self):
        """Test TCP transport uses default port."""
        from seigr_toolset_transmissions.utils.constants import STT_DEFAULT_TCP_PORT
        
        transport = TCPTransport()
        
        assert transport.port == STT_DEFAULT_TCP_PORT
    
    @pytest.mark.asyncio
    async def test_tcp_connection_tracking(self):
        """Test that connections are tracked correctly."""
        transport = TCPTransport(host="127.0.0.1", port=0)
        
        connected_count = []
        
        async def on_connection(reader, writer):
            connected_count.append(len(transport.connections))
            await asyncio.sleep(0.2)
        
        await transport.start(on_connection)
        
        server_addr = transport.server.sockets[0].getsockname()
        server_port = server_addr[1]
        
        # Connect client
        _r, w = await asyncio.open_connection("127.0.0.1", server_port)
        
        await asyncio.sleep(0.1)
        
        # Should have 1 connection tracked
        assert len(transport.connections) == 1
        
        # Close client
        w.close()
        await w.wait_closed()
        
        # Give time for cleanup
        await asyncio.sleep(0.3)
        
        # Connection should be removed from tracking
        assert len(transport.connections) == 0
        
        await transport.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
