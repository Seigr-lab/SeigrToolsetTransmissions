"""
Test configuration for pytest.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from seigr_toolset_transmissions.crypto import STCWrapper


@pytest.fixture(scope="function")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    # Clean up all pending tasks
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()


@pytest.fixture
def test_seed():
    """Shared seed for testing."""
    return b"test_seed_32_bytes_minimum!!!!!"


@pytest.fixture
def stc_wrapper(test_seed):
    """STC wrapper with test seed."""
    return STCWrapper(test_seed)


@pytest.fixture
def temp_dir():
    """Temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_node_id():
    """Test node ID."""
    return b'\x01' * 32


@pytest.fixture
def test_session_id():
    """Test session ID."""
    return b'\x01\x02\x03\x04\x05\x06\x07\x08'


@pytest.fixture
def peer_node_id():
    """Peer node ID for testing."""
    return b'\x02' * 32
