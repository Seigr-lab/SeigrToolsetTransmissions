"""
STT Node - Core runtime for Seigr Toolset Transmissions.
"""

import asyncio
import secrets
from pathlib import Path
from typing import Optional, AsyncIterator
from dataclasses import dataclass

from .transport import TCPTransport, TransportAddress
from ..session import SessionManager, STTSession
from ..handshake import HandshakeManager, HandshakeHello
from ..frame import STTFrame
from ..chamber import Chamber
from ..utils.constants import (
    STT_DEFAULT_TCP_PORT,
    STT_FRAME_TYPE_HANDSHAKE,
    STT_FRAME_TYPE_DATA,
    STT_HANDSHAKE_HELLO,
    STT_SESSION_STATE_ACTIVE,
)
from ..utils.exceptions import STTException, STTSessionError
from ..utils.logging import get_logger


logger = get_logger(__name__)


@dataclass
class ReceivedPacket:
    """Represents a received data packet."""
    
    session_id: bytes
    stream_id: int
    data: bytes


class STTNode:
    """
    Main STT node providing async API for secure binary communications.
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = STT_DEFAULT_TCP_PORT,
        chamber_path: Optional[Path] = None,
        node_id: Optional[bytes] = None,
    ):
        """
        Initialize STT node.
        
        Args:
            host: Host address to bind
            port: Port to listen on
            chamber_path: Path to chamber storage
            node_id: Node identifier (generated if not provided)
        """
        self.host = host
        self.port = port
        
        # Generate or use provided node ID
        self.node_id = node_id or secrets.token_bytes(32)
        
        # Initialize chamber
        if chamber_path is None:
            chamber_path = Path.home() / ".seigr" / "chambers" / self.node_id.hex()
        self.chamber = Chamber(chamber_path, self.node_id)
        
        # Initialize managers
        self.session_manager = SessionManager(self.node_id)
        self.handshake_manager = HandshakeManager(self.node_id)
        
        # Transport
        self.transport: Optional[TCPTransport] = None
        
        # Receive queue
        self._recv_queue: asyncio.Queue[ReceivedPacket] = asyncio.Queue()
        
        # Running state
        self._running = False
        self._tasks: list[asyncio.Task] = []
    
    async def start(self) -> None:
        """Start the STT node."""
        if self._running:
            logger.warning("Node already running")
            return
        
        self._running = True
        
        # Start TCP transport
        self.transport = TCPTransport(self.host, self.port)
        await self.transport.start(self._handle_connection)
        
        logger.info(
            f"STT Node started: {self.node_id.hex()[:16]}... "
            f"on {self.host}:{self.port}"
        )
    
    async def stop(self) -> None:
        """Stop the STT node."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel tasks
        for task in self._tasks:
            task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self._tasks.clear()
        
        # Close all sessions
        await self.session_manager.close_all_sessions()
        
        # Stop transport
        if self.transport:
            await self.transport.stop()
        
        logger.info("STT Node stopped")
    
    async def connect(
        self,
        peer_host: str,
        peer_port: int,
    ) -> STTSession:
        """
        Connect to a remote peer and establish session.
        
        Args:
            peer_host: Peer's host address
            peer_port: Peer's port
            
        Returns:
            Established STTSession
        """
        if not self.transport:
            raise STTException("Node not started")
        
        try:
            # Connect to peer
            reader, writer = await self.transport.connect(peer_host, peer_port)
            
            # Perform handshake
            session = await self._perform_handshake_client(reader, writer)
            
            # Start handling connection
            task = asyncio.create_task(
                self._handle_session_communication(reader, writer, session)
            )
            self._tasks.append(task)
            
            return session
            
        except Exception as e:
            raise STTException(f"Failed to connect to {peer_host}:{peer_port}: {e}")
    
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
        try:
            # Perform handshake as server
            session = await self._perform_handshake_server(reader, writer)
            
            # Handle session communication
            await self._handle_session_communication(reader, writer, session)
            
        except Exception as e:
            logger.error(f"Connection handling failed: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
    
    async def _perform_handshake_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> STTSession:
        """
        Perform handshake as client.
        
        Returns:
            Established session
        """
        # Generate ephemeral key (placeholder - use STC in production)
        ephemeral_key = secrets.token_bytes(32)
        
        # Create and send HELLO
        hello = self.handshake_manager.create_hello(ephemeral_key)
        hello_data = hello.to_bytes()
        
        # Send HELLO in a frame
        hello_frame = STTFrame.create_frame(
            frame_type=STT_FRAME_TYPE_HANDSHAKE,
            session_id=b'\x00' * 8,
            sequence=0,
            payload=bytes([STT_HANDSHAKE_HELLO]) + hello_data,
        )
        
        writer.write(hello_frame.to_bytes())
        await writer.drain()
        
        logger.debug("Sent HELLO to peer")
        
        # Receive HELLO_RESP
        # Simplified: In production, handle proper frame reception
        response_data = await reader.read(4096)
        
        # Derive session ID and create session
        # Placeholder implementation
        session_id = secrets.token_bytes(8)
        
        session = await self.session_manager.create_session(
            session_id=session_id,
            peer_node_id=secrets.token_bytes(32),  # Should be from HELLO_RESP
            capabilities=self.handshake_manager.capabilities,
        )
        
        session.state = STT_SESSION_STATE_ACTIVE
        
        logger.info(f"Handshake completed: session {session_id.hex()}")
        
        return session
    
    async def _perform_handshake_server(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> STTSession:
        """
        Perform handshake as server.
        
        Returns:
            Established session
        """
        # Receive HELLO
        # Simplified implementation
        hello_data = await reader.read(4096)
        
        # Generate session
        session_id = secrets.token_bytes(8)
        
        session = await self.session_manager.create_session(
            session_id=session_id,
            peer_node_id=secrets.token_bytes(32),
            capabilities=self.handshake_manager.capabilities,
        )
        
        session.state = STT_SESSION_STATE_ACTIVE
        
        logger.info(f"Handshake completed: session {session_id.hex()}")
        
        return session
    
    async def _handle_session_communication(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        session: STTSession,
    ) -> None:
        """Handle ongoing session communication."""
        try:
            while self._running and session.is_active():
                # Read frames and process
                data = await reader.read(4096)
                
                if not data:
                    break
                
                # Process frames (simplified)
                # In production: proper frame parsing and handling
                
                await asyncio.sleep(0.1)  # Prevent tight loop
                
        except Exception as e:
            logger.error(f"Session communication error: {e}")
        finally:
            await session.close()
    
    async def receive(self) -> AsyncIterator[ReceivedPacket]:
        """
        Receive data from any session/stream.
        
        Yields:
            ReceivedPacket instances
        """
        while self._running:
            try:
                packet = await asyncio.wait_for(
                    self._recv_queue.get(),
                    timeout=1.0
                )
                yield packet
            except asyncio.TimeoutError:
                continue
    
    def get_stats(self) -> dict:
        """Get node statistics."""
        return {
            'node_id': self.node_id.hex(),
            'host': self.host,
            'port': self.port,
            'running': self._running,
            'sessions': self.session_manager.get_stats(),
        }
