"""
Pluggable storage interface for STT.

STT is a transmission protocol - it doesn't require storage.
Applications that need persistence can implement this interface.

Example implementations:
- ST Syndicate (Seigr's storage layer)
- Custom database backends
- Cloud storage adapters
- In-memory caches
"""

from typing import Protocol, Optional, List, Dict, runtime_checkable


@runtime_checkable
class StorageProvider(Protocol):
    """
    Abstract storage interface for applications.
    
    STT accepts this optionally for features that may benefit from persistence
    (e.g., session resumption tokens, cached keys).
    
    Applications implement this to provide their own storage strategy.
    STT makes NO assumptions about:
    - Where data is stored (disk, cloud, memory, database)
    - How data is organized (user decides)
    - Data format (opaque bytes)
    - Encryption (user handles if needed)
    
    Example:
        class MySyndicateStorage:
            async def store(self, key: bytes, data: bytes) -> None:
                # Store in ST Syndicate
                ...
            
            async def retrieve(self, key: bytes) -> Optional[bytes]:
                # Retrieve from ST Syndicate
                ...
        
        node = STTNode(
            node_seed=seed,
            storage=MySyndicateStorage()
        )
    """
    
    async def store(self, key: bytes, data: bytes) -> None:
        """
        Store opaque bytes at key.
        
        Args:
            key: Unique key (user defines format - could be hash, UUID, etc.)
            data: Opaque bytes (STT doesn't interpret)
        
        Raises:
            Exception: Implementation-defined errors
        """
        raise NotImplementedError
    
    async def retrieve(self, key: bytes) -> Optional[bytes]:
        """
        Retrieve bytes by key.
        
        Args:
            key: Key to retrieve
        
        Returns:
            Data bytes if found, None if not found
        
        Raises:
            Exception: Implementation-defined errors (NOT for missing keys)
        """
        raise NotImplementedError
    
    async def exists(self, key: bytes) -> bool:
        """
        Check if key exists.
        
        Args:
            key: Key to check
        
        Returns:
            True if exists, False otherwise
        """
        raise NotImplementedError
    
    async def delete(self, key: bytes) -> None:
        """
        Delete data at key.
        
        Args:
            key: Key to delete
        
        Raises:
            Exception: Implementation-defined errors
        
        Note:
            Should not raise if key doesn't exist (idempotent delete)
        """
        raise NotImplementedError
    
    async def list_keys(self) -> List[bytes]:
        """
        List all keys.
        
        Returns:
            List of all keys in storage
        
        Note:
            For large storage, implementations may want to add
            pagination or filtering - extend the interface as needed.
        """
        raise NotImplementedError


class InMemoryStorage:
    """
    Simple in-memory storage implementation.
    
    Useful for:
    - Testing
    - Ephemeral sessions
    - Development
    
    NOT for production persistence (data lost on restart).
    """
    
    def __init__(self):
        """Initialize empty in-memory storage."""
        self._data: Dict[bytes, bytes] = {}
    
    async def store(self, key: bytes, data: bytes) -> None:
        """Store data in memory."""
        self._data[key] = data
    
    async def retrieve(self, key: bytes) -> Optional[bytes]:
        """Retrieve data from memory."""
        return self._data.get(key)
    
    async def exists(self, key: bytes) -> bool:
        """Check if key exists in memory."""
        return key in self._data
    
    async def delete(self, key: bytes) -> None:
        """Delete from memory (idempotent)."""
        self._data.pop(key, None)
    
    async def list_keys(self) -> List[bytes]:
        """List all keys in memory."""
        return list(self._data.keys())
    
    def clear(self) -> None:
        """Clear all data (for testing)."""
        self._data.clear()
    
    def __len__(self) -> int:
        """Get number of stored items."""
        return len(self._data)
