"""
Stream encryption - Creates isolated StreamingContext per stream.

Provides cryptographic isolation between streams to prevent nonce reuse.
Each (session_id, stream_id) pair gets its own StreamingContext.
"""

from typing import Dict, Tuple, Union

try:
    from seigr_crypto.interfaces.api.streaming_context import StreamingContext
except ImportError:
    # Fallback for different installation paths
    try:
        from interfaces.api.streaming_context import StreamingContext
    except ImportError:
        import sys
        import site
        sys.path.extend(site.getsitepackages())
        from interfaces.api.streaming_context import StreamingContext

from . import context as stc_context

# Stream contexts cache
_stream_contexts: Dict[Tuple[bytes, int], StreamingContext] = {}


def create_stream_context(session_id: bytes, stream_id: int) -> StreamingContext:
    """
    Create isolated StreamingContext for stream encryption.
    
    Returns STC v0.4.0 StreamingContext directly:
    - 132.9 FPS, 7.52ms latency
    - 16-byte fixed headers via ChunkHeader
    - Lazy CEL initialization
    - Precomputed key schedules
    
    Args:
        session_id: 8-byte ephemeral session identifier
        stream_id: Stream number within session
        
    Returns:
        StreamingContext for this stream
    """
    ctx = stc_context.get_context()
    
    cache_key = (session_id, stream_id)
    
    if cache_key in _stream_contexts:
        return _stream_contexts[cache_key]
    
    # Derive stream-specific seed (no personal data)
    stream_data = session_id + stream_id.to_bytes(4, 'big')
    stream_seed = ctx.derive_key(
        length=32,
        context_data={'stream': stream_data.hex()}
    )
    
    # Create and cache StreamingContext
    stream_context = StreamingContext(stream_seed)
    _stream_contexts[cache_key] = stream_context
    
    return stream_context


def clear_stream_context(session_id: bytes, stream_id: int):
    """
    Remove cached stream context when stream closes.
    
    Args:
        session_id: Session identifier
        stream_id: Stream identifier
    """
    cache_key = (session_id, stream_id)
    _stream_contexts.pop(cache_key, None)
