"""Comprehensive WebSocket frame processing coverage."""

import pytest
import asyncio
import struct
from unittest.mock import AsyncMock

from seigr_toolset_transmissions.transport.websocket import (
    WebSocketTransport,
    WebSocketState
)
from seigr_toolset_transmissions.frame import STTFrame
from seigr_toolset_transmissions.utils.exceptions import STTTransportError


class TestWebSocketFrameProcessing:
    """Test WebSocket frame reception and processing."""
    
    @pytest.mark.asyncio
    async def test_receive_binary_with_stt_frame(self):
        """Test receiving binary frame with valid STT frame."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        received_frames = []
        
        def on_frame(frame):
            received_frames.append(frame)
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True,
            on_frame_received=on_frame
        )
        ws.state = WebSocketState.OPEN
        
        # Create STT frame
        stt_frame = STTFrame(
            frame_type=0,
            session_id=b'\x11' * 8,
            sequence=1,
            stream_id=1,
            payload=b"test"
        )
        
        frame_data = stt_frame.to_bytes()
        ws_header = bytes([0x82, len(frame_data)])
        
        reader.readexactly = AsyncMock(side_effect=[
            ws_header,
            frame_data,
            asyncio.IncompleteReadError(b'', 2)
        ])
        
        try:
            await ws.receive_frames()
        except asyncio.IncompleteReadError:
            pass
        
        assert len(received_frames) == 1
    
    @pytest.mark.asyncio
    async def test_receive_text_frame_with_handler(self):
        """Test receiving TEXT frame triggers message handler."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        received_messages = []
        
        def message_handler(msg, addr):
            received_messages.append(msg)
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True
        )
        ws.state = WebSocketState.OPEN
        ws.message_handler = message_handler
        
        text_data = b"Hello"
        header = bytes([0x81, len(text_data)])
        
        reader.readexactly = AsyncMock(side_effect=[
            header,
            text_data,
            asyncio.IncompleteReadError(b'', 2)
        ])
        
        try:
            await ws.receive_frames()
        except asyncio.IncompleteReadError:
            pass
        
        assert len(received_messages) == 1
    
    @pytest.mark.asyncio
    async def test_receive_ping_sends_pong(self):
        """Test PING frame triggers PONG response."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True
        )
        ws.state = WebSocketState.OPEN
        
        ping_data = b"ping"
        header = bytes([0x89, len(ping_data)])
        
        reader.readexactly = AsyncMock(side_effect=[
            header,
            ping_data,
            asyncio.IncompleteReadError(b'', 2)
        ])
        
        try:
            await ws.receive_frames()
        except asyncio.IncompleteReadError:
            pass
        
        assert writer.write.called
    
    @pytest.mark.asyncio
    async def test_receive_pong_frame(self):
        """Test PONG frame is handled silently."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True
        )
        ws.state = WebSocketState.OPEN
        
        pong_data = b"pong"
        header = bytes([0x8A, len(pong_data)])
        
        reader.readexactly = AsyncMock(side_effect=[
            header,
            pong_data,
            asyncio.IncompleteReadError(b'', 2)
        ])
        
        try:
            await ws.receive_frames()
        except asyncio.IncompleteReadError:
            pass
    
    @pytest.mark.asyncio
    async def test_receive_close_with_code_and_reason(self):
        """Test CLOSE frame with code and reason."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True
        )
        ws.state = WebSocketState.OPEN
        
        close_data = struct.pack("!H", 1000) + b"Normal"
        header = bytes([0x88, len(close_data)])
        
        reader.readexactly = AsyncMock(side_effect=[
            header,
            close_data
        ])
        
        await ws.receive_frames()
        
        assert ws.state == WebSocketState.CLOSED
        assert ws.close_code == 1000
        assert ws.close_reason == "Normal"
    
    @pytest.mark.asyncio
    async def test_receive_close_sends_response(self):
        """Test CLOSE triggers close response when not closing."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True
        )
        ws.state = WebSocketState.OPEN
        
        close_data = struct.pack("!H", 1001)
        header = bytes([0x88, len(close_data)])
        
        reader.readexactly = AsyncMock(side_effect=[
            header,
            close_data
        ])
        
        await ws.receive_frames()
        
        assert writer.write.called
        assert ws.state == WebSocketState.CLOSED


class TestWebSocketExtendedLengths:
    """Test extended payload length encoding."""
    
    @pytest.mark.asyncio
    async def test_receive_126_length_encoding(self):
        """Test payload length 126 (2-byte extension)."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True
        )
        ws.state = WebSocketState.OPEN
        
        payload = b"x" * 200
        header = bytes([0x82, 126])
        length_bytes = struct.pack("!H", 200)
        
        reader.readexactly = AsyncMock(side_effect=[
            header,
            length_bytes,
            payload,
            asyncio.IncompleteReadError(b'', 2)
        ])
        
        try:
            await ws.receive_frames()
        except asyncio.IncompleteReadError:
            pass
        
        # bytes_received includes header overhead
        assert ws.bytes_received >= 200
    
    @pytest.mark.asyncio
    async def test_receive_127_length_encoding(self):
        """Test payload length 127 (8-byte extension)."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True
        )
        ws.state = WebSocketState.OPEN
        
        payload = b"x" * 70000
        header = bytes([0x82, 127])
        length_bytes = struct.pack("!Q", 70000)
        
        reader.readexactly = AsyncMock(side_effect=[
            header,
            length_bytes,
            payload,
            asyncio.IncompleteReadError(b'', 2)
        ])
        
        try:
            await ws.receive_frames()
        except asyncio.IncompleteReadError:
            pass
        
        # bytes_received includes header overhead
        assert ws.bytes_received >= 70000
    
    @pytest.mark.asyncio
    async def test_frame_exceeds_max_size(self):
        """Test frame exceeding max size raises error."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True
        )
        ws.state = WebSocketState.OPEN
        ws.config.max_frame_size = 1000
        
        header = bytes([0x82, 126])
        length_bytes = struct.pack("!H", 2000)
        
        reader.readexactly = AsyncMock(side_effect=[
            header,
            length_bytes
        ])
        
        # Error is caught and sets state to CLOSED
        await ws.receive_frames()
        assert ws.state == WebSocketState.CLOSED


class TestWebSocketMasking:
    """Test WebSocket masking operations."""
    
    @pytest.mark.asyncio
    async def test_receive_masked_frame(self):
        """Test receiving masked frame (client sends masked)."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        received_messages = []
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True  # Can receive masked frames
        )
        ws.state = WebSocketState.OPEN
        ws.message_handler = lambda msg, addr: received_messages.append(msg)
        
        payload = b"test"
        mask = b"\x01\x02\x03\x04"
        masked = bytearray(payload)
        for i in range(len(masked)):
            masked[i] ^= mask[i % 4]
        
        header = bytes([0x82, 0x80 | len(payload)])
        
        reader.readexactly = AsyncMock(side_effect=[
            header,
            mask,
            bytes(masked),
            asyncio.IncompleteReadError(b'', 2)
        ])
        
        try:
            await ws.receive_frames()
        except asyncio.IncompleteReadError:
            pass
        
        assert len(received_messages) == 1
        assert received_messages[0] == payload


class TestWebSocketAsyncHandlers:
    """Test async callback handlers."""
    
    @pytest.mark.asyncio
    async def test_async_message_handler(self):
        """Test async message handler is awaited."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        received = []
        
        async def async_handler(msg, addr):
            await asyncio.sleep(0.01)
            received.append(msg)
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True
        )
        ws.state = WebSocketState.OPEN
        ws.message_handler = async_handler
        
        text_data = b"async"
        header = bytes([0x81, len(text_data)])
        
        reader.readexactly = AsyncMock(side_effect=[
            header,
            text_data,
            asyncio.IncompleteReadError(b'', 2)
        ])
        
        try:
            await ws.receive_frames()
        except asyncio.IncompleteReadError:
            pass
        
        assert len(received) == 1
    
    @pytest.mark.asyncio
    async def test_async_frame_handler(self):
        """Test async frame received handler."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        received_frames = []
        
        async def async_frame_handler(frame):
            await asyncio.sleep(0.01)
            received_frames.append(frame)
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True,
            on_frame_received=async_frame_handler
        )
        ws.state = WebSocketState.OPEN
        
        stt_frame = STTFrame(
            frame_type=0,
            session_id=b'\xAA' * 8,
            sequence=99,
            stream_id=5,
            payload=b"async"
        )
        
        frame_data = stt_frame.to_bytes()
        header = bytes([0x82, len(frame_data)])
        
        reader.readexactly = AsyncMock(side_effect=[
            header,
            frame_data,
            asyncio.IncompleteReadError(b'', 2)
        ])
        
        try:
            await ws.receive_frames()
        except asyncio.IncompleteReadError:
            pass
        
        assert len(received_frames) == 1


class TestWebSocketErrors:
    """Test error handling paths."""
    
    @pytest.mark.asyncio
    async def test_receive_cancelled(self):
        """Test receive handles cancellation."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True
        )
        ws.state = WebSocketState.OPEN
        
        reader.readexactly = AsyncMock(side_effect=asyncio.CancelledError())
        
        with pytest.raises(asyncio.CancelledError):
            await ws.receive_frames()
    
    @pytest.mark.asyncio
    async def test_receive_general_exception(self):
        """Test receive handles general exceptions."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True
        )
        ws.state = WebSocketState.OPEN
        
        reader.readexactly = AsyncMock(side_effect=Exception("Network error"))
        
        await ws.receive_frames()
        
        assert ws.state == WebSocketState.CLOSED
    
    @pytest.mark.asyncio
    async def test_binary_not_valid_stt_frame(self):
        """Test binary frame that's not valid STT frame."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        frame_called = False
        
        def frame_handler(frame):
            nonlocal frame_called
            frame_called = True
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True,
            on_frame_received=frame_handler
        )
        ws.state = WebSocketState.OPEN
        
        bad_data = b"\xFF\xFF\xFF\xFF"
        header = bytes([0x82, len(bad_data)])
        
        reader.readexactly = AsyncMock(side_effect=[
            header,
            bad_data,
            asyncio.IncompleteReadError(b'', 2)
        ])
        
        try:
            await ws.receive_frames()
        except asyncio.IncompleteReadError:
            pass
        
        assert not frame_called


class TestWebSocketConnection:
    """Test connection operations."""
    
    @pytest.mark.asyncio
    async def test_connect_server_mode_error(self):
        """Test connect raises error in server mode."""
        ws = WebSocketTransport(host="127.0.0.1", port=8080, is_server=True)
        
        with pytest.raises(STTTransportError, match="client mode"):
            await ws.connect()
    
    @pytest.mark.asyncio
    async def test_connect_no_host_error(self):
        """Test connect requires host and port."""
        ws = WebSocketTransport(is_client=True)
        
        with pytest.raises(STTTransportError, match="Host and port required"):
            await ws.connect()


class TestWebSocketBinaryWithMessageHandler:
    """Test binary frames with message handler (no frame handler)."""
    
    @pytest.mark.asyncio
    async def test_binary_with_message_handler_no_frame_handler(self):
        """Test binary frame with message handler but no frame handler."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = AsyncMock(spec=asyncio.StreamWriter)
        
        received_messages = []
        
        def message_handler(msg, addr):
            received_messages.append(msg)
        
        ws = WebSocketTransport(
            reader=reader,
            writer=writer,
            is_client=True
        )
        ws.state = WebSocketState.OPEN
        ws.message_handler = message_handler
        # No on_frame_received handler
        
        binary_data = b"raw binary"
        header = bytes([0x82, len(binary_data)])
        
        reader.readexactly = AsyncMock(side_effect=[
            header,
            binary_data,
            asyncio.IncompleteReadError(b'', 2)
        ])
        
        try:
            await ws.receive_frames()
        except asyncio.IncompleteReadError:
            pass
        
        assert len(received_messages) == 1
        assert received_messages[0] == binary_data
