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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
