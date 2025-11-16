"""
Tests for node identity generation.
"""

import pytest

from seigr_toolset_transmissions.crypto import context
from seigr_toolset_transmissions.crypto.node_identity import generate_node_id


@pytest.fixture(scope="module", autouse=True)
def init_stc_context():
    """Initialize STC context for all tests."""
    context.initialize(b"test_node_identity_seed")


class TestNodeIdentity:
    """Test node ID generation."""
    
    def test_generate_node_id_basic(self):
        """Test basic node ID generation."""
        identity = b"test_public_key_12345678"
        
        node_id = generate_node_id(identity)
        
        assert isinstance(node_id, bytes)
        assert len(node_id) == 32
    
    def test_generate_node_id_different_identities(self):
        """Test different identities produce different node IDs."""
        identity1 = b"identity_one"
        identity2 = b"identity_two"
        
        node_id1 = generate_node_id(identity1)
        node_id2 = generate_node_id(identity2)
        
        assert node_id1 != node_id2
    
    def test_generate_node_id_short_identity(self):
        """Test with short identity."""
        identity = b"short"
        
        node_id = generate_node_id(identity)
        
        assert isinstance(node_id, bytes)
        assert len(node_id) == 32
    
    def test_generate_node_id_long_identity(self):
        """Test with long identity."""
        identity = b"a" * 256
        
        node_id = generate_node_id(identity)
        
        assert isinstance(node_id, bytes)
        assert len(node_id) == 32
    
    def test_generate_node_id_binary_data(self):
        """Test with arbitrary binary data."""
        identity = bytes(range(256))
        
        node_id = generate_node_id(identity)
        
        assert isinstance(node_id, bytes)
        assert len(node_id) == 32


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
