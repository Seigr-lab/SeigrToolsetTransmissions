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
import time
from typing import Optional, Callable, Dict, Any, Tuple, Union
from enum import IntEnum
from dataclasses import dataclass

from ..frame import STTFrame
from ..utils.exceptions import STTTransportError
from ..utils.logging import get_logger


logger = get_logger(__name__)


@dataclass
class WebSocketConfig:
    """WebSocket transport configuration."""
    
    max_frame_size: int = 10 * 1024 * 1024  # 10MB max frame
    max_message_size: int = 100 * 1024 * 1024  # 100MB max message
    connect_timeout: float = 10.0  # Connection timeout in seconds
    close_timeout: float = 5.0  # Close handshake timeout
    ping_interval: float = 30.0  # Ping interval for keepalive
    ping_timeout: float = 10.0  # Pong response timeout
    max_clients: int = 1000  # Max concurrent clients (server mode)
    

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
        host_or_reader: Optional[Union[str, asyncio.StreamReader]] = None,
        port_or_writer: Optional[Union[int, asyncio.StreamWriter]] = None,
        stc_wrapper_or_is_client: Optional[Union['STCWrapper', bool]] = None,
        is_server: bool = False,
        is_client: Optional[bool] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        stc_wrapper: Optional['STCWrapper'] = None,
        on_frame_received: Optional[Callable[[STTFrame], None]] = None,
        # Legacy parameters
        reader: Optional[asyncio.StreamReader] = None,
        writer: Optional[asyncio.StreamWriter] = None
    ):
        """
        Initialize WebSocket transport.
        
        Supports multiple calling conventions:
        - WebSocketTransport("127.0.0.1", 8080, stc_wrapper, is_server=True)
        - WebSocketTransport(reader=reader, writer=writer, is_client=True)
        - WebSocketTransport(host="127.0.0.1", port=8080, is_server=True)
        
        Args:
            host_or_reader: Host string or StreamReader
            port_or_writer: Port number or StreamWriter
            stc_wrapper_or_is_client: STCWrapper or is_client bool
            is_server: True if server role
            is_client: True if client role (optional)
            host: Host to connect to
            port: Port to connect to
            stc_wrapper: STC wrapper for encryption
            on_frame_received: Callback for received STT frames
            reader: Async stream reader (legacy)
            writer: Async stream writer (legacy)
        """
        # Parse flexible arguments
        if isinstance(host_or_reader, str):
            # Called as WebSocketTransport("host", port, stc_wrapper)
            self.host = host_or_reader
            self.port = port_or_writer
            if isinstance(stc_wrapper_or_is_client, bool):
                # WebSocketTransport("host", port, is_client=True)
                if is_client is None:
                    is_client = stc_wrapper_or_is_client
                self.stc_wrapper = stc_wrapper
            else:
                # WebSocketTransport("host", port, stc_wrapper)
                self.stc_wrapper = stc_wrapper_or_is_client
            self.reader = reader
            self.writer = writer
        elif isinstance(host_or_reader, asyncio.StreamReader):
            # Called with reader/writer
            self.reader = host_or_reader
            self.writer = port_or_writer
            self.host = host
            self.port = port
            self.stc_wrapper = stc_wrapper or stc_wrapper_or_is_client
        else:
            # Called with keyword arguments only
            self.reader = reader
            self.writer = writer
            self.host = host
            self.port = port
            self.stc_wrapper = stc_wrapper
        
        # Handle is_client/is_server flags
        if is_client is None:
            is_client = not is_server
        self.is_client = is_client
        self.is_server = is_server if is_server else not is_client
        
        self.on_frame_received = on_frame_received
        self.message_handler = None  # For raw message handling
        
        self.state = WebSocketState.CONNECTING
        self.close_code = None
        self.close_reason = None
        
        # Configuration
        self.config = WebSocketConfig()
        
        # Connection tracking
        self.connected_at = None
        self.last_ping_sent = None
        self.last_pong_received = None
        self.bytes_sent = 0
        self.bytes_received = 0
        self.frames_sent = 0
        self.frames_received = 0
        
        # Server mode tracking
        self.server = None
        self.clients = {}  # client_id -> (reader, writer, task, ws_transport)
    
    async def connect(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        path: str = "/"
    ) -> None:
        """
        Connect to WebSocket server (instance method).
        
        Args:
            host: Server hostname (uses self.host if not provided)
            port: Server port (uses self.port if not provided)
            path: Request path
        """
        if not self.is_client:
            raise STTTransportError("connect() only for client mode")
        
        host = host or self.host
        port = port or self.port
        
        if not host or not port:
            raise STTTransportError("Host and port required for connection")
        
        try:
            # Open TCP connection with timeout
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.config.connect_timeout
            )
            
            # Perform WebSocket handshake
            await asyncio.wait_for(
                self._client_handshake(host, port, path),
                timeout=self.config.connect_timeout
            )
            
            self.state = WebSocketState.OPEN
            self.connected_at = time.time()
            
            logger.info(f"WebSocket connected to {host}:{port}{path}")
            
        except asyncio.TimeoutError:
            raise STTTransportError(f"Connection timeout after {self.config.connect_timeout}s")
        except Exception as e:
            raise STTTransportError(f"WebSocket connection failed: {e}")
    
    @classmethod
    async def connect_to(
        cls,
        host: str,
        port: int,
        path: str = "/",
        on_frame_received: Optional[Callable[[STTFrame], None]] = None
    ) -> 'WebSocketTransport':
        """
        Class method to connect to WebSocket server.
        
        Args:
            host: Server hostname
            port: Server port
            path: Request path
            on_frame_received: Frame callback
            
        Returns:
            Connected WebSocket transport
        """
        # Create instance
        ws = cls(is_client=True, host=host, port=port, on_frame_received=on_frame_received)
        
        # Connect
        await ws.connect(host, port, path)
        
        return ws
    
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
            hashlib.sha1(key.encode() + WEBSOCKET_GUID, usedforsecurity=False).digest()
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
            
        Raises:
            STTTransportError: If frame too large or transport error
        """
        # Validate frame size
        if len(payload) > self.config.max_frame_size:
            raise STTTransportError(
                f"Frame size {len(payload)} exceeds max {self.config.max_frame_size}"
            )
        
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
        frame_data = header + payload
        self.writer.write(frame_data)
        await self.writer.drain()
        
        # Update statistics
        self.bytes_sent += len(frame_data)
        self.frames_sent += 1
        
        # Track ping timing
        if opcode == WebSocketOpcode.PING:
            self.last_ping_sent = time.time()
    
    async def receive_frames(self) -> None:
        """
        Receive WebSocket frames in loop (client mode).
        
        Processes incoming frames and invokes callbacks.
        Runs until connection closes.
        """
        if not self.is_client:
            raise STTTransportError("receive_frames() only for client mode - server uses _client_receive_loop")
        
        try:
            while self.state == WebSocketState.OPEN:
                # Read WebSocket frame
                opcode, payload = await self._receive_ws_frame()
                
                if opcode == WebSocketOpcode.BINARY:
                    # Invoke message handler for raw data
                    if self.message_handler:
                        if asyncio.iscoroutinefunction(self.message_handler):
                            await self.message_handler(payload, None)
                        else:
                            self.message_handler(payload, None)
                    
                    # Try to parse STT frame
                    if self.on_frame_received:
                        try:
                            frame = STTFrame.from_bytes(payload)
                            if asyncio.iscoroutinefunction(self.on_frame_received):
                                await self.on_frame_received(frame)
                            else:
                                self.on_frame_received(frame)
                        except Exception as e:
                            logger.debug(f"Not an STT frame: {e}")
                
                elif opcode == WebSocketOpcode.TEXT:
                    # Handle text messages
                    if self.message_handler:
                        if asyncio.iscoroutinefunction(self.message_handler):
                            await self.message_handler(payload, None)
                        else:
                            self.message_handler(payload, None)
                
                elif opcode == WebSocketOpcode.PING:
                    # Respond with pong
                    await self._send_ws_frame(WebSocketOpcode.PONG, payload)
                
                elif opcode == WebSocketOpcode.PONG:
                    # Pong received
                    pass
                
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
        
        except asyncio.CancelledError:
            logger.debug("Receive loop cancelled")
            raise
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
        
        # Parse header (FIN bit at header[0] & 0x80 reserved for fragmentation)
        opcode = WebSocketOpcode(header[0] & 0x0F)
        masked = (header[1] & 0x80) != 0
        payload_len = header[1] & 0x7F
        
        # Read extended payload length
        if payload_len == 126:
            payload_len = struct.unpack("!H", await self.reader.readexactly(2))[0]
        elif payload_len == 127:
            payload_len = struct.unpack("!Q", await self.reader.readexactly(8))[0]
        
        # Validate frame size
        if payload_len > self.config.max_frame_size:
            raise STTTransportError(
                f"Frame size {payload_len} exceeds max {self.config.max_frame_size}"
            )
        
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
        
        # Update statistics
        self.bytes_received += 2 + (2 if payload_len >= 126 else 0) + (8 if payload_len >= 65536 else 0) + (4 if masked else 0) + len(payload)
        self.frames_received += 1
        
        # Track pong timing
        if opcode == WebSocketOpcode.PONG:
            self.last_pong_received = time.time()
        
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
        
        # Only send close frame if we have a valid writer
        if self.writer and self.state == WebSocketState.OPEN:
            self.state = WebSocketState.CLOSING
            
            try:
                # Build close payload
                close_payload = struct.pack("!H", code)
                if reason:
                    close_payload += reason.encode('utf-8')
                
                # Send close frame
                await self._send_ws_frame(WebSocketOpcode.CLOSE, close_payload)
                
                # Wait for close response
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.debug(f"Error sending close frame: {e}")
        
        # Close TCP connection
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                logger.debug(f"Error closing writer: {e}")
        
        self.state = WebSocketState.CLOSED
        
        logger.info(f"WebSocket closed (code={code})")
    
    def is_open(self) -> bool:
        """Check if connection is open."""
        return self.state == WebSocketState.OPEN
    
    @property
    def is_running(self) -> bool:
        """Check if transport is running (server mode)."""
        return self.is_server and self.state == WebSocketState.OPEN
    
    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self.state == WebSocketState.OPEN
    
    async def start(self) -> None:
        """Start WebSocket server."""
        if not self.is_server:
            raise STTTransportError("start() only for server mode")
        
        if self.state == WebSocketState.OPEN:
            raise STTTransportError("Server already started")
        
        try:
            # Start TCP server
            self.server = await asyncio.start_server(
                self._handle_client,
                self.host or "127.0.0.1",
                self.port or 0
            )
            
            # Get actual bound port
            if self.server.sockets:
                addr = self.server.sockets[0].getsockname()
                self.host = addr[0]
                self.port = addr[1]
            
            self.state = WebSocketState.OPEN
            logger.info(f"WebSocket server started on {self.host}:{self.port}")
            
        except Exception as e:
            raise STTTransportError(f"Failed to start WebSocket server: {e}")
    
    async def stop(self) -> None:
        """Stop WebSocket server."""
        if not self.is_server:
            raise STTTransportError("stop() only for server mode")
        
        if self.state == WebSocketState.CLOSED:
            return
        
        self.state = WebSocketState.CLOSING
        
        # Close all client connections
        for client_id, (_, _writer, task, client_ws) in list(self.clients.items()):
            try:
                # Cancel receive task
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass  # Task cancellation acknowledged
                
                # Close client connection
                if client_ws.state != WebSocketState.CLOSED:
                    await client_ws.close(1001, "Server shutting down")
                
            except Exception as e:
                logger.debug(f"Error closing client {client_id}: {e}")
        
        self.clients.clear()
        
        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        
        self.state = WebSocketState.CLOSED
        logger.info("WebSocket server stopped")
    
    async def disconnect(self) -> None:
        """Disconnect client."""
        await self.close()
    
    def get_port(self) -> int:
        """Get server port."""
        if not self.is_server:
            raise STTTransportError("get_port() only for server mode")
        return self.port
    
    def set_message_handler(self, handler: Callable) -> None:
        """Set handler for received messages."""
        self.on_frame_received = handler
        self.message_handler = handler
    
    async def send(self, data: bytes) -> None:
        """Send raw bytes."""
        if self.state != WebSocketState.OPEN:
            raise STTTransportError("WebSocket not connected")
        await self._send_ws_frame(WebSocketOpcode.BINARY, data)
    
    async def ping(self, payload: bytes = b"") -> None:
        """
        Send WebSocket ping frame.
        
        Args:
            payload: Optional ping payload (max 125 bytes)
        """
        if len(payload) > 125:
            raise STTTransportError("Ping payload too large (max 125 bytes)")
        
        await self._send_ws_frame(WebSocketOpcode.PING, payload)
    
    async def pong(self, payload: bytes = b"") -> None:
        """
        Send WebSocket pong frame.
        
        Args:
            payload: Optional pong payload (max 125 bytes)
        """
        if len(payload) > 125:
            raise STTTransportError("Pong payload too large (max 125 bytes)")
        
        await self._send_ws_frame(WebSocketOpcode.PONG, payload)
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """
        Handle incoming client connection.
        
        Performs server-side WebSocket handshake and manages client session.
        
        Args:
            reader: Client stream reader
            writer: Client stream writer
        """
        client_addr = writer.get_extra_info('peername')
        client_id = f"{client_addr[0]}:{client_addr[1]}"
        
        try:
            # Perform server-side handshake
            await self._server_handshake(reader, writer)
            
            logger.info(f"WebSocket client connected: {client_id}")
            
            # Create client transport for this connection
            client_ws = WebSocketTransport(
                reader=reader,
                writer=writer,
                is_client=False,
                is_server=True,
                stc_wrapper=self.stc_wrapper
            )
            client_ws.state = WebSocketState.OPEN
            
            # Store client and start receive loop
            receive_task = asyncio.create_task(
                self._client_receive_loop(client_ws, client_id)
            )
            self.clients[client_id] = (reader, writer, receive_task, client_ws)
            
            # Wait for receive task to complete
            await receive_task
            
        except Exception as e:
            logger.error(f"Client handler error {client_id}: {e}")
        finally:
            # Cleanup
            if client_id in self.clients:
                _, _, task, _ = self.clients[client_id]
                if not task.done():
                    task.cancel()
                del self.clients[client_id]
            
            writer.close()
            await writer.wait_closed()
            logger.info(f"WebSocket client disconnected: {client_id}")
    
    async def _server_handshake(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """
        Perform server-side WebSocket handshake.
        
        Args:
            reader: Client stream reader
            writer: Client stream writer
        
        Raises:
            STTTransportError: If handshake fails
        """
        # Read request line
        request_line = await reader.readline()
        if not request_line:
            raise STTTransportError("Empty request")
        
        # Parse request
        parts = request_line.decode().strip().split()
        if len(parts) < 3 or parts[0] != "GET":
            raise STTTransportError(f"Invalid request: {request_line.decode()}")
        
        # Read headers
        headers = {}
        while True:
            line = await reader.readline()
            if line == b"\r\n":
                break
            
            if b":" in line:
                name, value = line.decode().split(":", 1)
                headers[name.strip().lower()] = value.strip()
        
        # Validate WebSocket headers
        upgrade_header = headers.get("upgrade", "")
        if upgrade_header.lower() != "websocket":
            raise STTTransportError(f"Missing Upgrade: websocket header (got: '{upgrade_header}')")
        
        connection_header = headers.get("connection", "")
        # Connection header should contain "Upgrade" (case-insensitive)
        if "upgrade" not in connection_header.lower():
            raise STTTransportError(f"Missing Connection: Upgrade header (got: '{connection_header}')")
        
        ws_key = headers.get("sec-websocket-key")
        if not ws_key:
            raise STTTransportError(f"Missing Sec-WebSocket-Key header (headers: {list(headers.keys())})")
        
        ws_version = headers.get("sec-websocket-version")
        if ws_version != "13":
            raise STTTransportError(f"Unsupported WebSocket version: {ws_version}")
        
        # Generate accept key
        accept_key = base64.b64encode(
            hashlib.sha1((ws_key + WEBSOCKET_GUID.decode()).encode(), usedforsecurity=False).digest()
        ).decode()
        
        # Send handshake response
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n"
            "\r\n"
        )
        
        writer.write(response.encode())
        await writer.drain()
    
    async def _client_receive_loop(self, client_ws: 'WebSocketTransport', client_id: str) -> None:
        """
        Receive loop for individual client.
        
        Args:
            client_ws: WebSocket transport for this client
            client_id: Client identifier
        """
        try:
            while client_ws.state == WebSocketState.OPEN:
                # Read WebSocket frame
                opcode, payload = await client_ws._receive_ws_frame()
                
                if opcode == WebSocketOpcode.BINARY:
                    # Invoke message handler if set
                    if self.message_handler:
                        # Call handler with data and client_id
                        if asyncio.iscoroutinefunction(self.message_handler):
                            await self.message_handler(payload, client_id)
                        else:
                            self.message_handler(payload, client_id)
                    
                    # Try to parse as STT frame if callback set
                    if self.on_frame_received:
                        try:
                            frame = STTFrame.from_bytes(payload)
                            if asyncio.iscoroutinefunction(self.on_frame_received):
                                await self.on_frame_received(frame)
                            else:
                                self.on_frame_received(frame)
                        except Exception as e:
                            logger.debug(f"Not an STT frame: {e}")
                
                elif opcode == WebSocketOpcode.TEXT:
                    # Handle text messages if needed
                    if self.message_handler:
                        text = payload.decode('utf-8')
                        if asyncio.iscoroutinefunction(self.message_handler):
                            await self.message_handler(text.encode(), client_id)
                        else:
                            self.message_handler(text.encode(), client_id)
                
                elif opcode == WebSocketOpcode.PING:
                    # Respond with pong
                    await client_ws._send_ws_frame(WebSocketOpcode.PONG, payload)
                
                elif opcode == WebSocketOpcode.PONG:
                    # Pong received - ignore or update keepalive
                    pass
                
                elif opcode == WebSocketOpcode.CLOSE:
                    # Handle close frame
                    if len(payload) >= 2:
                        close_code = struct.unpack("!H", payload[:2])[0]
                        close_reason = payload[2:].decode('utf-8', errors='ignore')
                        logger.debug(f"Client {client_id} closing: {close_code} {close_reason}")
                    
                    # Send close response
                    await client_ws._send_ws_frame(WebSocketOpcode.CLOSE, payload)
                    client_ws.state = WebSocketState.CLOSED
                    break
        
        except asyncio.CancelledError:
            logger.debug(f"Client {client_id} receive loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Client {client_id} receive error: {e}")
            client_ws.state = WebSocketState.CLOSED
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        uptime = None
        if self.connected_at:
            uptime = time.time() - self.connected_at
        
        # Calculate rates
        send_rate_bps = 0
        receive_rate_bps = 0
        if uptime and uptime > 0:
            send_rate_bps = self.bytes_sent / uptime
            receive_rate_bps = self.bytes_received / uptime
        
        local_addr = None
        remote_addr = None
        
        if self.reader:
            try:
                transport = self.writer.get_extra_info('socket') if self.writer else None
                if transport:
                    local_addr = transport.getsockname()
                    remote_addr = transport.getpeername()
            except Exception as e:
                logger.debug(f"Could not get peer name: {e}")
        
        return {
            'connected': self.state == WebSocketState.OPEN,
            'local_address': local_addr,
            'remote_address': remote_addr,
            'state': self.state.name,
            'is_client': self.is_client,
            'is_server': self.is_server,
            'host': self.host,
            'port': self.port,
            'close_code': self.close_code,
            'close_reason': self.close_reason,
            'connected_at': self.connected_at,
            'uptime': uptime,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'frames_sent': self.frames_sent,
            'frames_received': self.frames_received,
            'last_ping_sent': self.last_ping_sent,
            'last_pong_received': self.last_pong_received,
            'send_rate_bps': send_rate_bps,
            'receive_rate_bps': receive_rate_bps,
            'num_clients': len(self.clients) if self.is_server else None,
        }
    
    def get_address(self) -> Optional[Tuple[str, int]]:
        """Get local address (alias for backward compatibility)."""
        return self.get_local_address()
    
    def get_local_address(self) -> Optional[Tuple[str, int]]:
        """Get local bound address."""
        if self.is_server and self.server:
            return (self.host, self.port)
        elif self.writer:
            try:
                sock = self.writer.get_extra_info('socket')
                if sock:
                    return sock.getsockname()
            except Exception as e:
                logger.debug(f"Could not get socket name: {e}")
        return None
    
    def set_on_message(self, callback: Callable[[bytes], None]) -> None:
        """Set message callback.
        
        Args:
            callback: Function to call when message received
        """
        self.on_message = callback
