"""
WebSocket bridge for browser-compatible STT connections.
Acts as a transparent binary tunnel between WebSocket and native STT.
"""

import asyncio
from typing import Optional

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketServerProtocol = object

from ..core.transport import TCPTransport
from ..utils.constants import STT_DEFAULT_WS_PORT, STT_BUFFER_SIZE
from ..utils.exceptions import STTTransportError
from ..utils.logging import get_logger


logger = get_logger(__name__)


class WebSocketBridge:
    """
    Transparent binary tunnel between WebSocket clients and STT backend.
    
    The bridge performs NO decryption or inspection - it simply forwards
    binary frames between WebSocket and native STT protocol.
    """
    
    def __init__(
        self,
        ws_host: str = "0.0.0.0",
        ws_port: int = STT_DEFAULT_WS_PORT,
        backend_host: str = "127.0.0.1",
        backend_port: int = 9000,
    ):
        """
        Initialize WebSocket bridge.
        
        Args:
            ws_host: WebSocket server host
            ws_port: WebSocket server port
            backend_host: STT backend host
            backend_port: STT backend port
        """
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError(
                "websockets package required for WebSocket bridge. "
                "Install with: pip install seigr-toolset-transmissions[websocket]"
            )
        
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.backend_host = backend_host
        self.backend_port = backend_port
        
        self.server = None
        self._running = False
        self.active_connections = 0
    
    async def start(self) -> None:
        """Start the WebSocket bridge server."""
        if self._running:
            logger.warning("Bridge already running")
            return
        
        self._running = True
        
        try:
            self.server = await websockets.serve(
                self._handle_websocket,
                self.ws_host,
                self.ws_port,
            )
            
            logger.info(
                f"WebSocket bridge started on ws://{self.ws_host}:{self.ws_port} -> "
                f"STT backend {self.backend_host}:{self.backend_port}"
            )
            
        except Exception as e:
            self._running = False
            raise STTTransportError(f"Failed to start WebSocket bridge: {e}")
    
    async def stop(self) -> None:
        """Stop the WebSocket bridge server."""
        if not self._running:
            return
        
        self._running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("WebSocket bridge stopped")
    
    async def _handle_websocket(self, websocket: 'WebSocketServerProtocol') -> None:
        """
        Handle WebSocket connection by creating a tunnel to STT backend.
        
        Args:
            websocket: WebSocket connection
        """
        self.active_connections += 1
        remote_addr = websocket.remote_address
        
        logger.info(f"New WebSocket connection from {remote_addr}")
        
        backend_reader = None
        backend_writer = None
        
        try:
            # Connect to STT backend
            backend_reader, backend_writer = await asyncio.open_connection(
                self.backend_host,
                self.backend_port,
            )
            
            logger.debug(f"Connected to backend for {remote_addr}")
            
            # Create bidirectional tunnel
            await asyncio.gather(
                self._ws_to_backend(websocket, backend_writer),
                self._backend_to_ws(backend_reader, websocket),
                return_exceptions=True,
            )
            
        except Exception as e:
            logger.error(f"Bridge error for {remote_addr}: {e}")
        
        finally:
            # Cleanup
            if backend_writer:
                try:
                    backend_writer.close()
                    await backend_writer.wait_closed()
                except Exception:
                    pass
            
            try:
                await websocket.close()
            except Exception:
                pass
            
            self.active_connections -= 1
            logger.info(f"WebSocket connection closed: {remote_addr}")
    
    async def _ws_to_backend(
        self,
        websocket: 'WebSocketServerProtocol',
        backend_writer: asyncio.StreamWriter,
    ) -> None:
        """
        Forward data from WebSocket to backend.
        
        Args:
            websocket: WebSocket connection
            backend_writer: Backend stream writer
        """
        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    # Forward binary data to backend
                    backend_writer.write(message)
                    await backend_writer.drain()
                else:
                    logger.warning("Received non-binary WebSocket message, ignoring")
        
        except Exception as e:
            logger.debug(f"WS->Backend tunnel closed: {e}")
    
    async def _backend_to_ws(
        self,
        backend_reader: asyncio.StreamReader,
        websocket: 'WebSocketServerProtocol',
    ) -> None:
        """
        Forward data from backend to WebSocket.
        
        Args:
            backend_reader: Backend stream reader
            websocket: WebSocket connection
        """
        try:
            while True:
                # Read from backend
                data = await backend_reader.read(STT_BUFFER_SIZE)
                
                if not data:
                    break
                
                # Forward to WebSocket
                await websocket.send(data)
        
        except Exception as e:
            logger.debug(f"Backend->WS tunnel closed: {e}")
    
    def get_stats(self) -> dict:
        """Get bridge statistics."""
        return {
            'ws_address': f"ws://{self.ws_host}:{self.ws_port}",
            'backend_address': f"{self.backend_host}:{self.backend_port}",
            'running': self._running,
            'active_connections': self.active_connections,
        }
