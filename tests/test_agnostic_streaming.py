"""
Tests for agnostic binary streaming.

Tests that STT makes NO assumptions about data:
- Bounded/live streaming
- Out-of-order segment handling
- Binary storage (pure byte buckets)
- Multi-endpoint routing
- Event system
- Custom frames
"""

import asyncio
import pytest
from pathlib import Path

from seigr_toolset_transmissions.streaming.encoder import BinaryStreamEncoder
from seigr_toolset_transmissions.streaming.decoder import BinaryStreamDecoder
from seigr_toolset_transmissions.storage.binary_storage import BinaryStorage
from seigr_toolset_transmissions.endpoints.manager import EndpointManager
from seigr_toolset_transmissions.events.emitter import EventEmitter, STTEvents
from seigr_toolset_transmissions.frame.frame import (
    STTFrame,
    FrameDispatcher,
    FRAME_TYPE_CUSTOM_MIN,
)
from seigr_toolset_transmissions.crypto.stc_wrapper import STCWrapper


# Test seed for STC
TEST_SEED = b"test_seed_32_bytes_for_testing!!"


@pytest.fixture
def stc_wrapper():
    """Create STC wrapper for testing."""
    return STCWrapper(TEST_SEED)


@pytest.mark.asyncio
async def test_bounded_streaming(stc_wrapper):
    """Test bounded streaming (known size)."""
    session_id = b"12345678"
    stream_id = 1
    
    # Create encoder/decoder for bounded stream
    encoder = BinaryStreamEncoder(stc_wrapper, session_id, stream_id, mode='bounded')
    decoder = BinaryStreamDecoder(stc_wrapper, session_id, stream_id)
    
    # Arbitrary binary data (NOT a file, just bytes)
    test_data = b"This could be anything: audio, video, sensor data, protocol messages..."
    
    # Encode and send segments
    async for segment in encoder.send(test_data):
        # Process each segment as it's produced
        await decoder.process_segment(segment['data'], segment['sequence'])
    
    # End bounded stream
    end_marker = await encoder.end()
    if end_marker:
        await decoder.process_segment(end_marker['data'], end_marker['sequence'])
    
    decoder.signal_end()
    
    # Receive all bytes
    received = await decoder.receive_all()
    
    assert received == test_data, "Bounded stream data mismatch"


@pytest.mark.asyncio
async def test_live_streaming(stc_wrapper):
    """Test live streaming (infinite)."""
    session_id = b"87654321"
    stream_id = 2
    
    encoder = BinaryStreamEncoder(stc_wrapper, session_id, stream_id, mode='live')
    decoder = BinaryStreamDecoder(stc_wrapper, session_id, stream_id)
    
    # Simulate live data stream
    received_chunks = []
    
    async def receive_live():
        """Receive live stream chunks."""
        count = 0
        async for chunk in decoder.receive():
            received_chunks.append(chunk)
            count += 1
            if count >= 3:  # Receive 3 chunks then stop
                break
    
    # Start receiver
    receive_task = asyncio.create_task(receive_live())
    
    # Give receiver time to start
    await asyncio.sleep(0.01)
    
    # Send live data
    chunks = [b"chunk1", b"chunk2", b"chunk3", b"chunk4"]
    for chunk in chunks:
        async for segment in encoder.send(chunk):
            await decoder.process_segment(segment['data'], segment['sequence'])
    
    # Wait for receiver
    await asyncio.wait_for(receive_task, timeout=2.0)
    
    assert len(received_chunks) == 3, "Live stream should receive 3 chunks"


@pytest.mark.asyncio
async def test_out_of_order_segments(stc_wrapper):
    """Test segment reordering."""
    session_id = b"abcdefgh"
    stream_id = 3
    
    encoder = BinaryStreamEncoder(stc_wrapper, session_id, stream_id, mode='bounded', segment_size=16384)
    decoder = BinaryStreamDecoder(stc_wrapper, session_id, stream_id)
    
    test_data = b"x" * 50000  # 50KB - creates ~3-4 segments with 16KB segment size
    
    # Encode all segments first
    segments = []
    async for segment in encoder.send(test_data):
        segments.append(segment)
    
    end_marker = await encoder.end()
    if end_marker:
        segments.append(end_marker)
    
    # Receive out of order
    if len(segments) > 1:
        # Reverse order
        for segment in reversed(segments):
            await decoder.process_segment(segment['data'], segment['sequence'])
    
    decoder.signal_end()
    received = await decoder.receive_all()
    
    assert received == test_data, "Out-of-order segments should be reordered"


@pytest.mark.asyncio
async def test_binary_storage(tmp_path, stc_wrapper):
    """Test binary storage (NO file semantics)."""
    # Create storage
    storage = BinaryStorage(
        storage_path=tmp_path / "storage",
        stc_wrapper=stc_wrapper
    )
    
    # Store arbitrary binary data
    data1 = b"arbitrary binary blob 1"
    data2 = b"different data structure"
    
    # Put bytes, get address
    address1 = await storage.put(data1)
    address2 = await storage.put(data2)
    
    assert address1 != address2, "Different data should have different addresses"
    
    # Get bytes by address
    retrieved1 = await storage.get(address1)
    retrieved2 = await storage.get(address2)
    
    assert retrieved1 == data1
    assert retrieved2 == data2
    
    # List addresses
    addresses = await storage.list_addresses()
    assert address1 in addresses
    assert address2 in addresses
    
    # Remove
    await storage.remove(address1)
    addresses = await storage.list_addresses()
    assert address1 not in addresses


@pytest.mark.asyncio
async def test_multi_endpoint():
    """Test multi-endpoint routing (NO peer assumptions)."""
    manager = EndpointManager()
    
    # Register endpoints (user defines what they mean)
    endpoint1 = b"endpoint_alpha"
    endpoint2 = b"endpoint_beta"
    
    await manager.add_endpoint(endpoint1, ("addr1", 9000), {"user_key": "user_value"})
    await manager.add_endpoint(endpoint2, ("addr2", 9001), {})
    
    # Simulate receiving data (transport layer would do this)
    await manager._enqueue_received(endpoint1, b"message for alpha")
    await manager._enqueue_received(endpoint2, b"message for beta")
    
    # Receive from any
    data, from_endpoint = await manager.receive_any(timeout=1.0)
    assert from_endpoint in [endpoint1, endpoint2]
    assert len(data) > 0
    
    # Check endpoint list
    endpoints = manager.get_endpoints()
    assert endpoint1 in endpoints
    assert endpoint2 in endpoints


@pytest.mark.asyncio
async def test_events():
    """Test event system (user-defined semantics)."""
    emitter = EventEmitter()
    
    events_received = []
    
    # Register handlers
    @emitter.on(STTEvents.BYTES_RECEIVED)
    async def handle_bytes(data, endpoint_id):
        events_received.append(('bytes', data, endpoint_id))
    
    @emitter.on('custom_event')  # User-defined event
    async def handle_custom(user_data):
        events_received.append(('custom', user_data))
    
    # Emit events
    await emitter.emit(STTEvents.BYTES_RECEIVED, b"data", b"endpoint")
    await emitter.emit('custom_event', {'user': 'defined'})
    
    assert len(events_received) == 2
    assert events_received[0][0] == 'bytes'
    assert events_received[1][0] == 'custom'


@pytest.mark.asyncio
async def test_custom_frames(stc_wrapper):
    """Test custom frame types (user-defined semantics)."""
    dispatcher = FrameDispatcher()
    
    frames_handled = []
    
    # User defines custom frame type
    CUSTOM_TYPE = FRAME_TYPE_CUSTOM_MIN + 1
    
    # User defines handler
    async def handle_custom(frame: STTFrame):
        # User interprets payload however they want
        frames_handled.append(frame.payload)
    
    dispatcher.register_custom_handler(CUSTOM_TYPE, handle_custom)
    
    # Create custom frame
    frame = STTFrame.create_frame(
        frame_type=CUSTOM_TYPE,
        session_id=b"12345678",
        sequence=1,
        stream_id=1,
        payload=b"user-defined protocol data"
    )
    
    # Dispatch
    await dispatcher.dispatch(frame)
    
    assert len(frames_handled) == 1
    assert frames_handled[0] == b"user-defined protocol data"


@pytest.mark.asyncio
async def test_storage_deduplication(tmp_path, stc_wrapper):
    """Test storage automatic deduplication."""
    storage = BinaryStorage(
        storage_path=tmp_path / "dedup_storage",
        stc_wrapper=stc_wrapper
    )
    
    # Same data stored twice should return same address
    data = b"duplicate data test"
    
    addr1 = await storage.put(data)
    addr2 = await storage.put(data)
    
    assert addr1 == addr2, "Same data should deduplicate to same address"
    
    # Should only have one copy
    addresses = await storage.list_addresses()
    assert addresses.count(addr1) == 1


@pytest.mark.asyncio
async def test_storage_exists_check(tmp_path, stc_wrapper):
    """Test storage exists check."""
    storage = BinaryStorage(
        storage_path=tmp_path / "exists_storage",
        stc_wrapper=stc_wrapper
    )
    
    data = b"existence test"
    addr = await storage.put(data)
    
    assert await storage.exists(addr), "Stored data should exist"
    
    fake_addr = "0" * 64
    assert not await storage.exists(fake_addr), "Non-existent address should return False"


@pytest.mark.asyncio
async def test_storage_get_nonexistent(tmp_path, stc_wrapper):
    """Test getting non-existent data from storage."""
    from seigr_toolset_transmissions.utils.exceptions import STTStorageError
    
    storage = BinaryStorage(
        storage_path=tmp_path / "get_fail_storage",
        stc_wrapper=stc_wrapper
    )
    
    fake_addr = b"0" * 32  # 32 bytes for hash address
    
    # Should raise exception for non-existent address
    try:
        result = await storage.get(fake_addr)
        assert False, "Should have raised STTStorageError"
    except STTStorageError:
        pass  # Expected


@pytest.mark.asyncio
async def test_endpoint_remove(tmp_path):
    """Test endpoint removal."""
    manager = EndpointManager()
    
    endpoint = b"test_endpoint"
    await manager.add_endpoint(endpoint, ("addr", 8000), {})
    
    endpoints = manager.get_endpoints()
    assert endpoint in endpoints
    
    await manager.remove_endpoint(endpoint)
    
    endpoints = manager.get_endpoints()
    assert endpoint not in endpoints


@pytest.mark.asyncio
async def test_endpoint_send_to(tmp_path):
    """Test endpoint send_to method."""
    manager = EndpointManager()
    
    endpoint = b"send_endpoint"
    await manager.add_endpoint(endpoint, ("addr", 8001), {})
    
    # Send data to endpoint
    # Note: send_to is a placeholder - transport layer actually sends
    await manager.send_to(endpoint, b"test message")
    
    # Check endpoint exists and stats updated
    info = manager.get_endpoint_info(endpoint)
    assert info is not None


@pytest.mark.asyncio
async def test_endpoint_receive_timeout(tmp_path):
    """Test endpoint receive timeout."""
    manager = EndpointManager()
    
    endpoint = b"timeout_endpoint"
    await manager.add_endpoint(endpoint, ("addr", 8002), {})
    
    # Try to receive with short timeout (should raise exception)
    from seigr_toolset_transmissions.utils.exceptions import STTEndpointError
    try:
        result = await manager.receive_from(endpoint, timeout=0.1)
        assert False, "Should have raised STTEndpointError"
    except STTEndpointError:
        pass  # Expected


@pytest.mark.asyncio
async def test_events_decorator():
    """Test event decorator syntax."""
    emitter = EventEmitter()
    
    events_received = []
    
    @emitter.on('test_event')
    async def handler(data):
        events_received.append(data)
    
    # Emit - should receive
    await emitter.emit('test_event', 'data1')
    assert len(events_received) == 1


@pytest.mark.asyncio
async def test_encoder_segment_size(stc_wrapper):
    """Test encoder with custom segment size."""
    session_id = b"seg_size"
    stream_id = 5
    
    # Small segment size
    encoder = BinaryStreamEncoder(
        stc_wrapper, session_id, stream_id, 
        mode='bounded', segment_size=100
    )
    
    data = b"x" * 500  # Should create multiple segments
    
    segments = []
    async for segment in encoder.send(data):
        segments.append(segment)
    
    assert len(segments) > 1, "Large data with small segment size should create multiple segments"


@pytest.mark.asyncio
async def test_storage_remove_multiple(tmp_path, stc_wrapper):
    """Test removing multiple items from storage."""
    storage = BinaryStorage(
        storage_path=tmp_path / "remove_storage",
        stc_wrapper=stc_wrapper
    )
    
    # Store some data
    addr1 = await storage.put(b"data1")
    addr2 = await storage.put(b"data2")
    addr3 = await storage.put(b"data3")
    
    addresses = await storage.list_addresses()
    assert len(addresses) == 3
    
    # Remove items one by one
    await storage.remove(addr1)
    await storage.remove(addr2)
    
    addresses = await storage.list_addresses()
    assert len(addresses) == 1
    assert addr3 in addresses


@pytest.mark.asyncio
async def test_endpoint_metadata(tmp_path):
    """Test endpoint metadata storage and retrieval."""
    manager = EndpointManager()
    
    endpoint = b"metadata_endpoint"
    metadata = {"priority": 10, "region": "us-west", "custom": "value"}
    
    await manager.add_endpoint(endpoint, ("addr", 8003), metadata)
    
    info = manager.get_endpoint_info(endpoint)
    assert info is not None
    assert info['metadata'] == metadata
    assert info['metadata']['priority'] == 10


@pytest.mark.asyncio
async def test_endpoint_existence(tmp_path):
    """Test endpoint existence check."""
    manager = EndpointManager()
    
    endpoint = b"exists_endpoint"
    await manager.add_endpoint(endpoint, ("addr", 8004), {})
    
    endpoints = manager.get_endpoints()
    assert endpoint in endpoints, "Added endpoint should exist"
    assert b"nonexistent" not in endpoints, "Non-existent endpoint should not be in list"
