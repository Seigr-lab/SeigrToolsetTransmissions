"""
Seigr Toolset Transmissions (STT)

Binary, encrypted, application-agnostic transmission protocol.

Philosophy: Zero semantic assumptions. STT transports bytes securely.
YOU define what they mean. YOU provide storage if needed.

STT is a TRANSMISSION protocol - it moves encrypted bytes between nodes.
Storage is NOT part of STT - applications provide their own via StorageProvider.
"""

__version__ = "0.2.0a0"
__author__ = "Sergi Saldaña-Massó - Seigr Lab"

from .core import STTNode, ReceivedPacket
from .session import STTSession, SessionManager
from .stream import STTStream, StreamManager
from .frame import STTFrame, FrameDispatcher
from .handshake import HandshakeManager, STTHandshake
from .crypto import STCWrapper

# Agnostic Primitives
from .streaming import StreamEncoder, StreamDecoder
from .endpoints import EndpointManager
from .events import EventEmitter, STTEvents

# Pluggable Storage Interface (applications implement their own)
from .storage import StorageProvider, InMemoryStorage

# NAT Coordination (Pluggable)
from .nat import NATCoordinator, ManualNATCoordinator, RelayNATCoordinator, NATStrategy

# Performance Profiling
from .utils.profiler import PerformanceProfiler, PerformanceSnapshot

# DEPRECATED - will be removed in future versions
# Storage is NOT part of transmission - use StorageProvider instead
from .storage import BinaryStorage  # DEPRECATED
from .chamber import Chamber        # DEPRECATED

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
    # Crypto
    'STCWrapper',
    # Agnostic Primitives
    'StreamEncoder',          # Binary stream encoder (live/bounded)
    'StreamDecoder',          # Binary stream decoder (out-of-order handling)
    'EndpointManager',        # Multi-endpoint routing
    'EventEmitter',           # User-defined event system
    'STTEvents',              # Event registry
    # Pluggable Storage Interface
    'StorageProvider',        # Abstract interface - applications implement
    'InMemoryStorage',        # Simple in-memory implementation for testing
    # NAT Coordination
    'NATCoordinator',         # Abstract NAT coordinator interface
    'ManualNATCoordinator',   # Manual peer configuration (default)
    'RelayNATCoordinator',    # Relay-based NAT traversal
    'NATStrategy',            # NAT strategy enumeration
    # Performance
    'PerformanceProfiler',    # Performance profiling utility
    'PerformanceSnapshot',    # Performance metrics snapshot
    # DEPRECATED - will be removed
    'BinaryStorage',          # DEPRECATED: Use StorageProvider
    'Chamber',                # DEPRECATED: Use StorageProvider
]
