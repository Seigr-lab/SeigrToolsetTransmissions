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
