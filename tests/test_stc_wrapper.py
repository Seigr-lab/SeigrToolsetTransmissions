"""
Tests for STC wrapper cryptographic operations.
"""

import pytest
from seigr_toolset_transmissions.crypto import STCWrapper
from seigr_toolset_transmissions.utils.exceptions import STTCryptoError


class TestSTCWrapper:
    """Test STC wrapper for cryptographic operations."""
    
    @pytest.fixture
    def seed(self):
        """Shared seed for tests."""
        return b"test_seed_32_bytes_minimum!!!!!"
    
    @pytest.fixture
    def stc_wrapper(self, seed):
        """Create STC wrapper."""
        return STCWrapper(seed)
    
    def test_create_wrapper(self, seed):
        """Test creating STC wrapper."""
        wrapper = STCWrapper(seed)
        assert wrapper is not None
    
    def test_hash_data(self, stc_wrapper):
        """Test hashing data with PHE."""
        data = b"test data to hash"
        
        hash_value = stc_wrapper.hash_data(data)
        
        assert isinstance(hash_value, bytes)
        assert len(hash_value) == 32  # PHE hash size
    
    def test_hash_deterministic(self, stc_wrapper):
        """Test that hashing is deterministic."""
        data = b"deterministic test"
        
        hash1 = stc_wrapper.hash_data(data)
        hash2 = stc_wrapper.hash_data(data)
        
        assert hash1 == hash2
    
    def test_hash_different_data(self, stc_wrapper):
        """Test that different data produces different hashes."""
        data1 = b"first data"
        data2 = b"second data"
        
        hash1 = stc_wrapper.hash_data(data1)
        hash2 = stc_wrapper.hash_data(data2)
        
        assert hash1 != hash2
    
    def test_generate_node_id(self, stc_wrapper):
        """Test generating node ID."""
        node_id = stc_wrapper.generate_node_id(b"node_seed")
        
        assert isinstance(node_id, bytes)
        assert len(node_id) == 32
    
    def test_node_id_deterministic(self, stc_wrapper):
        """Test that node ID generation is deterministic."""
        seed = b"same_seed"
        
        node_id1 = stc_wrapper.generate_node_id(seed)
        node_id2 = stc_wrapper.generate_node_id(seed)
        
        assert node_id1 == node_id2
    
    def test_derive_session_key(self, stc_wrapper):
        """Test deriving session key."""
        context = b"session_context"
        
        session_key = stc_wrapper.derive_session_key(context)
        
        assert isinstance(session_key, bytes)
        assert len(session_key) >= 32
    
    def test_session_key_deterministic(self, stc_wrapper):
        """Test that session key derivation is deterministic."""
        context = b"same_context"
        
        key1 = stc_wrapper.derive_session_key(context)
        key2 = stc_wrapper.derive_session_key(context)
        
        assert key1 == key2
    
    def test_different_contexts_different_keys(self, stc_wrapper):
        """Test that different contexts produce different keys."""
        key1 = stc_wrapper.derive_session_key(b"context1")
        key2 = stc_wrapper.derive_session_key(b"context2")
        
        assert key1 != key2
    
    def test_rotate_session_key(self, stc_wrapper):
        """Test rotating session key."""
        session_id = b'\x01\x02\x03\x04\x05\x06\x07\x08'
        version = 0
        
        key1 = stc_wrapper.rotate_session_key(session_id, version)
        key2 = stc_wrapper.rotate_session_key(session_id, version + 1)
        
        assert key1 != key2
    
    def test_encrypt_decrypt_frame(self, stc_wrapper):
        """Test encrypting and decrypting frame payload."""
        session_id = b'\x01' * 8
        stream_id = 1
        payload = b"secret message"
        associated_data = b"metadata"
        
        # Encrypt
        encrypted, nonce = stc_wrapper.encrypt_frame(
            session_id=session_id,
            stream_id=stream_id,
            payload=payload,
            associated_data=associated_data,
        )
        
        assert encrypted != payload
        assert isinstance(nonce, bytes)
        
        # Decrypt
        decrypted = stc_wrapper.decrypt_frame(
            session_id=session_id,
            stream_id=stream_id,
            encrypted_payload=encrypted,
            nonce=nonce,
            associated_data=associated_data,
        )
        
        assert decrypted == payload
    
    def test_encrypt_decrypt_roundtrip(self, stc_wrapper):
        """Test full encrypt/decrypt roundtrip."""
        session_id = b'\x02' * 8
        stream_id = 2
        original = b"confidential data"
        metadata = b"frame metadata"
        
        # Encrypt
        encrypted, nonce = stc_wrapper.encrypt_frame(
            session_id, stream_id, original, metadata
        )
        
        # Decrypt
        decrypted = stc_wrapper.decrypt_frame(
            session_id, stream_id, encrypted, nonce, metadata
        )
        
        assert decrypted == original
    
    def test_wrong_associated_data_fails(self, stc_wrapper):
        """Test that wrong associated data fails decryption."""
        session_id = b'\x03' * 8
        stream_id = 3
        payload = b"authenticated"
        metadata = b"correct metadata"
        
        encrypted, nonce = stc_wrapper.encrypt_frame(
            session_id, stream_id, payload, metadata
        )
        
        # Try to decrypt with wrong metadata
        with pytest.raises(STTCryptoError):
            stc_wrapper.decrypt_frame(
                session_id, stream_id, encrypted, nonce, b"wrong metadata"
            )
    
    def test_wrong_nonce_fails(self, stc_wrapper):
        """Test that wrong nonce fails decryption."""
        session_id = b'\x04' * 8
        stream_id = 4
        payload = b"data"
        metadata = b"meta"
        
        encrypted, nonce = stc_wrapper.encrypt_frame(
            session_id, stream_id, payload, metadata
        )
        
        # Try to decrypt with wrong nonce
        wrong_nonce = b'\x00' * len(nonce)
        
        with pytest.raises(STTCryptoError):
            stc_wrapper.decrypt_frame(
                session_id, stream_id, encrypted, wrong_nonce, metadata
            )
    
    def test_create_stream_context(self, stc_wrapper):
        """Test creating isolated stream context."""
        session_id = b'\x05' * 8
        stream_id = 5
        
        context = stc_wrapper.create_stream_context(session_id, stream_id)
        
        assert context is not None
    
    def test_stream_context_isolation(self, stc_wrapper):
        """Test that stream contexts are isolated."""
        session_id = b'\x06' * 8
        
        context1 = stc_wrapper.create_stream_context(session_id, stream_id=1)
        context2 = stc_wrapper.create_stream_context(session_id, stream_id=2)
        
        # Different stream IDs should produce different contexts
        assert context1 != context2
    
    def test_encrypt_with_empty_payload(self, stc_wrapper):
        """Test encrypting empty payload."""
        session_id = b'\x07' * 8
        stream_id = 7
        
        encrypted, nonce = stc_wrapper.encrypt_frame(
            session_id, stream_id, b"", b""
        )
        
        decrypted = stc_wrapper.decrypt_frame(
            session_id, stream_id, encrypted, nonce, b""
        )
        
        assert decrypted == b""
    
    def test_encrypt_large_payload(self, stc_wrapper):
        """Test encrypting large payload."""
        session_id = b'\x08' * 8
        stream_id = 8
        large_payload = b"x" * 100000  # 100KB
        
        encrypted, nonce = stc_wrapper.encrypt_frame(
            session_id, stream_id, large_payload, b""
        )
        
        decrypted = stc_wrapper.decrypt_frame(
            session_id, stream_id, encrypted, nonce, b""
        )
        
        assert decrypted == large_payload
    
    def test_different_seeds_different_results(self):
        """Test that different seeds produce different results."""
        seed1 = b"seed_one_32_bytes_minimum!!!!!"
        seed2 = b"seed_two_32_bytes_minimum!!!!!"
        
        wrapper1 = STCWrapper(seed1)
        wrapper2 = STCWrapper(seed2)
        
        data = b"same data"
        
        hash1 = wrapper1.hash_data(data)
        hash2 = wrapper2.hash_data(data)
        
        assert hash1 != hash2
    
    def test_cross_wrapper_decryption_fails(self):
        """Test that different wrappers cannot decrypt each other's data."""
        seed1 = b"wrapper_one_32_bytes_minimum!!"
        seed2 = b"wrapper_two_32_bytes_minimum!!"
        
        wrapper1 = STCWrapper(seed1)
        wrapper2 = STCWrapper(seed2)
        
        session_id = b'\x09' * 8
        stream_id = 9
        payload = b"secret"
        
        # Encrypt with wrapper1
        encrypted, nonce = wrapper1.encrypt_frame(
            session_id, stream_id, payload, b""
        )
        
        # Try to decrypt with wrapper2
        with pytest.raises(STTCryptoError):
            wrapper2.decrypt_frame(session_id, stream_id, encrypted, nonce, b"")
    
    def test_sequential_encryptions_different_nonces(self, stc_wrapper):
        """Test that sequential encryptions use different nonces."""
        session_id = b'\x0a' * 8
        stream_id = 10
        payload = b"message"
        
        encrypted1, nonce1 = stc_wrapper.encrypt_frame(
            session_id, stream_id, payload, b""
        )
        encrypted2, nonce2 = stc_wrapper.encrypt_frame(
            session_id, stream_id, payload, b""
        )
        
        # Nonces should be different
        assert nonce1 != nonce2
        
        # But both should decrypt correctly
        decrypted1 = stc_wrapper.decrypt_frame(
            session_id, stream_id, encrypted1, nonce1, b""
        )
        decrypted2 = stc_wrapper.decrypt_frame(
            session_id, stream_id, encrypted2, nonce2, b""
        )
        
        assert decrypted1 == payload
        assert decrypted2 == payload
