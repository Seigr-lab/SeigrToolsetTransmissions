"""
NAT traversal coordination interfaces and implementations.

Pluggable NAT coordination allows applications to choose their
network topology strategy without coupling to STT core.
"""

from .coordinator import NATCoordinator, NATStrategy, NATCoordinationError
from .manual import ManualNATCoordinator
from .relay import RelayNATCoordinator
from .relay_server import RelayServer

__all__ = [
    'NATCoordinator',
    'NATStrategy',
    'NATCoordinationError',
    'ManualNATCoordinator',
    'RelayNATCoordinator',
    'RelayServer',
]
