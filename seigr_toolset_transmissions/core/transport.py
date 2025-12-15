"""
Transport layer for STT protocol.
Handles TCP/UDP socket communications.
"""

import asyncio
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass

from ..utils.constants import (
    STT_DEFAULT_TCP_PORT,
    STT_BACKLOG,
)
from ..utils.exceptions import STTTransportError
from ..utils.logging import get_logger


logger = get_logger(__name__)


@dataclass
class TransportAddress:
    """Network address for transport."""
    
    host: str
    port: int
    
    def __str__(self) -> str:
        return f"{self.host}:{self.port}"


class TCPTransport:
    """TCP transport implementation."""
    
    def __init__(
        self,
        host: str = "127.0.0.1",  # Default to localhost for security
        port: int = STT_DEFAULT_TCP_PORT,
    ):
        """
        Initialize TCP transport.
        
        Args:
            host: Host address to bind
            port: Port to bind
        """
        self.host = host
        self.port = port
        self.server: Optional[asyncio.Server] = None
        self.connections: set = set()
        self._on_connection: Optional[Callable] = None
    
    async def start(
        self,
        on_connection: Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]],
    ) -> None:
        """
        Start listening for connections.
        
        Args:
            on_connection: Callback for new connections
        """
        self._on_connection = on_connection
        
        try:
            self.server = await asyncio.start_server(
                self._handle_connection,
                self.host,
                self.port,
                backlog=STT_BACKLOG,
            )
            
            addr = self.server.sockets[0].getsockname() if self.server.sockets else None
            logger.info(f"TCP transport listening on {addr}")
            
        except Exception as e:
            raise STTTransportError(f"Failed to start TCP transport: {e}")
    
    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """
        Handle incoming connection.
        
        Args:
            reader: Stream reader
            writer: Stream writer
        """
        peer_addr = writer.get_extra_info('peername')
        logger.info(f"New TCP connection from {peer_addr}")
        
        self.connections.add(writer)
        
        try:
            if self._on_connection:
                await self._on_connection(reader, writer)
        except Exception as e:
            logger.error(f"Error handling connection from {peer_addr}: {e}")
        finally:
            self.connections.discard(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as e:
                logger.debug(f"Error closing writer: {e}")
            logger.info(f"Connection closed: {peer_addr}")
    
    async def connect(
        self,
        host: str,
        port: int,
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """
        Connect to remote peer.
        
        Args:
            host: Remote host
            port: Remote port
            
        Returns:
            Tuple of (reader, writer)
        """
        try:
            reader, writer = await asyncio.open_connection(host, port)
            
            peer_addr = writer.get_extra_info('peername')
            logger.info(f"Connected to {peer_addr}")
            
            self.connections.add(writer)
            
            return reader, writer
            
        except Exception as e:
            raise STTTransportError(f"Failed to connect to {host}:{port}: {e}")
    
    async def stop(self) -> None:
        """Stop transport and close all connections."""
        # Close all active connections
        for writer in list(self.connections):
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as e:
                logger.debug(f"Error closing connection during stop: {e}")
        
        self.connections.clear()
        
        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("TCP transport stopped")
    
    def is_running(self) -> bool:
        """Check if transport is running."""
        return self.server is not None and self.server.is_serving()


class UDPTransport:
    """UDP transport implementation (placeholder for future)."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 9001):  # Default to localhost
        """
        Initialize UDP transport.
        
        Args:
            host: Host address to bind
            port: Port to bind
        """
        self.host = host
        self.port = port
        logger.warning("UDP transport not yet implemented")
    
    async def start(self) -> None:
        """Start UDP transport."""
        raise NotImplementedError("UDP transport not yet implemented")
    
    async def stop(self) -> None:
        """Stop UDP transport."""
        pass


class TransportManager:
    """Manages multiple transport protocols."""
    
    def __init__(self):
        """Initialize transport manager."""
        self.tcp: Optional[TCPTransport] = None
        self.udp: Optional[UDPTransport] = None
    
    async def start_tcp(
        self,
        host: str,
        port: int,
        on_connection: Callable,
    ) -> None:
        """
        Start TCP transport.
        
        Args:
            host: Host to bind
            port: Port to bind
            on_connection: Connection callback
        """
        self.tcp = TCPTransport(host, port)
        await self.tcp.start(on_connection)
    
    async def stop_all(self) -> None:
        """Stop all transports."""
        if self.tcp:
            await self.tcp.stop()
        if self.udp:
            await self.udp.stop()
        
        logger.info("All transports stopped")
