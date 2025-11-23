"""
STT Node - Core runtime for Seigr Toolset Transmissions.
"""

import asyncio
import secrets
from pathlib import Path
from typing import Optional, AsyncIterator, Tuple
from dataclasses import dataclass

from ..crypto.stc_wrapper import STCWrapper
from ..transport import UDPTransport, WebSocketTransport
from ..session import SessionManager, STTSession
from ..handshake import HandshakeManager, STTHandshake
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
        node_seed: bytes,
        shared_seed: bytes,
        host: str = "0.0.0.0",
        port: int = 0,
        chamber_path: Optional[Path] = None,
    ):
        """
        Initialize STT node.
        
        Args:
            node_seed: Seed for STC initialization and node ID generation
            shared_seed: Pre-shared seed for peer authentication
            host: Host address to bind (default: all interfaces)
            port: UDP port to bind (0 = random)
            chamber_path: Path to chamber storage
        """
        self.host = host
        self.port = port
        
        # Initialize STC wrapper
        self.stc = STCWrapper(node_seed)
        
        # Generate node ID from identity
        self.node_id = self.stc.generate_node_id(b"stt_node_identity")
        
        # Initialize chamber with STC
        if chamber_path is None:
            chamber_path = Path.home() / ".seigr" / "chambers" / self.node_id.hex()
        self.chamber = Chamber(chamber_path, self.node_id, self.stc)
        
        # Initialize managers
        self.session_manager = SessionManager(self.node_id, self.stc)
        self.handshake_manager = HandshakeManager(self.node_id, self.stc)
        
        # Transports
        self.udp_transport: Optional[UDPTransport] = None
        self.ws_connections: dict[str, WebSocketTransport] = {}
        
        # Receive queue
        self._recv_queue: asyncio.Queue[ReceivedPacket] = asyncio.Queue()
        
        # Server mode
        self._server_mode = False
        self._accept_connections = False
        
        # Running state
        self._running = False
        self._tasks: list[asyncio.Task] = []
    
    async def start(self, server_mode: bool = False) -> Tuple[str, int]:
        """
        Start the STT node.
        
        Args:
            server_mode: If True, automatically accept incoming connections
        
        Returns:
            Tuple of (local_ip, local_port)
        """
        if self._running:
            logger.warning("Node already running")
            return (self.host, self.port)
        
        self._running = True
        self._server_mode = server_mode
        self._accept_connections = server_mode
        
        # Start UDP transport
        self.udp_transport = UDPTransport(
            on_frame_received=self._handle_frame_received
        )
        local_addr = await self.udp_transport.start()
        
        logger.info(
            f"STT Node started: {self.node_id.hex()[:16]}... "
            f"on {local_addr[0]}:{local_addr[1]} "
            f"(server_mode={server_mode})"
        )
        
        return local_addr
    
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
        
        # Close WebSocket connections
        for ws in self.ws_connections.values():
            await ws.close()
        self.ws_connections.clear()
        
        # Stop UDP transport
        if self.udp_transport:
            await self.udp_transport.stop()
        
        logger.info("STT Node stopped")
    
    async def connect_udp(
        self,
        peer_host: str,
        peer_port: int,
    ) -> STTSession:
        """
        Connect to peer via UDP and establish session.
        
        Args:
            peer_host: Peer's host address
            peer_port: Peer's UDP port
            
        Returns:
            Established STTSession
        """
        if not self.udp_transport:
            raise STTException("Node not started")
        
        try:
            # Initiate handshake (async method returns handshake object)
            peer_addr = (peer_host, peer_port)
            handshake = await self.handshake_manager.initiate_handshake(peer_addr)
            
            # Create and send HELLO
            hello_data = handshake.create_hello()
            await self.udp_transport.send_raw(hello_data, peer_addr)
            
            # Wait for response (simplified - should use proper async waiting)
            await asyncio.sleep(0.1)
            
            # Get session key and peer ID from handshake
            session_key = handshake.session_key
            peer_node_id = handshake.peer_node_id
            
            if not session_key or not peer_node_id:
                raise STTException("Handshake incomplete")
            
            # Create session
            session_id = secrets.token_bytes(8)
            session = await self.session_manager.create_session(
                session_id=session_id,
                peer_node_id=peer_node_id,
                capabilities=0,
            )
            session.session_key = session_key
            session.state = STT_SESSION_STATE_ACTIVE
            session.peer_addr = peer_addr  # Track peer address
            session.transport_type = 'udp'
            
            logger.info(f"UDP session established with {peer_addr}")
            
            return session
            
        except Exception as e:
            raise STTException(f"Failed to connect to {peer_host}:{peer_port}: {e}")
    
    def _handle_frame_received(
        self,
        frame: STTFrame,
        peer_addr: Tuple[str, int]
    ) -> None:
        """
        Handle received frame from UDP transport.
        
        Args:
            frame: Received STT frame
            peer_addr: Peer address (ip, port)
        """
        try:
            # Check if this is a handshake frame
            if frame.frame_type == STT_FRAME_TYPE_HANDSHAKE:
                # Handle handshake
                asyncio.create_task(
                    self._handle_handshake_frame(frame, peer_addr)
                )
            elif frame.frame_type == STT_FRAME_TYPE_DATA:
                # Handle data frame
                asyncio.create_task(
                    self._handle_data_frame(frame, peer_addr)
                )
            else:
                logger.warning(f"Unknown frame type: {frame.frame_type}")
        
        except Exception as e:
            logger.error(f"Frame handling error: {e}")
    
    async def _handle_handshake_frame(
        self,
        frame: STTFrame,
        peer_addr: Tuple[str, int]
    ) -> None:
        """
        Handle handshake frame (HELLO or RESPONSE).
        
        Args:
            frame: Handshake frame containing HELLO or RESPONSE
            peer_addr: Peer address
        """
        try:
            # Check if we accept connections for incoming HELLOs
            handshake = self.handshake_manager.active_handshakes.get(peer_addr)
            
            if not handshake and not self._accept_connections:
                logger.warning(f"Rejecting connection from {peer_addr} (server mode disabled)")
                return
            
            # Use handle_incoming to process HELLO or RESPONSE
            response_data = await self.handshake_manager.handle_incoming(peer_addr, frame.payload)
            
            # Send response if we got one (this is a RESPONSE to their HELLO)
            if response_data:
                await self.udp_transport.send_raw(response_data, peer_addr)
                logger.info(f"Sent handshake response to {peer_addr}")
            
            # Check if handshake completed
            handshake = self.handshake_manager.active_handshakes.get(peer_addr)
            if handshake and handshake.completed:
                # Create session
                session_id = handshake.get_session_id()
                peer_node_id = handshake.peer_node_id
                
                session = await self.session_manager.create_session(
                    session_id=session_id,
                    peer_node_id=peer_node_id,
                    capabilities=0,
                )
                session.session_key = handshake.session_key
                session.state = STT_SESSION_STATE_ACTIVE
                session.peer_addr = peer_addr
                session.transport_type = 'udp'
                
                logger.info(f"Session established with {peer_addr}")
        
        except Exception as e:
            logger.error(f"Handshake error: {e}")
    
    async def _handle_data_frame(
        self,
        frame: STTFrame,
        peer_addr: Tuple[str, int]
    ) -> None:
        """
        Handle data frame.
        
        Args:
            frame: Data frame
            peer_addr: Peer address
        """
        try:
            # Get session
            session = self.session_manager.get_session(frame.session_id)
            
            if not session:
                logger.warning(f"No session for frame: {frame.session_id.hex()}")
                return
            
            # Decrypt if encrypted
            if frame._is_encrypted:
                frame.decrypt_payload(self.stc)
            
            # Add to receive queue
            packet = ReceivedPacket(
                session_id=frame.session_id,
                stream_id=frame.stream_id,
                data=frame.payload
            )
            await self._recv_queue.put(packet)
        
        except Exception as e:
            logger.error(f"Data frame error: {e}")
    
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
        udp_stats = self.udp_transport.get_stats() if self.udp_transport else {}
        
        return {
            'node_id': self.node_id.hex(),
            'running': self._running,
            'server_mode': self._server_mode,
            'accepting_connections': self._accept_connections,
            'udp_transport': udp_stats,
            'websocket_connections': len(self.ws_connections),
            'sessions': self.session_manager.get_stats(),
        }
    
    # Server mode methods
    
    def enable_accept_connections(self):
        """Enable accepting incoming connections (server mode)."""
        self._accept_connections = True
        logger.info("Now accepting incoming connections")
    
    def disable_accept_connections(self):
        """Disable accepting incoming connections."""
        self._accept_connections = False
        logger.info("No longer accepting incoming connections")
    
    # One-to-many streaming methods
    
    async def send_to_all(self, data: bytes, stream_id: int = 0):
        """
        Send data to all active sessions (broadcast).
        
        Args:
            data: Data to broadcast
            stream_id: Stream ID to use
        """
        sessions = self.session_manager.get_all_sessions()
        
        if not sessions:
            logger.warning("No active sessions for broadcast")
            return
        
        logger.info(f"Broadcasting {len(data)} bytes to {len(sessions)} sessions")
        
        # Send to all sessions in parallel
        tasks = []
        for session in sessions:
            tasks.append(self._send_to_session(session, data, stream_id))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_to_sessions(self, session_ids: list[bytes], data: bytes, stream_id: int = 0):
        """
        Send data to specific sessions (multicast).
        
        Args:
            session_ids: List of session IDs to send to
            data: Data to send
            stream_id: Stream ID to use
        """
        if not session_ids:
            logger.warning("No session IDs specified for multicast")
            return
        
        logger.info(f"Multicasting {len(data)} bytes to {len(session_ids)} sessions")
        
        tasks = []
        for session_id in session_ids:
            session = self.session_manager.get_session(session_id)
            if session:
                tasks.append(self._send_to_session(session, data, stream_id))
            else:
                logger.warning(f"Session not found: {session_id.hex()}")
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_to_session(self, session: STTSession, data: bytes, stream_id: int):
        """
        Send data to a single session.
        
        Args:
            session: Session to send to
            data: Data to send
            stream_id: Stream ID
        """
        try:
            # Create frame
            frame = STTFrame(
                session_id=session.session_id,
                stream_id=stream_id,
                payload=data,
                frame_type=STT_FRAME_TYPE_DATA
            )
            
            # Encrypt if session has key
            if session.session_key:
                frame.encrypt_payload(self.stc, session.session_key)
            
            # Send frame
            # Note: Need to track peer address for each session
            # For now, this is a stub - need to add peer_addr to session
            if self.udp_transport and hasattr(session, 'peer_addr'):
                await self.udp_transport.send_frame(frame, session.peer_addr)
                session.record_frame_sent(len(data))
            else:
                logger.warning(f"Cannot send to session {session.session_id.hex()}: no transport address")
        
        except Exception as e:
            logger.error(f"Failed to send to session {session.session_id.hex()}: {e}")
