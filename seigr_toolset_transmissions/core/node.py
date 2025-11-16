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
        
        # Running state
        self._running = False
        self._tasks: list[asyncio.Task] = []
    
    async def start(self) -> Tuple[str, int]:
        """
        Start the STT node.
        
        Returns:
            Tuple of (local_ip, local_port)
        """
        if self._running:
            logger.warning("Node already running")
            return (self.host, self.port)
        
        self._running = True
        
        # Start UDP transport
        self.udp_transport = UDPTransport(
            on_frame_received=self._handle_frame_received
        )
        local_addr = await self.udp_transport.start()
        
        logger.info(
            f"STT Node started: {self.node_id.hex()[:16]}... "
            f"on {local_addr[0]}:{local_addr[1]}"
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
            # Create handshake
            peer_addr = f"{peer_host}:{peer_port}"
            handshake = self.handshake_manager.create_handshake(peer_addr)
            
            # Initiate handshake
            hello_bytes = handshake.initiate_handshake()
            
            # Send HELLO via UDP
            await self.udp_transport.send_raw(hello_bytes, (peer_host, peer_port))
            
            # Wait for response (simplified - should use proper async waiting)
            await asyncio.sleep(0.1)
            
            # Get session key and peer ID from handshake
            session_key = handshake.get_session_key()
            peer_node_id = handshake.get_peer_node_id()
            
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
        Handle handshake frame.
        
        Args:
            frame: Handshake frame
            peer_addr: Peer address
        """
        try:
            peer_key = f"{peer_addr[0]}:{peer_addr[1]}"
            handshake = self.handshake_manager.get_handshake(peer_key)
            
            if not handshake:
                # New handshake as server
                handshake = self.handshake_manager.create_handshake(peer_key)
                response = handshake.handle_hello(frame.payload)
                
                # Send response
                await self.udp_transport.send_raw(response, peer_addr)
            else:
                # Complete handshake
                session_key, peer_node_id = handshake.handle_response(frame.payload)
                
                # Create session
                session_id = secrets.token_bytes(8)
                session = await self.session_manager.create_session(
                    session_id=session_id,
                    peer_node_id=peer_node_id,
                    capabilities=0,
                )
                session.session_key = session_key
                session.state = STT_SESSION_STATE_ACTIVE
                
                logger.info(f"Session established with {peer_key}")
        
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
            'udp_transport': udp_stats,
            'websocket_connections': len(self.ws_connections),
            'sessions': self.session_manager.get_stats(),
        }
