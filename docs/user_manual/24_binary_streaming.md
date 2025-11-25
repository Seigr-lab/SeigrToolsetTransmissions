# Chapter 24: Binary Streaming

**Version**: 0.2.0a0 (unreleased)  
**Components**: `BinaryStreamEncoder`, `BinaryStreamDecoder`  
**Test Coverage**: 96-100%

---

## Overview

**Binary streaming** handles sending/receiving large or continuous data by breaking it into segments and reassembling on the receiver side.

**BinaryStreamEncoder** - Splits data into encrypted segments  
**BinaryStreamDecoder** - Reassembles segments into original data

**Agnostic Design**: STT doesn't care what bytes represent - files, messages, video, user decides.

---

## Why Binary Streaming?

Without streaming:

```python
# Problem: Can't send 1 GB file as one frame
huge_file = open('1GB_file.bin', 'rb').read()
frame = STTFrame(payload=huge_file)  # ✗ Exceeds max frame size
```

With streaming:

```python
# Solution: Stream automatically fragments
stream = await node.create_stream(session_id, stream_id=1)
await stream.send_all(huge_file)  # ✓ Automatic segmentation
```

---

## Stream Modes

### Live Streaming

For infinite/unbounded data (e.g., sensor data, video):

```python
encoder = BinaryStreamEncoder(
    stc_wrapper=node.stc,
    session_id=session.session_id,
    stream_id=1,
    mode='live'  # No end expected
)

# Send continuously
while True:
    sensor_data = read_sensor()
    async for segment in encoder.send(sensor_data):
        await transport.send(segment)
```

### Bounded Streaming

For finite data with known or unknown size:

```python
encoder = BinaryStreamEncoder(
    stc_wrapper=node.stc,
    session_id=session.session_id,
    stream_id=1,
    mode='bounded'  # Will eventually end
)

# Send file
file_data = open('file.bin', 'rb').read()

async for segment in encoder.send(file_data):
    await transport.send(segment)

# Signal end
async for segment in encoder.end():
    await transport.send(segment)
```

---

## Segmentation

### Segment Size

```python
# Default: 64 KB segments
encoder = BinaryStreamEncoder(segment_size=65536, ...)

# Smaller segments (lower latency)
encoder = BinaryStreamEncoder(segment_size=1024, ...)  # 1 KB

# Larger segments (higher throughput)
encoder = BinaryStreamEncoder(segment_size=1048576, ...)  # 1 MB
```

**Tradeoff**:

- **Small segments**: Lower latency, more overhead
- **Large segments**: Higher throughput, higher latency

### How Segmentation Works

```python
# Input: 200 KB data
data = b"X" * (200 * 1024)

# With 64 KB segments:
# Segment 0: bytes 0-65535 (64 KB)
# Segment 1: bytes 65536-131071 (64 KB)
# Segment 2: bytes 131072-196607 (64 KB)
# Segment 3: bytes 196608-204799 (8 KB) - final partial

# Each segment:
# - Encrypted separately
# - Has sequence number
# - Sent as individual frame
```

---

## Encoding (Sending)

### Basic Encoding

```python
from seigr_toolset_transmissions.streaming import BinaryStreamEncoder

# Create encoder
encoder = BinaryStreamEncoder(
    stc_wrapper=node.stc,
    session_id=session.session_id,
    stream_id=1,
    segment_size=65536,
    mode='bounded'
)

# Send data
data = b"Data to send"

async for segment in encoder.send(data):
    # segment is a dict with:
    # {
    #     'sequence': int,
    #     'data': bytes (encrypted),
    #     'session_id': bytes,
    #     'stream_id': int,
    #     'is_final': bool
    # }
    
    await send_to_transport(segment)
```

### Ending Stream

```python
# Signal end of bounded stream
async for segment in encoder.end():
    await send_to_transport(segment)

# Decoder knows stream is complete
```

---

## Decoding (Receiving)

### Basic Decoding

```python
from seigr_toolset_transmissions.streaming import BinaryStreamDecoder

# Create decoder
decoder = BinaryStreamDecoder(
    stc_wrapper=node.stc,
    session_id=session.session_id,
    stream_id=1
)

# Receive segments
while True:
    segment = await receive_from_transport()
    
    # Feed segment to decoder
    data_chunk = await decoder.receive(segment)
    
    if data_chunk:
        # Got reassembled data
        process_data(data_chunk)
    
    if decoder.is_complete():
        break  # Stream ended
```

### Handling Out-of-Order Delivery

Decoder automatically handles segments arriving out-of-order:

```python
# Segments arrive: 0, 2, 1 (out of order)

decoder.receive(segment_0)  # Returns data immediately
decoder.receive(segment_2)  # Buffered (waiting for 1)
decoder.receive(segment_1)  # Returns buffered data in order

# User always gets data in correct order
```

---

## Complete Example: File Transfer

```python
import asyncio
from seigr_toolset_transmissions import STTNode
from seigr_toolset_transmissions.streaming import (
    BinaryStreamEncoder,
    BinaryStreamDecoder
)

async def file_transfer_example():
    shared_seed = b"shared_secret_32bytes_minimum!"
    
    # Server
    server = STTNode(
        node_seed=b"server" * 8,
        shared_seed=shared_seed,
        port=8080
    )
    await server.start(server_mode=True)
    
    # Client
    client = STTNode(
        node_seed=b"client" * 8,
        shared_seed=shared_seed,
        port=0
    )
    await client.start()
    
    # Connect
    session = await client.connect_udp("localhost", 8080)
    
    # === SENDER (client) ===
    
    # Create encoder
    encoder = BinaryStreamEncoder(
        stc_wrapper=client.stc,
        session_id=session.session_id,
        stream_id=1,
        segment_size=65536,
        mode='bounded'
    )
    
    # Prepare file
    file_data = b"FILE CONTENTS" * 100000  # ~1.3 MB
    
    print(f"Sending {len(file_data)} bytes...")
    
    # Send file
    segments_sent = 0
    async for segment in encoder.send(file_data):
        # Send segment
        await client.send_to_sessions([session.session_id], segment['data'])
        segments_sent += 1
    
    # End stream
    async for segment in encoder.end():
        await client.send_to_sessions([session.session_id], segment['data'])
    
    print(f"Sent {segments_sent} segments")
    
    # === RECEIVER (server) ===
    
    # Create decoder
    decoder = BinaryStreamDecoder(
        stc_wrapper=server.stc,
        session_id=session.session_id,
        stream_id=1
    )
    
    # Receive and reassemble
    received_data = b""
    
    async for packet in server.receive():
        chunk = await decoder.receive(packet.payload)
        
        if chunk:
            received_data += chunk
        
        if decoder.is_complete():
            break
    
    print(f"Received {len(received_data)} bytes")
    print(f"Match: {received_data == file_data}")
    
    # Cleanup
    await client.stop()
    await server.stop()

asyncio.run(file_transfer_example())
```

---

## Flow Control

Encoder uses **credit-based flow control** to prevent overwhelming receiver:

```python
# Encoder has credits (default: 100 segments)
encoder._credits = 100

# Each send() consumes a credit
async for segment in encoder.send(data):
    # Credit consumed
    pass

# When credits exhausted, encoder waits
# Receiver grants credits via ACKs (automatic)
```

**Why?** Prevents sender from flooding slow receiver.

---

## Sequence Numbers

Each segment has sequence number for ordering:

```python
# Segment structure
{
    'sequence': 0,  # First segment
    'data': b'...',
    'is_final': False
}

# Next segment
{
    'sequence': 1,
    'data': b'...',
    'is_final': False
}

# Last segment
{
    'sequence': N,
    'data': b'...',
    'is_final': True  # Signals end
}
```

---

## Statistics

### Encoder Statistics

```python
stats = encoder.get_statistics()

# Returns:
{
    'total_bytes_sent': 1048576,
    'sequence': 16,
    'mode': 'bounded',
    'ended': False,
    'credits': 84
}
```

### Decoder Statistics

```python
stats = decoder.get_statistics()

# Returns:
{
    'total_bytes_received': 1048576,
    'expected_sequence': 16,
    'out_of_order_count': 2,
    'complete': False
}
```

---

## Common Patterns

### Streaming Iterator

```python
async def stream_generator(file_path):
    """Stream file in chunks"""
    encoder = BinaryStreamEncoder(
        stc_wrapper=node.stc,
        session_id=session_id,
        stream_id=1,
        mode='bounded'
    )
    
    # Read and stream file
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(65536)  # 64 KB chunks
            if not chunk:
                break
            
            async for segment in encoder.send(chunk):
                yield segment
    
    # End stream
    async for segment in encoder.end():
        yield segment

# Usage
async for segment in stream_generator('large_file.bin'):
    await send_segment(segment)
```

### Reassembly with Callback

```python
class StreamReceiver:
    def __init__(self, decoder, on_data):
        self.decoder = decoder
        self.on_data = on_data  # Callback for each chunk
    
    async def handle_segment(self, segment):
        """Process incoming segment"""
        data_chunk = await self.decoder.receive(segment)
        
        if data_chunk:
            await self.on_data(data_chunk)
        
        return self.decoder.is_complete()

# Usage
async def save_chunk(chunk):
    with open('output.bin', 'ab') as f:
        f.write(chunk)

receiver = StreamReceiver(decoder, on_data=save_chunk)

while not await receiver.handle_segment(segment):
    segment = await get_next_segment()
```

---

## Troubleshooting

### Segments Not Reassembling

**Problem**: Decoder doesn't return data

**Cause**: Missing sequence numbers (packet loss)

**Solution**: Check decoder state:

```python
stats = decoder.get_statistics()
print(f"Expected sequence: {stats['expected_sequence']}")
print(f"Out of order: {stats['out_of_order_count']}")

# If out_of_order_count grows, packets are missing
```

### Stream Never Ends

**Problem**: `decoder.is_complete()` never returns `True`

**Cause**: Encoder didn't call `end()`

**Solution**: Always end bounded streams:

```python
# Encoder side
async for segment in encoder.send(data):
    await send(segment)

# Must call end() for bounded streams
async for segment in encoder.end():  # ✓ Don't forget!
    await send(segment)
```

### High Memory Usage

**Problem**: Decoder using lots of memory

**Cause**: Many out-of-order segments buffered

**Solution**: Process data as it arrives:

```python
# Bad: Accumulate all data
received_data = b""
async for chunk in decoder.receive_all():
    received_data += chunk  # ✗ Grows unbounded

# Good: Process chunks immediately
async for chunk in decoder.receive_all():
    process_chunk(chunk)  # ✓ Constant memory
```

---

## Performance Considerations

**Segment Size Impact**:

- **1 KB segments**: ~1000 segments/sec, low latency (~1ms per segment)
- **64 KB segments**: ~100 segments/sec, high throughput (~6.4 MB/sec)
- **1 MB segments**: ~10 segments/sec, maximum throughput (~10 MB/sec)

**Encryption Overhead**:

- Per segment: ~0.5ms encryption
- Stream context reuse: ~0.1ms (cached)
- Total: Minimal impact on throughput

**Memory Usage**:

- Encoder: ~segment_size bytes
- Decoder: ~segment_size * buffered_segments bytes
- Typical: 64 KB to 1 MB memory

---

## Related Documentation

- **[Chapter 19: Frames](19_frames.md)** - Frame structure carrying segments
- **[Chapter 20: Streams](20_streams.md)** - Stream multiplexing
- **[Chapter 23: Cryptography](23_cryptography.md)** - Segment encryption
- **[API Reference](../api/API.md#streaming)** - Complete API

---

**Document Version**: 0.2.0a0 (unreleased)  
**Last Updated**: November 25, 2025
