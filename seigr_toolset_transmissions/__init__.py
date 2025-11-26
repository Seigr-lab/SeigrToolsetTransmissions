"""
Seigr Toolset Transmissions (STT)

Binary, encrypted, application-agnostic transmission protocol.

Philosophy: Zero semantic assumptions. STT transports/stores/routes bytes.
YOU define what they mean.
"""

__version__ = "0.2.0a0"
__author__ = "Sergi Saldaña-Massó - Seigr Lab"

from .core import STTNode, ReceivedPacket
from .session import STTSession, SessionManager
from .stream import STTStream, StreamManager
from .frame import STTFrame, FrameDispatcher
from .handshake import HandshakeManager, STTHandshake
from .chamber import Chamber
from .crypto import STCWrapper

# Agnostic Primitives (Phase 0)
from .streaming import StreamEncoder, StreamDecoder
from .storage import BinaryStorage
from .endpoints import EndpointManager
from .events import EventEmitter, STTEvents

__all__ = [
    # Core Runtime
    'STTNode',
    'ReceivedPacket',
    # Session/Stream Management
    'STTSession',
    'SessionManager',
    'STTStream',
    'StreamManager',
    # Frame Protocol
    'STTFrame',
    'FrameDispatcher',
    # Handshake
    'HandshakeManager',
    'STTHandshake',
    # Storage
    'Chamber',
    # Crypto
    'STCWrapper',
    # Agnostic Primitives
    'StreamEncoder',          # Binary stream encoder (live/bounded)
    'StreamDecoder',          # Binary stream decoder (out-of-order handling)
    'BinaryStorage',          # Hash-addressed encrypted byte buckets
    'EndpointManager',        # Multi-endpoint routing
    'EventEmitter',           # User-defined event system
    'STTEvents',              # Event registry
]
