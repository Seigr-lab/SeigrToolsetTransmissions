"""
Edge case tests for core/transport.py - targeting uncovered lines.
Missing lines: 30, 77-78, 107-108, 126-137, 143-147, 159, 173-175, 183, 191-192, 208-209, 213-218
"""

import pytest
import asyncio
from seigr_toolset_transmissions.core.transport import (
    TCPTransport,
    UDPTransport,
    TransportManager,
    TransportAddress,
)
from seigr_toolset_transmissions.utils.exceptions import STTTransportError


def test_transport_address_str():
    """Test TransportAddress __str__ method (line 30)."""
    addr = TransportAddress(host="192.168.1.100", port=8080)
    assert str(addr) == "192.168.1.100:8080"


@pytest.mark.asyncio
async def test_tcp_connect_success():
    """Test TCPTransport connect method (lines 126-137)."""
    # Start a server to connect to
    transport = TCPTransport(host="127.0.0.1", port=0)
    
    async def simple_callback(reader, writer):
        pass
    
    await transport.start(on_connection=simple_callback)
    server_port = transport.server.sockets[0].getsockname()[1]
    
    try:
        # Use connect method
        reader, writer = await transport.connect("127.0.0.1", server_port)
        
        assert reader is not None
        assert writer is not None
        
        # Clean up
        writer.close()
        await writer.wait_closed()
    finally:
        await transport.stop()


@pytest.mark.asyncio
async def test_tcp_connect_failure():
    """Test TCPTransport connect failure (lines 143-147)."""
    transport = TCPTransport(host="127.0.0.1", port=0)
    
    # Try to connect to non-existent server
    with pytest.raises(STTTransportError, match="Failed to connect"):
        await transport.connect("127.0.0.1", 1)  # Port 1 should be unavailable


@pytest.mark.asyncio
async def test_tcp_connection_callback_exception():
    """Test exception handling in _handle_connection callback (lines 77-78)."""
    transport = TCPTransport(host="127.0.0.1", port=0)
    
    async def failing_callback(reader, writer):
        raise RuntimeError("Callback failed intentionally")
    
    await transport.start(on_connection=failing_callback)
    server_port = transport.server.sockets[0].getsockname()[1]
    
    try:
        # Connect - this should trigger the callback exception
        reader, writer = await asyncio.open_connection("127.0.0.1", server_port)
        
        # Give time for exception handling
        await asyncio.sleep(0.1)
        
        # Connection should be closed despite callback failure
        writer.close()
        await writer.wait_closed()
    finally:
        await transport.stop()


@pytest.mark.asyncio
async def test_tcp_stop_connection_close_exception():
    """Test exception handling when closing connections during stop (lines 107-108, 146-147)."""
    transport = TCPTransport(host="127.0.0.1", port=0)
    
    async def simple_callback(reader, writer):
        pass
    
    await transport.start(on_connection=simple_callback)
    server_port = transport.server.sockets[0].getsockname()[1]
    
    # Create connection
    reader, writer = await asyncio.open_connection("127.0.0.1", server_port)
    
    # Manually close writer to cause exception during stop
    writer.close()
    await writer.wait_closed()
    
    # This should handle the exception gracefully when trying to close already-closed connection
    await transport.stop()


@pytest.mark.asyncio
async def test_tcp_is_running():
    """Test is_running method (line 159)."""
    transport = TCPTransport(host="127.0.0.1", port=0)
    
    # Not running initially
    assert not transport.is_running()
    
    async def simple_callback(reader, writer):
        pass
    
    await transport.start(on_connection=simple_callback)
    
    # Should be running
    assert transport.is_running()
    
    await transport.stop()
    
    # Should not be running after stop
    assert not transport.is_running()


@pytest.mark.asyncio
async def test_udp_transport_not_implemented():
    """Test UDP transport raises NotImplementedError (lines 173-175)."""
    udp = UDPTransport(host="127.0.0.1", port=9001)
    
    with pytest.raises(NotImplementedError, match="UDP transport not yet implemented"):
        await udp.start()


@pytest.mark.asyncio
async def test_udp_transport_stop():
    """Test UDP transport stop does nothing (line 183)."""
    udp = UDPTransport(host="127.0.0.1", port=9001)
    
    # Should not raise exception
    await udp.stop()


@pytest.mark.asyncio
async def test_transport_manager_initialization():
    """Test TransportManager initialization (lines 191-192)."""
    manager = TransportManager()
    
    assert manager.tcp is None
    assert manager.udp is None


@pytest.mark.asyncio
async def test_transport_manager_start_tcp():
    """Test TransportManager start_tcp method."""
    manager = TransportManager()
    
    async def simple_callback(reader, writer):
        pass
    
    await manager.start_tcp("127.0.0.1", 0, simple_callback)
    
    assert manager.tcp is not None
    assert manager.tcp.is_running()
    
    await manager.stop_all()


@pytest.mark.asyncio
async def test_transport_manager_stop_all_with_no_transports():
    """Test stop_all when no transports are running (lines 208-209)."""
    manager = TransportManager()
    
    # Should not raise exception even with no transports
    await manager.stop_all()


@pytest.mark.asyncio
async def test_transport_manager_stop_all_with_tcp():
    """Test stop_all with TCP transport (lines 208-209, 213-218)."""
    manager = TransportManager()
    
    async def simple_callback(reader, writer):
        pass
    
    await manager.start_tcp("127.0.0.1", 0, simple_callback)
    
    assert manager.tcp.is_running()
    
    await manager.stop_all()
    
    assert not manager.tcp.is_running()


@pytest.mark.asyncio
async def test_transport_manager_stop_all_with_udp():
    """Test stop_all with UDP transport (lines 210-211, 213-218)."""
    manager = TransportManager()
    
    # Manually set UDP transport without starting it
    manager.udp = UDPTransport("127.0.0.1", 9001)
    
    # Should call UDP stop without errors
    await manager.stop_all()
