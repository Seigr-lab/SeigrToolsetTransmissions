"""
STC Wrapper - Single point of truth for all cryptographic operations.

This module centralizes all interactions with Seigr Toolset Crypto (STC),
providing a consistent interface for encryption, hashing, and key derivation
throughout the STT protocol.

All cryptographic operations MUST go through this wrapper - no direct
hashlib, secrets, or other crypto library usage is permitted.
"""

import time
from typing import Dict, Optional, Tuple, Union
import sys

# Import STC - handle path issues
try:
    from interfaces.api import stc_api
except ImportError:
    # Add site-packages to path if needed
    import site
    sys.path.extend(site.getsitepackages())
    from interfaces.api import stc_api


class STCWrapper:
    """
    Centralized wrapper for all STC cryptographic operations.
    
    Provides:
    - Probabilistic hashing (PHE) for node IDs and content addressing
    - Key derivation (CKE) for session keys and subkeys
    - Frame encryption with AEAD-like properties via associated data
    - Stream context creation for isolated per-stream encryption
    """
    
    def __init__(self, node_seed: Union[str, bytes, int]):
        """
        Initialize STC wrapper with node-level seed.
        
        Args:
            node_seed: Seed for node-level STC context. Should be unique
                      per node and derived from node identity.
        """
        self.node_seed = node_seed
        self.context = stc_api.initialize(
            seed=node_seed,
            lattice_size=128,        # Balanced performance
            depth=6,                  # Balanced security
            morph_interval=100,       # Morphing frequency
            adaptive_difficulty='balanced',
            adaptive_morphing=True
        )
        
        # Cache for stream contexts to avoid recreation
        self._stream_contexts = {}
    
    def hash_data(self, data: bytes, context: Optional[Dict] = None) -> bytes:
        """
        Generate probabilistic hash using STC PHE.
        
        Args:
            data: Data to hash
            context: Optional context data (affects hash output)
            
        Returns:
            Hash bytes (context-dependent, NOT SHA-256)
        """
        return self.context.hash(data, context_data=context)
    
    def generate_node_id(self, identity: bytes) -> bytes:
        """
        Generate node ID from identity using STC hash.
        
        Args:
            identity: Node identity (e.g., public key, unique identifier)
            
        Returns:
            Node ID (32 bytes for DHT XOR distance calculations)
        """
        return self.hash_data(identity, {'purpose': 'node_id'})
    
    def hash_content(self, content: bytes) -> bytes:
        """
        Generate content ID for content-addressed storage.
        
        Args:
            content: Content data to hash
            
        Returns:
            Content ID (STC hash, NOT SHA-256)
        """
        return self.hash_data(content, {'purpose': 'content_id'})
    
    def derive_session_key(self, handshake_data: Dict) -> bytes:
        """
        Derive session key from handshake context.
        
        Args:
            handshake_data: Dictionary containing handshake parameters
                          (e.g., nonces, timestamps, ephemeral data)
            
        Returns:
            32-byte session key
        """
        return self.context.derive_key(
            context_data=handshake_data,
            key_size=32
        )
    
    def rotate_session_key(self, current_key: bytes, rotation_nonce: bytes) -> bytes:
        """
        Derive new session key for key rotation.
        
        Args:
            current_key: Current session key
            rotation_nonce: Fresh nonce for rotation
            
        Returns:
            New 32-byte session key
        """
        return self.context.derive_key(
            context_data={
                'current_key': current_key.hex(),
                'rotation_nonce': rotation_nonce.hex(),
                'purpose': 'key_rotation',
                'timestamp': time.time()
            },
            key_size=32
        )
    
    def encrypt_frame(self, payload: bytes, associated_data: Dict) -> Tuple[bytes, bytes]:
        """
        Encrypt frame payload with AEAD-like properties.
        
        Uses STC encryption with associated data to provide authentication
        alongside encryption (similar to AES-GCM/ChaCha20-Poly1305).
        
        Args:
            payload: Frame payload to encrypt
            associated_data: Dictionary containing frame metadata
                           (type, flags, session_id, sequence, timestamp)
            
        Returns:
            Tuple of (encrypted_payload, compact_metadata)
        """
        # Encrypt with associated data for AEAD-like authentication
        encrypted, metadata = self.context.encrypt(
            data=payload,
            context_data=associated_data
        )
        
        # Serialize metadata to compact TLV format
        compact_meta = stc_api.serialize_metadata_tlv(metadata)
        
        return encrypted, compact_meta
    
    def decrypt_frame(self, encrypted: bytes, compact_meta: bytes,
                     associated_data: Dict) -> bytes:
        """
        Decrypt frame payload and verify associated data.
        
        Args:
            encrypted: Encrypted payload
            compact_meta: Compact TLV-encoded metadata
            associated_data: Same associated data used in encryption
            
        Returns:
            Decrypted payload
            
        Raises:
            Exception: If decryption or authentication fails
        """
        # Deserialize metadata from TLV
        metadata = stc_api.deserialize_metadata_tlv(compact_meta)
        
        # Decrypt and verify associated data
        return self.context.decrypt(
            encrypted_data=encrypted,
            metadata=metadata,
            context_data=associated_data
        )
    
    def create_stream_context(self, session_id: bytes, stream_id: int) -> 'StreamContext':
        """
        Create isolated STC context for a specific stream.
        
        Each stream gets its own STC context to prevent nonce reuse
        and provide cryptographic isolation between streams.
        
        Args:
            session_id: Session identifier (8 bytes)
            stream_id: Stream identifier (4-byte integer)
            
        Returns:
            StreamContext instance
        """
        # Create unique cache key
        cache_key = (session_id, stream_id)
        
        # Return cached context if exists
        if cache_key in self._stream_contexts:
            return self._stream_contexts[cache_key]
        
        # Derive stream-specific seed from session_id and stream_id
        stream_seed = self.hash_data(
            session_id + stream_id.to_bytes(4, 'big'),
            {'purpose': 'stream_context'}
        )
        
        # Create isolated STC context
        stream_ctx = stc_api.initialize(stream_seed)
        
        # Create and cache StreamContext
        context = StreamContext(stream_ctx, stream_id)
        self._stream_contexts[cache_key] = context
        
        return context
    
    def clear_stream_context(self, session_id: bytes, stream_id: int):
        """
        Clear cached stream context (e.g., when stream closes).
        
        Args:
            session_id: Session identifier
            stream_id: Stream identifier
        """
        cache_key = (session_id, stream_id)
        self._stream_contexts.pop(cache_key, None)


class StreamContext:
    """
    Isolated STC context for a specific stream.
    
    Provides cryptographic isolation between streams and prevents
    nonce reuse by maintaining per-stream encryption state.
    """
    
    def __init__(self, stc_context, stream_id: int):
        """
        Initialize stream context.
        
        Args:
            stc_context: Isolated STC context for this stream
            stream_id: Stream identifier
        """
        self.context = stc_context
        self.stream_id = stream_id
        self.chunk_index = 0
    
    def encrypt_chunk(self, chunk: bytes) -> Tuple[bytes, bytes]:
        """
        Encrypt single stream chunk.
        
        Args:
            chunk: Chunk data to encrypt
            
        Returns:
            Tuple of (encrypted_chunk, compact_metadata)
        """
        # Associated data includes stream_id and chunk_index
        associated_data = {
            'stream_id': self.stream_id,
            'chunk_index': self.chunk_index,
            'purpose': 'stream_chunk'
        }
        
        # Encrypt chunk
        encrypted, metadata = self.context.encrypt(
            data=chunk,
            context_data=associated_data
        )
        
        # Serialize metadata to compact format
        compact_meta = stc_api.serialize_metadata_tlv(metadata)
        
        # Increment chunk index for next encryption
        self.chunk_index += 1
        
        return encrypted, compact_meta
    
    def decrypt_chunk(self, encrypted: bytes, compact_meta: bytes,
                     chunk_index: int) -> bytes:
        """
        Decrypt stream chunk.
        
        Args:
            encrypted: Encrypted chunk data
            compact_meta: Compact TLV-encoded metadata
            chunk_index: Chunk index (for verification)
            
        Returns:
            Decrypted chunk data
            
        Raises:
            Exception: If decryption or verification fails
        """
        # Deserialize metadata
        metadata = stc_api.deserialize_metadata_tlv(compact_meta)
        
        # Associated data must match encryption
        associated_data = {
            'stream_id': self.stream_id,
            'chunk_index': chunk_index,
            'purpose': 'stream_chunk'
        }
        
        # Decrypt and verify
        return self.context.decrypt(
            encrypted_data=encrypted,
            metadata=metadata,
            context_data=associated_data
        )
    
    def reset_index(self):
        """Reset chunk index (e.g., for stream restart)."""
        self.chunk_index = 0
