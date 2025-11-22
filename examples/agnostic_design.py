"""
Example: STT Agnostic Design - You Define Semantics

This example demonstrates how STT makes ZERO assumptions about data.
The SAME primitives work for completely different use cases.
"""

import asyncio
from seigr_toolset_transmissions.streaming.encoder import BinaryStreamEncoder
from seigr_toolset_transmissions.streaming.decoder import BinaryStreamDecoder
from seigr_toolset_transmissions.storage.binary_storage import BinaryStorage
from seigr_toolset_transmissions.endpoints.manager import EndpointManager
from seigr_toolset_transmissions.events.emitter import EventEmitter, STTEvents
from seigr_toolset_transmissions.crypto.stc_wrapper import STCWrapper


# Seed for testing
TEST_SEED = b"example_seed_32_bytes_minimum!!!"


async def example_video_streaming():
    """
    Example 1: Live video streaming
    
    STT doesn't know it's video - you define that meaning.
    """
    print("\n=== Example 1: Live Video Streaming ===")
    
    stc = STCWrapper(TEST_SEED)
    session_id = b"video001"
    stream_id = 1
    
    # Encoder/decoder for LIVE streaming (infinite)
    encoder = BinaryStreamEncoder(stc, session_id, stream_id, mode='live')
    decoder = BinaryStreamDecoder(stc, session_id, stream_id)
    
    # Simulate video frames (STT sees only bytes)
    video_frames = [
        b"<video_frame_1_h264_encoded_data>",
        b"<video_frame_2_h264_encoded_data>",
        b"<video_frame_3_h264_encoded_data>",
    ]
    
    print("Streaming video frames (STT just sees bytes)...")
    
    # Receiver task
    async def receive_video():
        frame_count = 0
        async for frame_data in decoder.receive():
            frame_count += 1
            print(f"  Received frame {frame_count}: {len(frame_data)} bytes")
            if frame_count >= 3:
                break
    
    receive_task = asyncio.create_task(receive_video())
    await asyncio.sleep(0.01)  # Let receiver start
    
    # Send frames
    for frame in video_frames:
        async for segment in encoder.send(frame):
            await decoder.process_segment(segment['data'], segment['sequence'])
    
    await receive_task
    print("✓ Video streaming complete (STT never knew it was video!)")


async def example_sensor_data():
    """
    Example 2: IoT sensor data storage
    
    STT doesn't know it's sensor data - you define that meaning.
    """
    print("\n=== Example 2: IoT Sensor Data Storage ===")
    
    import tempfile
    from pathlib import Path
    
    stc = STCWrapper(TEST_SEED)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = BinaryStorage(
            storage_path=Path(tmpdir),
            stc_wrapper=stc
        )
        
        # Simulate sensor readings (STT sees only bytes)
        sensor_data = {
            "temperature": b"25.3C",
            "humidity": b"60%",
            "pressure": b"1013hPa"
        }
        
        print("Storing sensor data (STT just sees bytes)...")
        addresses = {}
        
        for sensor_type, reading in sensor_data.items():
            address = await storage.put(reading)
            addresses[sensor_type] = address
            print(f"  Stored {sensor_type}: {address.hex()[:16]}...")
        
        # Retrieve data
        print("\nRetrieving sensor data...")
        for sensor_type, address in addresses.items():
            data = await storage.get(address)
            print(f"  Retrieved {sensor_type}: {data.decode()}")
        
        print("✓ Sensor data stored/retrieved (STT never knew it was sensor data!)")


async def example_p2p_messaging():
    """
    Example 3: P2P messaging network
    
    STT doesn't know it's messages - you define that meaning.
    """
    print("\n=== Example 3: P2P Messaging Network ===")
    
    manager = EndpointManager()
    emitter = EventEmitter()
    
    # User defines message handling (STT doesn't care)
    messages_received = []
    
    @emitter.on('message_received')
    async def handle_message(sender_id, message_text):
        messages_received.append((sender_id, message_text))
        print(f"  Message from {sender_id.decode()}: {message_text.decode()}")
    
    # Register "peers" (STT just calls them endpoints)
    peer_alice = b"peer_alice"
    peer_bob = b"peer_bob"
    
    await manager.add_endpoint(peer_alice, ("192.168.1.10", 9000), {"nickname": "Alice"})
    await manager.add_endpoint(peer_bob, ("192.168.1.20", 9000), {"nickname": "Bob"})
    
    print("Simulating P2P messages (STT just sees bytes)...")
    
    # Simulate receiving messages (transport would do this)
    await manager._enqueue_received(peer_alice, b"Hello from Alice!")
    await manager._enqueue_received(peer_bob, b"Hi from Bob!")
    
    # Receive and process
    for _ in range(2):
        data, sender_id = await manager.receive_any(timeout=1.0)
        await emitter.emit('message_received', sender_id, data)
    
    print("✓ P2P messaging complete (STT never knew they were messages!)")


async def example_custom_protocol():
    """
    Example 4: Custom binary protocol
    
    STT provides frame types 0x80-0xFF for user protocols.
    You define what they mean.
    """
    print("\n=== Example 4: Custom Binary Protocol ===")
    
    from seigr_toolset_transmissions.frame.frame import (
        STTFrame,
        FrameDispatcher,
        FRAME_TYPE_CUSTOM_MIN
    )
    
    dispatcher = FrameDispatcher()
    
    # User defines custom protocol
    MY_PROTOCOL_HANDSHAKE = FRAME_TYPE_CUSTOM_MIN + 0
    MY_PROTOCOL_DATA = FRAME_TYPE_CUSTOM_MIN + 1
    MY_PROTOCOL_ACK = FRAME_TYPE_CUSTOM_MIN + 2
    
    frames_processed = []
    
    # User defines handlers
    async def handle_handshake(frame: STTFrame):
        frames_processed.append(('handshake', frame.payload))
        print(f"  Custom handshake: {frame.payload.decode()}")
    
    async def handle_data(frame: STTFrame):
        frames_processed.append(('data', frame.payload))
        print(f"  Custom data: {len(frame.payload)} bytes")
    
    async def handle_ack(frame: STTFrame):
        frames_processed.append(('ack', frame.payload))
        print(f"  Custom ack: {frame.payload.decode()}")
    
    # Register handlers
    dispatcher.register_custom_handler(MY_PROTOCOL_HANDSHAKE, handle_handshake)
    dispatcher.register_custom_handler(MY_PROTOCOL_DATA, handle_data)
    dispatcher.register_custom_handler(MY_PROTOCOL_ACK, handle_ack)
    
    print("Processing custom protocol frames (STT just dispatches)...")
    
    # Create and dispatch custom frames
    frames = [
        STTFrame.create_frame(MY_PROTOCOL_HANDSHAKE, b"12345678", 1, 1, b"HELLO_V1"),
        STTFrame.create_frame(MY_PROTOCOL_DATA, b"12345678", 2, 1, b"<custom_data>"),
        STTFrame.create_frame(MY_PROTOCOL_ACK, b"12345678", 3, 1, b"OK"),
    ]
    
    for frame in frames:
        await dispatcher.dispatch(frame)
    
    print("✓ Custom protocol complete (STT just provided frame types!)")


async def main():
    """
    Run all examples showing STT's agnostic design.
    
    The SAME primitives work for video, sensors, messages, and custom protocols.
    STT never assumes what the data means - that's YOUR job.
    """
    print("=" * 70)
    print("STT AGNOSTIC DESIGN EXAMPLES")
    print("=" * 70)
    print("\nSTT Principle: Secure Binary Transport Protocol")
    print("What you send is YOUR business, not STT's.")
    print("=" * 70)
    
    await example_video_streaming()
    await example_sensor_data()
    await example_p2p_messaging()
    await example_custom_protocol()
    
    print("\n" + "=" * 70)
    print("ALL EXAMPLES COMPLETE")
    print("=" * 70)
    print("\nKey Takeaway:")
    print("  STT provides primitives (streaming, storage, endpoints, events)")
    print("  YOU define semantics (video, sensors, messages, protocols)")
    print("  Zero assumptions = Maximum flexibility")
    print("=" * 70)


if __name__ == '__main__':
    asyncio.run(main())
