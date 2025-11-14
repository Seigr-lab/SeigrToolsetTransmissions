"""
Native WebSocket implementation (RFC 6455).

Replaces websockets library dependency with self-contained implementation.
Supports both client and server roles for bidirectional frame transport.
"""

import asyncio
import base64
import hashlib
import secrets
import struct
from typing import Optional, Callable, Dict, Any, Tuple
from enum import IntEnum

from ..frame import STTFrame
from ..utils.exceptions import STTTransportError
from ..utils.logging import get_logger


logger = get_logger(__name__)


class WebSocketOpcode(IntEnum):
    """WebSocket frame opcodes (RFC 6455)."""
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA


class WebSocketState(IntEnum):
    """WebSocket connection states."""
    CONNECTING = 0
    OPEN = 1
    CLOSING = 2
    CLOSED = 3


WEBSOCKET_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WebSocketTransport:
    """
    Native WebSocket transport (RFC 6455).
    
    Self-contained WebSocket implementation without external dependencies.
    Supports STT frames over WebSocket binary frames.
    """
    
    def __init__(
        self,
        reader: Optional[asyncio.StreamReader] = None,
        writer: Optional[asyncio.StreamWriter] = None,
        is_client: bool = False,
        host: Optional[str] = None,
        port: Optional[int] = None,
        stc_wrapper: Optional['STCWrapper'] = None,
        on_frame_received: Optional[Callable[[STTFrame], None]] = None
    ):
        """
        Initialize WebSocket transport.
        
        Args:
            reader: Async stream reader (optional if connecting later)
            writer: Async stream writer (optional if connecting later)
            is_client: True if client role, False if server
            host: Host to connect to (if connecting)
            port: Port to connect to (if connecting)
            stc_wrapper: STC wrapper for encryption
            on_frame_received: Callback for received STT frames
        """
        self.reader = reader
        self.writer = writer
        self.is_client = is_client
        self.host = host
        self.port = port
        self.stc_wrapper = stc_wrapper
        self.on_frame_received = on_frame_received
        
        self.state = WebSocketState.CONNECTING
        self.close_code = None
        self.close_reason = None
    
    @classmethod
    async def connect(
        cls,
        host: str,
        port: int,
        path: str = "/",
        on_frame_received: Optional[Callable[[STTFrame], None]] = None
    ) -> 'WebSocketTransport':
        """
        Connect to WebSocket server.
        
        Args:
            host: Server hostname
            port: Server port
            path: Request path
            on_frame_received: Frame callback
            
        Returns:
            Connected WebSocket transport
        """
        try:
            # Open TCP connection
            reader, writer = await asyncio.open_connection(host, port)
            
            # Create transport instance
            ws = cls(reader, writer, is_client=True, on_frame_received=on_frame_received)
            
            # Perform WebSocket handshake
            await ws._client_handshake(host, port, path)
            
            ws.state = WebSocketState.OPEN
            
            logger.info(f"WebSocket connected to {host}:{port}{path}")
            
            return ws
            
        except Exception as e:
            raise STTTransportError(f"WebSocket connection failed: {e}")
    
    async def _client_handshake(self, host: str, port: int, path: str) -> None:
        """
        Perform client-side WebSocket handshake.
        
        Args:
            host: Server hostname
            port: Server port
            path: Request path
        """
        # Generate random key
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        
        # Build handshake request
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        
        # Send request
        self.writer.write(request.encode())
        await self.writer.drain()
        
        # Read response
        response_line = await self.reader.readline()
        if not response_line.startswith(b"HTTP/1.1 101"):
            raise STTTransportError(f"Handshake failed: {response_line.decode()}")
        
        # Read headers
        headers = {}
        while True:
            line = await self.reader.readline()
            if line == b"\r\n":
                break
            
            if b":" in line:
                name, value = line.decode().split(":", 1)
                headers[name.strip().lower()] = value.strip()
        
        # Verify accept key
        expected_accept = base64.b64encode(
            hashlib.sha1(key.encode() + WEBSOCKET_GUID).digest()
        ).decode()
        
        if headers.get("sec-websocket-accept") != expected_accept:
            raise STTTransportError("Invalid Sec-WebSocket-Accept")
    
    async def send_frame(self, frame: STTFrame) -> None:
        """
        Send STT frame over WebSocket.
        
        Args:
            frame: STT frame to send
        """
        if self.state != WebSocketState.OPEN:
            raise STTTransportError(f"Cannot send in state {self.state.name}")
        
        # Serialize STT frame
        frame_bytes = frame.to_bytes()
        
        # Send as WebSocket binary frame
        await self._send_ws_frame(WebSocketOpcode.BINARY, frame_bytes)
    
    async def _send_ws_frame(self, opcode: WebSocketOpcode, payload: bytes) -> None:
        """
        Send WebSocket frame.
        
        Args:
            opcode: Frame opcode
            payload: Frame payload
        """
        # Build WebSocket frame header
        header = bytearray()
        
        # Byte 0: FIN + opcode
        header.append(0x80 | opcode)
        
        # Byte 1: MASK + payload length
        payload_len = len(payload)
        
        if self.is_client:
            mask_bit = 0x80
        else:
            mask_bit = 0x00
        
        if payload_len < 126:
            header.append(mask_bit | payload_len)
        elif payload_len < 65536:
            header.append(mask_bit | 126)
            header.extend(struct.pack("!H", payload_len))
        else:
            header.append(mask_bit | 127)
            header.extend(struct.pack("!Q", payload_len))
        
        # Masking (required for client)
        if self.is_client:
            mask = secrets.token_bytes(4)
            header.extend(mask)
            
            # Mask payload
            masked_payload = bytearray(payload)
            for i in range(len(masked_payload)):
                masked_payload[i] ^= mask[i % 4]
            
            payload = bytes(masked_payload)
        
        # Send frame
        self.writer.write(header + payload)
        await self.writer.drain()
    
    async def receive_frames(self) -> None:
        """
        Receive WebSocket frames in loop.
        
        Processes incoming frames and invokes callbacks.
        Runs until connection closes.
        """
        try:
            while self.state == WebSocketState.OPEN:
                # Read WebSocket frame
                opcode, payload = await self._receive_ws_frame()
                
                if opcode == WebSocketOpcode.BINARY:
                    # Parse STT frame
                    frame = STTFrame.from_bytes(payload)
                    
                    # Invoke callback
                    if self.on_frame_received:
                        self.on_frame_received(frame)
                
                elif opcode == WebSocketOpcode.PING:
                    # Respond with pong
                    await self._send_ws_frame(WebSocketOpcode.PONG, payload)
                
                elif opcode == WebSocketOpcode.CLOSE:
                    # Handle close frame
                    if len(payload) >= 2:
                        self.close_code = struct.unpack("!H", payload[:2])[0]
                        self.close_reason = payload[2:].decode('utf-8', errors='ignore')
                    
                    # Send close response if not already closing
                    if self.state != WebSocketState.CLOSING:
                        await self._send_ws_frame(WebSocketOpcode.CLOSE, payload)
                    
                    self.state = WebSocketState.CLOSED
                    break
        
        except Exception as e:
            logger.error(f"WebSocket receive error: {e}")
            self.state = WebSocketState.CLOSED
    
    async def _receive_ws_frame(self) -> Tuple[WebSocketOpcode, bytes]:
        """
        Receive single WebSocket frame.
        
        Returns:
            Tuple of (opcode, payload)
        """
        # Read first 2 bytes
        header = await self.reader.readexactly(2)
        
        # Parse header
        fin = (header[0] & 0x80) != 0
        opcode = WebSocketOpcode(header[0] & 0x0F)
        masked = (header[1] & 0x80) != 0
        payload_len = header[1] & 0x7F
        
        # Read extended payload length
        if payload_len == 126:
            payload_len = struct.unpack("!H", await self.reader.readexactly(2))[0]
        elif payload_len == 127:
            payload_len = struct.unpack("!Q", await self.reader.readexactly(8))[0]
        
        # Read mask key if present
        if masked:
            mask = await self.reader.readexactly(4)
        
        # Read payload
        payload = await self.reader.readexactly(payload_len)
        
        # Unmask if needed
        if masked:
            unmasked = bytearray(payload)
            for i in range(len(unmasked)):
                unmasked[i] ^= mask[i % 4]
            payload = bytes(unmasked)
        
        return opcode, payload
    
    async def close(self, code: int = 1000, reason: str = "") -> None:
        """
        Close WebSocket connection.
        
        Args:
            code: Close code (1000 = normal)
            reason: Close reason string
        """
        if self.state == WebSocketState.CLOSED:
            return
        
        self.state = WebSocketState.CLOSING
        
        # Build close payload
        close_payload = struct.pack("!H", code)
        if reason:
            close_payload += reason.encode('utf-8')
        
        # Send close frame
        await self._send_ws_frame(WebSocketOpcode.CLOSE, close_payload)
        
        # Wait for close response
        await asyncio.sleep(0.1)
        
        # Close TCP connection
        self.writer.close()
        await self.writer.wait_closed()
        
        self.state = WebSocketState.CLOSED
        
        logger.info(f"WebSocket closed (code={code})")
    
    def is_open(self) -> bool:
        """Check if connection is open."""
        return self.state == WebSocketState.OPEN
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            'state': self.state.name,
            'is_client': self.is_client,
            'close_code': self.close_code,
            'close_reason': self.close_reason,
        }
