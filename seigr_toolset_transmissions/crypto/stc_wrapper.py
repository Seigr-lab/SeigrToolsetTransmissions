"""
STCWrapper - STC v0.4.0 crypto operations for STT.

Uses STC's adaptive, non-deterministic crypto:
- Probabilistic hashing (PHE) for privacy
- Adaptive morphing for forward secrecy
- StreamingContext for high-performance encryption

This is MODERN crypto - not old-school deterministic hashing.
"""

from typing import Union
from . import context


class STCWrapper:
    """
    Backwards compatibility wrapper for legacy code.
    
    New code should use modular functions directly from:
    - crypto.streaming
    - crypto.session_keys
    - crypto.node_identity
    """
    
    def __init__(self, node_seed: Union[str, bytes, int]):
        """Initialize STC context with isolated stream cache."""
        # Each wrapper instance gets its own context and stream cache
        self._context = context.initialize(node_seed)
        self.node_seed = node_seed
        self._stream_contexts = {}  # Per-instance cache
    
    def create_stream_context(self, session_id: bytes, stream_id: int):
        """Create StreamingContext with per-instance caching."""
        cache_key = (session_id, stream_id)
        
        if cache_key in self._stream_contexts:
            return self._stream_contexts[cache_key]
        
        # Create context using our instance context
        from interfaces.api.streaming_context import StreamingContext
        
        stream_data = session_id + stream_id.to_bytes(4, 'big')
        stream_seed = self._context.derive_key(
            length=32,
            context_data={'stream': stream_data.hex()}
        )
        
        stream_context = StreamingContext(stream_seed)
        self._stream_contexts[cache_key] = stream_context
        
        return stream_context
    
    def derive_session_key(self, handshake_data):
        """Derive session key using instance context."""
        if isinstance(handshake_data, bytes):
            handshake_data = {'seed': handshake_data.hex()}
        return self._context.derive_key(length=32, context_data=handshake_data)
    
    def rotate_session_key(self, current_key: bytes, rotation_nonce: Union[bytes, int]):
        """Rotate session key using instance context."""
        # Handle int rotation_nonce (version number from tests)
        if isinstance(rotation_nonce, int):
            rotation_nonce_hex = rotation_nonce.to_bytes(8, 'big').hex()
        else:
            rotation_nonce_hex = rotation_nonce.hex()
            
        return self._context.derive_key(
            length=32,
            context_data={
                'current_key': current_key.hex(),
                'nonce': rotation_nonce_hex,
                'purpose': 'rotation'
            }
        )
    
    def hash_data(self, data: bytes, context: dict = None) -> bytes:
        """
        Hash data using STC PHE (non-deterministic, privacy-preserving).
        
        NOTE: Output changes each call due to adaptive morphing - this is CORRECT.
        For session establishment, both peers derive from shared secret, not hash.
        
        Args:
            data: Data to hash
            context: Optional context dict (for compatibility, merged into PHE context)
        """
        phe_context = {'purpose': 'hash'}
        if context:
            phe_context.update(context)
        return self._context.phe.digest(data, context=phe_context)
    
    def generate_node_id(self, identity: bytes) -> bytes:
        """
        Generate node ID from identity (non-deterministic).
        
        Each node generates ephemeral ID on startup - no correlation with identity.
        Privacy-first design.
        """
        return self._context.phe.digest(identity, context={'purpose': 'node_id'})
    
    def encrypt_frame(self, *args, **kwargs):
        """Encrypt frame with AEAD-like authentication."""
        # Parse flexible arguments for backwards compatibility
        if kwargs:
            session_id = kwargs.get('session_id')
            stream_id = kwargs.get('stream_id')
            payload = kwargs.get('payload')
            associated_data = kwargs.get('associated_data', {})
        elif len(args) == 4:
            session_id, stream_id, payload, associated_data = args
        elif len(args) == 2:
            payload, associated_data = args
            session_id = stream_id = None
        else:
            raise TypeError(f"encrypt_frame() invalid arguments")
        
        # Build context for encryption
        assoc_dict = {}
        if session_id is not None:
            assoc_dict['session_id'] = session_id if isinstance(session_id, str) else session_id.hex() if isinstance(session_id, bytes) else str(session_id)
        if stream_id is not None:
            assoc_dict['stream_id'] = stream_id
        if isinstance(associated_data, dict):
            assoc_dict.update(associated_data)
        elif associated_data:
            assoc_dict['data'] = associated_data.hex() if isinstance(associated_data, bytes) else str(associated_data)
        
        encrypted, metadata = self._context.encrypt(data=payload, context_data=assoc_dict)
        return encrypted, metadata
    
    def decrypt_frame(self, *args, **kwargs):
        """Decrypt frame and verify authentication."""
        # Parse flexible arguments
        if kwargs:
            # Support both naming conventions
            encrypted_payload = kwargs.get('encrypted_payload') or kwargs.get('encrypted')
            nonce = kwargs.get('nonce') or kwargs.get('metadata')
            session_id = kwargs.get('session_id')
            stream_id = kwargs.get('stream_id')
            associated_data = kwargs.get('associated_data', {})
        elif len(args) == 5:
            session_id, stream_id, encrypted_payload, nonce, associated_data = args
        elif len(args) == 3:
            encrypted_payload, nonce, associated_data = args
            session_id = stream_id = None
        else:
            raise TypeError(f"decrypt_frame() invalid arguments")
        
        # Build context for decryption
        assoc_dict = {}
        if session_id is not None:
            assoc_dict['session_id'] = session_id if isinstance(session_id, str) else session_id.hex() if isinstance(session_id, bytes) else str(session_id)
        if stream_id is not None:
            assoc_dict['stream_id'] = stream_id
        if isinstance(associated_data, dict):
            assoc_dict.update(associated_data)
        elif associated_data:
            assoc_dict['data'] = associated_data.hex() if isinstance(associated_data, bytes) else str(associated_data)
        
        return self._context.decrypt(encrypted_data=encrypted_payload, metadata=nonce, context_data=assoc_dict)
    
    def clear_stream_context(self, session_id: bytes, stream_id: int):
        """Clear cached stream context."""
        cache_key = (session_id, stream_id)
        self._stream_contexts.pop(cache_key, None)
