"""
Tests for STC crypto context initialization and management.
"""

import pytest

from seigr_toolset_transmissions.crypto import context


class TestCryptoContext:
    """Test STC context management."""
    
    def teardown_method(self):
        """Reset context after each test."""
        # Reset global context
        context._context = None
    
    def test_initialize_with_bytes_seed(self):
        """Test initializing context with bytes seed."""
        ctx = context.initialize(b"test_seed_bytes")
        
        assert ctx is not None
        assert context.get_context() == ctx
    
    def test_initialize_with_string_seed(self):
        """Test initializing context with string seed."""
        ctx = context.initialize("test_seed_string")
        
        assert ctx is not None
        assert context.get_context() == ctx
    
    def test_initialize_with_int_seed(self):
        """Test initializing context with int seed."""
        ctx = context.initialize(12345678)
        
        assert ctx is not None
        assert context.get_context() == ctx
    
    def test_get_context_before_init(self):
        """Test getting context before initialization raises error."""
        with pytest.raises(RuntimeError, match="STC context not initialized"):
            context.get_context()
    
    def test_get_context_after_init(self):
        """Test getting context after initialization."""
        expected_ctx = context.initialize(b"test_seed")
        actual_ctx = context.get_context()
        
        assert actual_ctx == expected_ctx
    
    def test_reinitialize_context(self):
        """Test reinitializing context with different seed."""
        ctx1 = context.initialize(b"seed1")
        ctx2 = context.initialize(b"seed2")
        
        # Both should be valid contexts
        assert ctx1 is not None
        assert ctx2 is not None
        
        # Current context should be the latest
        assert context.get_context() == ctx2
    
    def test_initialize_with_zero_seed(self):
        """Test initializing with zero seed."""
        ctx = context.initialize(0)
        assert ctx is not None
        assert context.get_context() == ctx
    
    def test_initialize_with_large_int_seed(self):
        """Test initializing with large integer seed."""
        ctx = context.initialize(2**128)
        assert ctx is not None
        assert context.get_context() == ctx
    
    def test_initialize_with_empty_bytes(self):
        """Test initializing with empty bytes."""
        ctx = context.initialize(b"")
        assert ctx is not None
        assert context.get_context() == ctx
    
    def test_initialize_with_empty_string(self):
        """Test initializing with empty string."""
        ctx = context.initialize("")
        assert ctx is not None
        assert context.get_context() == ctx
    
    def test_initialize_with_long_bytes(self):
        """Test initializing with very long bytes seed."""
        import secrets
        ctx = context.initialize(secrets.token_bytes(1024))
        assert ctx is not None
        assert context.get_context() == ctx
    
    def test_initialize_with_unicode_string(self):
        """Test initializing with unicode string seed."""
        ctx = context.initialize("测试种子🔒🔑")
        assert ctx is not None
        assert context.get_context() == ctx


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
