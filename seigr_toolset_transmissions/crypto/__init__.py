"""
Cryptographic operations using Seigr Toolset Crypto (STC).

Modular crypto functions - each dedicated to one purpose:
- streaming: StreamingContext creation for per-stream encryption
- session_keys: Session key derivation and rotation
- node_identity: Node ID generation for DHT

All functions use ephemeral data only - NO personal information.
"""

# For backwards compatibility, provide STCWrapper
from .stc_wrapper import STCWrapper

# New modular API (optional imports - not required for basic usage)
try:
    from . import streaming
    from . import session_keys
    from . import node_identity
    _MODULAR_API_AVAILABLE = True
except ImportError:
    _MODULAR_API_AVAILABLE = False
    streaming = None
    session_keys = None
    node_identity = None

__all__ = [
    'STCWrapper',  # Legacy compatibility
    'streaming',
    'session_keys', 
    'node_identity'
]
