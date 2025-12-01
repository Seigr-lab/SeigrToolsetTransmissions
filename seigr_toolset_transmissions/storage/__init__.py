"""
Storage module - Pluggable storage interface.

STT is a transmission protocol - it doesn't require storage.
Applications that need persistence implement the StorageProvider interface.

The StorageProvider protocol allows applications to plug in their own storage:
- ST Syndicate (Seigr's storage layer)
- Custom database backends
- Cloud storage adapters
- In-memory caches

BinaryStorage is DEPRECATED and will be removed in a future version.
Use StorageProvider interface instead.
"""

import warnings
from .provider import StorageProvider, InMemoryStorage

# Deprecated - will be removed
def _get_binary_storage():
    """Lazy import for deprecated BinaryStorage."""
    warnings.warn(
        "BinaryStorage is deprecated. STT is a transmission protocol - "
        "applications should implement StorageProvider for their own storage needs. "
        "BinaryStorage will be removed in a future version.",
        DeprecationWarning,
        stacklevel=3
    )
    from .binary_storage import BinaryStorage
    return BinaryStorage

# For backwards compatibility, but deprecated
class _DeprecatedBinaryStorageImport:
    """Wrapper to show deprecation warning on import."""
    def __getattr__(self, name):
        BinaryStorage = _get_binary_storage()
        return getattr(BinaryStorage, name)
    
    def __call__(self, *args, **kwargs):
        BinaryStorage = _get_binary_storage()
        return BinaryStorage(*args, **kwargs)

BinaryStorage = _DeprecatedBinaryStorageImport()

__all__ = [
    'StorageProvider',      # Primary interface for applications
    'InMemoryStorage',      # Simple in-memory implementation for testing
    'BinaryStorage',        # DEPRECATED - will be removed
]
