"""
Tests for crypto streaming module.
"""

import pytest
from seigr_toolset_transmissions.crypto import context
from seigr_toolset_transmissions.crypto.streaming import (
    create_stream_context,
    clear_stream_context,
    _stream_contexts
)


@pytest.fixture(scope="module", autouse=True)
def init_stc_context():
    """Initialize STC context for all tests."""
    context.initialize(b"test_streaming_seed")


class TestCryptoStreaming:
    """Test stream encryption context management."""
    
    def teardown_method(self):
        """Clear contexts after each test."""
        _stream_contexts.clear()
    
    def test_create_stream_context(self):
        """Test creating stream context."""
        session_id = b"12345678"
        stream_id = 1
        
        ctx = create_stream_context(session_id, stream_id)
        
        assert ctx is not None
        # Should be cached
        assert (session_id, stream_id) in _stream_contexts
    
    def test_stream_context_cached(self):
        """Test stream context is cached."""
        session_id = b"12345678"
        stream_id = 1
        
        ctx1 = create_stream_context(session_id, stream_id)
        ctx2 = create_stream_context(session_id, stream_id)
        
        # Should return same instance
        assert ctx1 is ctx2
    
    def test_different_streams_different_contexts(self):
        """Test different streams get different contexts."""
        session_id = b"12345678"
        
        ctx1 = create_stream_context(session_id, 1)
        ctx2 = create_stream_context(session_id, 2)
        
        assert ctx1 is not ctx2
    
    def test_different_sessions_different_contexts(self):
        """Test different sessions get different contexts."""
        stream_id = 1
        
        ctx1 = create_stream_context(b"session1", stream_id)
        ctx2 = create_stream_context(b"session2", stream_id)
        
        assert ctx1 is not ctx2
    
    def test_clear_stream_context(self):
        """Test clearing stream context."""
        session_id = b"12345678"
        stream_id = 1
        
        # Create context
        create_stream_context(session_id, stream_id)
        assert (session_id, stream_id) in _stream_contexts
        
        # Clear it
        clear_stream_context(session_id, stream_id)
        assert (session_id, stream_id) not in _stream_contexts
    
    def test_clear_nonexistent_context(self):
        """Test clearing context that doesn't exist."""
        # Should not raise error
        clear_stream_context(b"nonexist", 99)
    
    def test_stream_isolation(self):
        """Test streams are cryptographically isolated."""
        session_id = b"12345678"
        
        # Create multiple stream contexts
        contexts = []
        for i in range(5):
            ctx = create_stream_context(session_id, i)
            contexts.append(ctx)
        
        # All should be different
        for i, ctx1 in enumerate(contexts):
            for j, ctx2 in enumerate(contexts):
                if i != j:
                    assert ctx1 is not ctx2
    
    def test_create_stream_context_large_stream_id(self):
        """Test creating context with large stream ID."""
        session_id = b"12345678"
        stream_id = 2**31 - 1  # Max 32-bit int
        
        ctx = create_stream_context(session_id, stream_id)
        assert ctx is not None
        assert (session_id, stream_id) in _stream_contexts
    
    def test_create_stream_context_zero_stream_id(self):
        """Test creating context with stream ID 0."""
        session_id = b"12345678"
        stream_id = 0
        
        ctx = create_stream_context(session_id, stream_id)
        assert ctx is not None
        assert (session_id, stream_id) in _stream_contexts
    
    def test_stream_context_short_session_id(self):
        """Test creating context with short session ID."""
        session_id = b"ab"
        stream_id = 1
        
        ctx = create_stream_context(session_id, stream_id)
        assert ctx is not None
    
    def test_stream_context_long_session_id(self):
        """Test creating context with long session ID."""
        session_id = b"a" * 256
        stream_id = 1
        
        ctx = create_stream_context(session_id, stream_id)
        assert ctx is not None
    
    def test_clear_then_recreate(self):
        """Test clearing and recreating stream context."""
        session_id = b"12345678"
        stream_id = 1
        
        # Create
        ctx1 = create_stream_context(session_id, stream_id)
        
        # Clear
        clear_stream_context(session_id, stream_id)
        
        # Recreate
        ctx2 = create_stream_context(session_id, stream_id)
        
        # Should be different instance
        assert ctx1 is not ctx2
    
    def test_multiple_sessions_multiple_streams(self):
        """Test multiple sessions each with multiple streams."""
        sessions = [b"session1", b"session2", b"session3"]
        streams = [1, 2, 3]
        
        contexts = {}
        for session in sessions:
            for stream in streams:
                ctx = create_stream_context(session, stream)
                contexts[(session, stream)] = ctx
        
        # Should have 9 unique contexts
        assert len(_stream_contexts) == 9
        assert len(set(contexts.values())) == 9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
