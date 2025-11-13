"""
Seigr Toolset Transmissions (STT)

Binary, encrypted, application-agnostic transmission protocol for the Seigr Ecosystem.
"""

__version__ = "0.1.0"
__author__ = "Seigr Development Team"

from .core import STTNode, ReceivedPacket
from .session import STTSession, SessionManager
from .stream import STTStream, StreamManager
from .frame import STTFrame
from .handshake import HandshakeManager
from .chamber import Chamber
from .bridge import WebSocketBridge

__all__ = [
    # Core
    'STTNode',
    'ReceivedPacket',
    # Session
    'STTSession',
    'SessionManager',
    # Stream
    'STTStream',
    'StreamManager',
    # Frame
    'STTFrame',
    # Handshake
    'HandshakeManager',
    # Chamber
    'Chamber',
    # Bridge
    'WebSocketBridge',
]
