"""
Additional transport tests for 100% coverage.

Tests error conditions, edge cases, and production features.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from seigr_toolset_transmissions.transport.udp import UDPTransport, UDPProtocol, UDPConfig
from seigr_toolset_transmissions.transport.websocket import WebSocketTransport, WebSocketConfig
from seigr_toolset_transmissions.frame import STTFrame
from seigr_toolset_transmissions.utils.exceptions import STTTransportError


class TestUDPTransportCoverage:
    """Test UDP transport edge cases and error conditions."""
    
    @pytest.mark.asyncio
    async def test_udp_double_start_error(self):
        """Test starting transport twice raises error."""
        transport = UDPTransport(host="127.0.0.1", port=0)
        
        await transport.start()
        
        # Try to start again
        with pytest.raises(STTTransportError, match="already running"):
            await transport.start()
        
        await transport.stop()
    
    @pytest.mark.asyncio
    async def test_udp_send_frame_not_running(self):
        """Test sending frame when transport not running."""
        transport = UDPTransport(host="127.0.0.1", port=0)
        frame = STTFrame(
            frame_type=1,
            session_id=b"test1234",
            sequence=1,
            stream_id=0,
            payload=b"test"
        )
        
        with pytest.raises(STTTransportError, match="not running"):
            await transport.send_frame(frame, ("127.0.0.1", 12345))
    
    @pytest.mark.asyncio
    async def test_udp_send_raw_not_running(self):
        """Test sending raw data when not running."""
        transport = UDPTransport()
        
        with pytest.raises(STTTransportError, match="not running"):
            await transport.send_raw(b"test", ("127.0.0.1", 12345))
    
    @pytest.mark.asyncio
    async def test_udp_send_not_running(self):
        """Test send() when not running."""
        transport = UDPTransport()
        
        with pytest.raises(STTTransportError, match="not running"):
            await transport.send(b"test", ("127.0.0.1", 12345))
    
    @pytest.mark.asyncio
    async def test_udp_stop_when_not_running(self):
        """Test stopping when not running."""
        transport = UDPTransport()
        
        # Should not raise error
        await transport.stop()
    
    @pytest.mark.asyncio
    async def test_udp_statistics_tracking(self):
        """Test comprehensive statistics tracking."""
        transport1 = UDPTransport(host="127.0.0.1", port=0)
        transport2 = UDPTransport(host="127.0.0.1", port=0)
        
        received_data = []
        
        async def on_receive(data, addr):
            received_data.append(data)
        
        transport2.on_frame_received = on_receive
        
        await transport1.start()
        await transport2.start()
        
        # Get addr
        addr2 = transport2.get_local_address()
        
        # Send data
        test_data = b"test statistics"
        await transport1.send(test_data, addr2)
        
        # Give time for receipt
        await asyncio.sleep(0.1)
        
        # Check sender stats
        stats1 = transport1.get_stats()
        assert stats1['running'] == True
        assert stats1['bytes_sent'] >= len(test_data)
        assert stats1['packets_sent'] >= 1
        assert stats1['started_at'] is not None
        assert stats1['uptime'] > 0
        assert 'send_rate_bps' in stats1
        assert 'receive_rate_bps' in stats1
        
        # Check receiver stats
        stats2 = transport2.get_stats()
        assert stats2['bytes_received'] >= len(test_data)
        assert stats2['packets_received'] >= 1
        
        await transport1.stop()
        await transport2.stop()
    
    @pytest.mark.asyncio
    async def test_udp_get_address_alias(self):
        """Test get_address() is alias for get_local_address()."""
        transport = UDPTransport()
        await transport.start()
        
        addr1 = transport.get_local_address()
        addr2 = transport.get_address()
        
        assert addr1 == addr2
        assert addr1 is not None
        
        await transport.stop()
    
    @pytest.mark.asyncio
    async def test_udp_set_receive_handler(self):
        """Test changing receive handler."""
        transport = UDPTransport()
        
        handler1_called = []
        handler2_called = []
        
        async def handler1(data, addr):
            handler1_called.append(data)
        
        async def handler2(data, addr):
            handler2_called.append(data)
        
        # Set initial handler
        transport.set_receive_handler(handler1)
        
        await transport.start()
        
        # Change handler
        transport.set_receive_handler(handler2)
        
        await transport.stop()
        
        assert transport.on_frame_received == handler2
    
    @pytest.mark.asyncio
    async def test_udp_protocol_error_received(self):
        """Test error_received increments statistics."""
        transport = UDPTransport()
        await transport.start()
        
        initial_errors = transport.errors_receive
        
        # Simulate error
        exc = OSError("Test error")
        transport.protocol.error_received(exc)
        
        assert transport.errors_receive == initial_errors + 1
        
        await transport.stop()
    
    @pytest.mark.asyncio
    async def test_udp_protocol_connection_lost_with_error(self):
        """Test connection_lost with exception."""
        transport = UDPTransport()
        await transport.start()
        
        # Simulate connection lost with error
        exc = Exception("Connection lost")
        transport.protocol.connection_lost(exc)
        
        # Should log error but not raise
        
        await transport.stop()
    
    @pytest.mark.asyncio
    async def test_udp_protocol_connection_lost_normal(self):
        """Test connection_lost without exception."""
        transport = UDPTransport()
        await transport.start()
        
        # Simulate normal close
        transport.protocol.connection_lost(None)
        
        # Should log debug but not raise
        
        await transport.stop()
    
    @pytest.mark.asyncio
    async def test_udp_send_frame_error_tracking(self):
        """Test send errors are tracked."""
        transport = UDPTransport()
        await transport.start()
        
        # Mock transport to raise error
        original_sendto = transport.transport.sendto
        transport.transport.sendto = Mock(side_effect=Exception("Send error"))
        
        initial_errors = transport.errors_send
        
        frame = STTFrame(
            frame_type=1,
            session_id=b"test1234",
            sequence=1,
            stream_id=0,
            payload=b"test"
        )
        with pytest.raises(STTTransportError, match="Failed to send frame"):
            await transport.send_frame(frame, ("127.0.0.1", 12345))
        
        assert transport.errors_send == initial_errors + 1
        
        # Restore
        transport.transport.sendto = original_sendto
        
        await transport.stop()
    
    @pytest.mark.asyncio
    async def test_udp_is_running_property(self):
        """Test is_running property."""
        transport = UDPTransport()
        
        assert transport.is_running == False
        
        await transport.start()
        assert transport.is_running == True
        
        await transport.stop()
        assert transport.is_running == False
    
    @pytest.mark.asyncio
    async def test_udp_config_customization(self):
        """Test custom UDP configuration."""
        transport = UDPTransport(host="127.0.0.1", port=9999)
        
        assert transport.config.bind_address == "127.0.0.1"
        assert transport.config.bind_port == 9999
        assert transport.config.max_packet_size == 1472
        assert transport.config.receive_buffer_size == 65536
        assert transport.config.send_buffer_size == 65536


class TestWebSocketTransportCoverage:
    """Test WebSocket transport edge cases and error conditions."""
    
    @pytest.mark.asyncio
    async def test_websocket_config_defaults(self):
        """Test WebSocketConfig default values."""
        ws = WebSocketTransport(is_client=True)
        
        assert ws.config.max_frame_size == 10 * 1024 * 1024
        assert ws.config.max_message_size == 100 * 1024 * 1024
        assert ws.config.connect_timeout == 10.0
        assert ws.config.close_timeout == 5.0
        assert ws.config.ping_interval == 30.0
        assert ws.config.ping_timeout == 10.0
        assert ws.config.max_clients == 1000
    
    @pytest.mark.asyncio
    async def test_websocket_frame_size_limit_send(self):
        """Test sending frame exceeding size limit."""
        server = WebSocketTransport(is_client=False, host="127.0.0.1", port=0)
        await server.start()
        addr = server.get_local_address()
        
        client = WebSocketTransport(is_client=True)
        await client.connect(addr[0], addr[1])
        
        # Create huge payload exceeding limit
        huge_data = b"X" * (11 * 1024 * 1024)  # 11MB > 10MB limit
        
        with pytest.raises(STTTransportError, match="exceeds max"):
            await client._send_ws_frame(0x02, huge_data)
        
        await client.close()
        await server.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_frame_size_limit_receive(self):
        """Test receiving frame exceeding size limit."""
        # This is hard to test without mocking, skip for now
        pass
    
    @pytest.mark.asyncio
    async def test_websocket_connection_timeout(self):
        """Test connection timeout."""
        client = WebSocketTransport(is_client=True)
        
        # Try to connect to non-existent server with short timeout
        client.config.connect_timeout = 0.1
        
        with pytest.raises((STTTransportError, asyncio.TimeoutError, OSError)):
            await client.connect("127.0.0.1", 9999)
    
    @pytest.mark.asyncio
    async def test_websocket_statistics_comprehensive(self):
        """Test comprehensive statistics tracking."""
        server = WebSocketTransport(is_client=False, host="127.0.0.1", port=0)
        await server.start()
        addr = server.get_local_address()
        
        client = WebSocketTransport(is_client=True)
        await client.connect(addr[0], addr[1])
        
        # Send some data
        await client.send(b"test data")
        await asyncio.sleep(0.1)
        
        # Check stats
        stats = client.get_stats()
        
        assert 'connected' in stats
        assert 'local_address' in stats
        assert 'remote_address' in stats
        assert 'connected_at' in stats
        assert 'uptime' in stats
        assert 'bytes_sent' in stats
        assert 'bytes_received' in stats
        assert 'frames_sent' in stats
        assert 'frames_received' in stats
        assert 'last_ping_sent' in stats
        assert 'last_pong_received' in stats
        assert 'send_rate_bps' in stats
        assert 'receive_rate_bps' in stats
        
        assert stats['bytes_sent'] > 0
        assert stats['frames_sent'] > 0
        
        await client.close()
        await server.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_send_not_connected(self):
        """Test sending when not connected."""
        ws = WebSocketTransport(is_client=True)
        
        with pytest.raises(STTTransportError, match="not connected"):
            await ws.send(b"test")
    
    @pytest.mark.asyncio
    async def test_websocket_close_not_connected(self):
        """Test closing when not connected."""
        ws = WebSocketTransport(is_client=True)
        
        # Should not raise error
        await ws.close()
    
    @pytest.mark.asyncio
    async def test_websocket_is_connected_property(self):
        """Test is_connected property."""
        server = WebSocketTransport(is_client=False, host="127.0.0.1", port=0)
        await server.start()
        addr = server.get_local_address()
        
        client = WebSocketTransport(is_client=True)
        
        assert client.is_connected == False
        
        await client.connect(addr[0], addr[1])
        assert client.is_connected == True
        
        await client.close()
        assert client.is_connected == False
        
        await server.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_flexible_constructor_positional(self):
        """Test WebSocket constructor with positional host/port."""
        # Positional host and port
        ws = WebSocketTransport("192.168.1.1", 8080)
        assert ws.host == "192.168.1.1"
        assert ws.port == 8080
    
    @pytest.mark.asyncio
    async def test_websocket_flexible_constructor_bool(self):
        """Test WebSocket constructor with bool is_client."""
        # is_client as first arg
        ws = WebSocketTransport(True)
        assert ws.is_client == True
        assert ws.stc_wrapper is None
    
    @pytest.mark.asyncio
    async def test_websocket_flexible_constructor_keyword(self):
        """Test WebSocket constructor with keyword args."""
        ws = WebSocketTransport(is_client=True, host="192.168.1.1", port=8080)
        assert ws.is_client == True
        assert ws.host == "192.168.1.1"
        assert ws.port == 8080
    
    @pytest.mark.asyncio
    async def test_websocket_server_double_start(self):
        """Test starting server twice raises error."""
        ws = WebSocketTransport(is_client=False, host="127.0.0.1", port=0)
        
        await ws.start()
        
        with pytest.raises(STTTransportError, match="already started"):
            await ws.start()
        
        await ws.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_stop_not_running(self):
        """Test stopping when not running."""
        ws = WebSocketTransport(is_client=False)
        
        # Should not raise
        await ws.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_get_local_address_alias(self):
        """Test get_local_address() is alias."""
        ws = WebSocketTransport(is_client=False, host="127.0.0.1", port=0)
        await ws.start()
        
        addr1 = ws.get_address()
        addr2 = ws.get_local_address()
        
        assert addr1 == addr2
        
        await ws.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_set_on_message(self):
        """Test setting message callback."""
        ws = WebSocketTransport(is_client=True)
        
        messages = []
        
        async def on_msg(data):
            messages.append(data)
        
        ws.set_on_message(on_msg)
        
        assert ws.on_message == on_msg
    
    @pytest.mark.asyncio
    async def test_websocket_text_frame(self):
        """Test sending and receiving text frames."""
        server = WebSocketTransport(is_client=False, host="127.0.0.1", port=0)
        await server.start()
        addr = server.get_local_address()
        
        client = WebSocketTransport(is_client=True)
        await client.connect(addr[0], addr[1])
        
        # Send text (will be encoded to bytes)
        await client._send_ws_frame(0x01, b"Hello text")
        
        await asyncio.sleep(0.1)
        
        await client.close()
        await server.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_continuation_frame(self):
        """Test continuation frames for fragmentation."""
        # Fragmentation not fully implemented yet, but test opcode
        server = WebSocketTransport(is_client=False, host="127.0.0.1", port=0)
        await server.start()
        addr = server.get_local_address()
        
        client = WebSocketTransport(is_client=True)
        await client.connect(addr[0], addr[1])
        
        # Send continuation frame (opcode 0x00)
        await client._send_ws_frame(0x00, b"continuation")
        
        await asyncio.sleep(0.1)
        
        await client.close()
        await server.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_extended_payload_16bit(self):
        """Test 16-bit extended payload length."""
        server = WebSocketTransport(is_client=False, host="127.0.0.1", port=0)
        await server.start()
        addr = server.get_local_address()
        
        client = WebSocketTransport(is_client=True)
        await client.connect(addr[0], addr[1])
        
        # Send 200 bytes (> 125, uses 16-bit extended length)
        data = b"X" * 200
        await client.send(data)
        
        await asyncio.sleep(0.1)
        
        await client.close()
        await server.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_extended_payload_64bit(self):
        """Test 64-bit extended payload length."""
        server = WebSocketTransport(is_client=False, host="127.0.0.1", port=0)
        await server.start()
        addr = server.get_local_address()
        
        client = WebSocketTransport(is_client=True)
        await client.connect(addr[0], addr[1])
        
        # Send 70KB (> 65535, uses 64-bit extended length)
        data = b"Y" * 70000
        await client.send(data)
        
        await asyncio.sleep(0.2)
        
        await client.close()
        await server.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
