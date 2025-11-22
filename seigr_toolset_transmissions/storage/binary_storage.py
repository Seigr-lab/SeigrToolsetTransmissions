"""
Agnostic binary storage - pure byte buckets with NO file semantics.

Stores opaque bytes by STC-hash address.
NO assumptions about what bytes represent.
"""

import asyncio
from pathlib import Path
from typing import Optional, List, Dict
import time

from ..crypto.stc_wrapper import STCWrapper
from ..utils.exceptions import STTStorageError


class BinaryStorage:
    """
    Pure byte bucket storage.
    
    NO assumptions about:
    - What bytes represent (files? blocks? messages? user decides)
    - Data structure (user defines)
    - Semantics (user interprets)
    
    Provides:
    - Hash-based addressing (SHA3-256)
    - Secure storage (STC encryption)
    - Integrity verification (hash validation)
    """
    
    def __init__(
        self,
        storage_path: Path,
        stc_wrapper: STCWrapper,
        max_size_bytes: Optional[int] = None
    ):
        """
        Initialize binary storage.
        
        Args:
            storage_path: Directory for storing encrypted bytes
            stc_wrapper: STC wrapper for cryptography
            max_size_bytes: Optional storage limit (None = unlimited)
        """
        self.storage_path = Path(storage_path)
        self.stc_wrapper = stc_wrapper
        self.max_size_bytes = max_size_bytes
        
        # Create storage directory
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Storage index (address -> metadata)
        self._index: Dict[bytes, dict] = {}
        self._current_size = 0
        self._lock = asyncio.Lock()
        
        # Load existing index
        self._load_index()
    
    async def put(self, data: bytes) -> bytes:
        """
        Store opaque bytes, return hash-based address.
        
        Args:
            data: Arbitrary bytes (could be anything - user decides)
        
        Returns:
            address: SHA3-256 hash of data (32 bytes, deterministic)
        
        Raises:
            STTStorageError: If storage full or operation fails
        
        Example:
            # Store anything
            address = await storage.put(b"arbitrary binary data")
            address = await storage.put(video_frame)
            address = await storage.put(sensor_reading)
        """
        if not isinstance(data, bytes):
            raise STTStorageError("Data must be bytes")
        
        async with self._lock:
            # Generate hash-based address (deterministic for deduplication)
            # Use SHA3-256 for deterministic hash-based addressing
            import hashlib
            address = hashlib.sha3_256(data).digest()  # 32 bytes, deterministic
            
            # Check if already exists
            if address in self._index:
                return address  # Deduplication
            
            # Check storage limit
            if self.max_size_bytes is not None:
                if self._current_size + len(data) > self.max_size_bytes:
                    # Evict oldest entries
                    await self._evict_lru(len(data))
            
            # Encrypt data with STC
            # Create a session for storage encryption
            storage_session = b"storage_" + address[:8]
            stream_context = self.stc_wrapper.create_stream_context(
                session_id=storage_session,
                stream_id=0
            )
            
            # Encrypt using streaming context
            header, encrypted = stream_context.encrypt_chunk(data)
            
            # Store encrypted bytes with header
            encrypted_with_header = header.to_bytes() + encrypted
            
            # Store encrypted bytes
            address_path = self._get_address_path(address)
            address_path.parent.mkdir(parents=True, exist_ok=True)
            
            address_path.write_bytes(encrypted_with_header)
            
            # Update index
            self._index[address] = {
                'size': len(data),
                'encrypted_size': len(encrypted_with_header),
                'timestamp': time.time(),
                'access_time': time.time()
            }
            self._current_size += len(data)
            
            # Persist index
            self._save_index()
            
            return address
    
    async def get(self, address: bytes) -> bytes:
        """
        Retrieve bytes by hash-based address.
        
        Args:
            address: SHA3-256 hash address (32 bytes)
        
        Returns:
            data: Decrypted bytes (opaque - user interprets)
        
        Raises:
            STTStorageError: If address not found or decryption fails
        
        Example:
            data = await storage.get(address)
            # User interprets data (video? message? block?)
        """
        if not isinstance(address, bytes):
            raise STTStorageError("Address must be bytes")
        
        async with self._lock:
            # Check index
            if address not in self._index:
                raise STTStorageError(f"Address not found: {address.hex()[:16]}...")
            
            # Read encrypted bytes
            address_path = self._get_address_path(address)
            if not address_path.exists():
                raise STTStorageError(f"Storage file missing for {address.hex()[:16]}...")
            
            encrypted_with_header = address_path.read_bytes()
            
            # Parse header and decrypt
            from interfaces.api.streaming_context import ChunkHeader
            
            # Extract header (16 bytes) and encrypted data
            header_bytes = encrypted_with_header[:16]
            encrypted = encrypted_with_header[16:]
            
            # Recreate stream context
            storage_session = b"storage_" + address[:8]
            stream_context = self.stc_wrapper.create_stream_context(
                session_id=storage_session,
                stream_id=0
            )
            
            # Decrypt
            try:
                header = ChunkHeader.from_bytes(header_bytes)
                decrypted = stream_context.decrypt_chunk(header, encrypted)
            except Exception as e:
                raise STTStorageError(f"Decryption failed: {e}")
            
            # Verify integrity (deterministic hash)
            import hashlib
            verified_address = hashlib.sha3_256(decrypted).digest()
            
            if verified_address != address:
                raise STTStorageError(f"Integrity check failed for {address.hex()[:16]}...")
            
            # Update access time
            self._index[address]['access_time'] = time.time()
            self._save_index()
            
            return decrypted
    
    async def remove(self, address: bytes) -> None:
        """
        Remove bytes by address.
        
        Args:
            address: STC hash address to remove
        
        Raises:
            STTStorageError: If address not found
        """
        async with self._lock:
            if address not in self._index:
                raise STTStorageError(f"Address not found: {address.hex()[:16]}...")
            
            # Delete file
            address_path = self._get_address_path(address)
            if address_path.exists():
                address_path.unlink()
            
            # Update index
            size = self._index[address]['size']
            del self._index[address]
            self._current_size -= size
            
            self._save_index()
    
    async def list_addresses(self) -> List[bytes]:
        """
        List all stored addresses.
        
        Returns:
            List of addresses (each 32 bytes)
        """
        async with self._lock:
            return list(self._index.keys())
    
    async def exists(self, address: bytes) -> bool:
        """
        Check if address exists in storage.
        
        Args:
            address: Address to check
        
        Returns:
            True if exists, False otherwise
        """
        return address in self._index
    
    def get_stats(self) -> dict:
        """
        Get storage statistics.
        
        Returns:
            dict with total_addresses, total_bytes, max_size
        """
        return {
            'total_addresses': len(self._index),
            'total_bytes': self._current_size,
            'max_size_bytes': self.max_size_bytes,
            'utilization': self._current_size / self.max_size_bytes if self.max_size_bytes else 0.0
        }
    
    async def _evict_lru(self, needed_bytes: int) -> None:
        """
        Evict least-recently-used entries to make space.
        
        Args:
            needed_bytes: Space needed
        """
        # Sort by access time (oldest first)
        sorted_addresses = sorted(
            self._index.items(),
            key=lambda x: x[1]['access_time']
        )
        
        freed_bytes = 0
        for address, metadata in sorted_addresses:
            if freed_bytes >= needed_bytes:
                break
            
            await self.remove(address)
            freed_bytes += metadata['size']
    
    def _get_address_path(self, address: bytes) -> Path:
        """
        Get filesystem path for address.
        
        Uses first 2 bytes for directory sharding (256^2 = 65536 dirs max).
        """
        addr_hex = address.hex()
        # Shard: first 2 bytes = 4 hex chars
        shard = addr_hex[:4]
        return self.storage_path / shard / addr_hex
    
    def _load_index(self) -> None:
        """Load storage index from disk."""
        index_path = self.storage_path / 'index.bin'
        if not index_path.exists():
            return
        
        # TODO: Implement index persistence
        # For now, rebuild from filesystem
        pass
    
    def _save_index(self) -> None:
        """Save storage index to disk."""
        # TODO: Implement index persistence
        pass
