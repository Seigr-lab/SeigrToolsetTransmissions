"""
Tests for crypto module __init__.py imports.
"""

import pytest


class TestCryptoInit:
    """Test crypto module initialization and imports."""
    
    def test_stc_wrapper_import(self):
        """Test STCWrapper is importable from crypto module."""
        from seigr_toolset_transmissions.crypto import STCWrapper
        
        assert STCWrapper is not None
        
        # Can instantiate
        wrapper = STCWrapper(b"test_seed_12345678")
        assert wrapper is not None
    
    def test_modular_api_imports(self):
        """Test modular API components are importable."""
        from seigr_toolset_transmissions import crypto
        
        # Check modular API availability
        assert hasattr(crypto, '_MODULAR_API_AVAILABLE')
        
        if crypto._MODULAR_API_AVAILABLE:
            assert crypto.streaming is not None
            assert crypto.session_keys is not None
            assert crypto.node_identity is not None
    
    def test_all_exports(self):
        """Test __all__ exports are correct."""
        from seigr_toolset_transmissions import crypto
        
        assert hasattr(crypto, '__all__')
        assert 'STCWrapper' in crypto.__all__
        assert 'streaming' in crypto.__all__
        assert 'session_keys' in crypto.__all__
        assert 'node_identity' in crypto.__all__
    
    def test_streaming_module_access(self):
        """Test streaming module can be accessed."""
        from seigr_toolset_transmissions import crypto
        
        if crypto._MODULAR_API_AVAILABLE:
            # Can access streaming functions
            from seigr_toolset_transmissions.crypto.streaming import create_stream_context
            assert create_stream_context is not None
    
    def test_session_keys_module_access(self):
        """Test session_keys module can be accessed."""
        from seigr_toolset_transmissions import crypto
        
        if crypto._MODULAR_API_AVAILABLE:
            # Can access session key functions
            from seigr_toolset_transmissions.crypto.session_keys import derive_session_key
            assert derive_session_key is not None
    
    def test_node_identity_module_access(self):
        """Test node_identity module can be accessed."""
        from seigr_toolset_transmissions import crypto
        
        if crypto._MODULAR_API_AVAILABLE:
            # Can access node identity functions
            from seigr_toolset_transmissions.crypto.node_identity import generate_node_id
            assert generate_node_id is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
