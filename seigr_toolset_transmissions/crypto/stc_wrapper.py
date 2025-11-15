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
    from interfaces.api.streaming_context import StreamingContext
except ImportError:
    # Add site-packages to path if needed
    import site
    sys.path.extend(site.getsitepackages())
    from interfaces.api import stc_api
    from interfaces.api.streaming_context import StreamingContext


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
    
    def derive_session_key(self, handshake_data: Union[Dict, bytes]) -> bytes:
        """
        Derive session key from handshake context.
        
        Args:
            handshake_data: Dictionary containing handshake parameters
                          (e.g., nonces, timestamps, ephemeral data)
                          or bytes for simple derivation
            
        Returns:
            32-byte session key
        """
        # Convert bytes to dict if needed
        if isinstance(handshake_data, bytes):
            handshake_data = {'seed': handshake_data.hex()}
            
        return self.context.derive_key(
            length=32,
            context_data=handshake_data
        )
    
    def rotate_session_key(self, current_key: bytes, rotation_nonce: Union[bytes, int]) -> bytes:
        """
        Derive new session key for key rotation.
        
        Args:
            current_key: Current session key
            rotation_nonce: Fresh nonce for rotation (bytes or int version number)
            
        Returns:
            New 32-byte session key
        """
        # Handle int rotation_nonce (version number)
        if isinstance(rotation_nonce, int):
            rotation_nonce = rotation_nonce.to_bytes(8, 'big')
            
        return self.context.derive_key(
            length=32,
            context_data={
                'current_key': current_key.hex(),
                'rotation_nonce': rotation_nonce.hex(),
                'purpose': 'key_rotation',
                'timestamp': time.time()
            }
        )
    
    def encrypt_frame(self, *args, **kwargs) -> Tuple[bytes, bytes]:
        """
        Encrypt frame payload with AEAD-like properties.
        
        Supports two calling conventions:
        1. encrypt_frame(payload, associated_data_dict) - original dict-based
        2. encrypt_frame(session_id=..., stream_id=..., payload=..., associated_data=...) - test-style
        3. encrypt_frame(session_id, stream_id, payload, associated_data) - positional
        
        Uses STC encryption with associated data to provide authentication
        alongside encryption (similar to AES-GCM/ChaCha20-Poly1305).
        
        Returns:
            Tuple of (encrypted_payload, metadata_bytes)
        """
        # Parse arguments
        if kwargs:
            # Keyword argument style from tests
            session_id = kwargs.get('session_id')
            stream_id = kwargs.get('stream_id')
            payload = kwargs.get('payload')
            associated_data = kwargs.get('associated_data')
            
            if session_id is not None and stream_id is not None and payload is not None:
                # Build associated data dict
                assoc_dict = {
                    'session_id': session_id,
                    'stream_id': stream_id,
                }
                if associated_data:
                    if isinstance(associated_data, bytes):
                        assoc_dict['associated_data'] = associated_data
                    elif isinstance(associated_data, dict):
                        assoc_dict.update(associated_data)
                payload_to_encrypt = payload
            else:
                # Original dict-based style with kwargs
                payload_to_encrypt = kwargs.get('payload', args[0] if args else b'')
                assoc_dict = kwargs.get('associated_data', args[1] if len(args) > 1 else {})
                if not isinstance(assoc_dict, dict):
                    assoc_dict = {'data': assoc_dict}
        elif len(args) == 4:
            # Positional: encrypt_frame(session_id, stream_id, payload, associated_data)
            session_id, stream_id, payload, associated_data = args
            assoc_dict = {
                'session_id': session_id,
                'stream_id': stream_id,
            }
            if associated_data:
                if isinstance(associated_data, bytes):
                    assoc_dict['associated_data'] = associated_data
                elif isinstance(associated_data, dict):
                    assoc_dict.update(associated_data)
            payload_to_encrypt = payload
        elif len(args) == 2:
            # Original dict-based: encrypt_frame(payload, associated_data_dict)
            payload_to_encrypt = args[0]
            assoc_dict = args[1] if isinstance(args[1], dict) else {'data': args[1]}
        else:
            raise TypeError(f"encrypt_frame() invalid arguments: args={args}, kwargs={kwargs}")
        
        # Encrypt with associated data for AEAD-like authentication
        encrypted, metadata = self.context.encrypt(
            data=payload_to_encrypt,
            context_data=assoc_dict
        )
        
        return encrypted, metadata
    
    def decrypt_frame(self, *args, **kwargs) -> bytes:
        """
        Decrypt frame payload and verify associated data.
        
        Supports multiple calling conventions:
        1. decrypt_frame(encrypted, metadata, associated_data_dict) - original
        2. decrypt_frame(session_id=..., stream_id=..., encrypted_payload=..., nonce=..., associated_data=...) - test
        3. decrypt_frame(session_id, stream_id, encrypted, nonce, associated_data) - positional
        
        Returns:
            Decrypted payload
            
        Raises:
            Exception: If decryption or authentication fails
        """
        # Parse arguments
        if kwargs:
            # Keyword argument style from tests
            session_id = kwargs.get('session_id')
            stream_id = kwargs.get('stream_id')
            encrypted_payload = kwargs.get('encrypted_payload')
            nonce = kwargs.get('nonce')
            associated_data = kwargs.get('associated_data')
            
            if session_id is not None and stream_id is not None:
                # Build associated data dict
                assoc_dict = {
                    'session_id': session_id,
                    'stream_id': stream_id,
                }
                if associated_data:
                    if isinstance(associated_data, bytes):
                        assoc_dict['associated_data'] = associated_data
                    elif isinstance(associated_data, dict):
                        assoc_dict.update(associated_data)
                data_to_decrypt = encrypted_payload
                metadata_to_use = nonce
            else:
                # Original dict-based with kwargs
                data_to_decrypt = kwargs.get('encrypted', args[0] if args else b'')
                metadata_to_use = kwargs.get('metadata', args[1] if len(args) > 1 else b'')
                assoc_dict = kwargs.get('associated_data', args[2] if len(args) > 2 else {})
                if not isinstance(assoc_dict, dict):
                    assoc_dict = {'data': assoc_dict}
        elif len(args) == 5:
            # Positional: decrypt_frame(session_id, stream_id, encrypted, nonce, associated_data)
            session_id, stream_id, encrypted_payload, nonce, associated_data = args
            assoc_dict = {
                'session_id': session_id,
                'stream_id': stream_id,
            }
            if associated_data:
                if isinstance(associated_data, bytes):
                    assoc_dict['associated_data'] = associated_data
                elif isinstance(associated_data, dict):
                    assoc_dict.update(associated_data)
            data_to_decrypt = encrypted_payload
            metadata_to_use = nonce
        elif len(args) == 3:
            # Original: decrypt_frame(encrypted, metadata, associated_data_dict)
            data_to_decrypt = args[0]
            metadata_to_use = args[1]
            assoc_dict = args[2] if isinstance(args[2], dict) else {'data': args[2]}
        else:
            raise TypeError(f"decrypt_frame() invalid arguments: args={args}, kwargs={kwargs}")
        
        # Decrypt and verify associated data
        return self.context.decrypt(
            encrypted_data=data_to_decrypt,
            metadata=metadata_to_use,
            context_data=assoc_dict
        )
    
    def create_stream_context(self, session_id: bytes, stream_id: int) -> StreamingContext:
        """
        Create isolated StreamingContext for a specific stream.
        
        Each stream gets its own StreamingContext to prevent nonce reuse
        and provide cryptographic isolation between streams.
        
        Args:
            session_id: Session identifier (8 bytes)
            stream_id: Stream identifier (4-byte integer)
            
        Returns:
            StreamingContext from STC v0.4.0 (no wrapper needed)
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
        
        # Create StreamingContext directly (no wrapper)
        context = StreamingContext(stream_seed)
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
