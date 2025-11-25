# Chapter 20: Streams & StreamManager

**Version**: 0.2.0a0 (unreleased)  
**Components**: `STTStream`, `StreamManager`  
**Test Coverage**: 98.61-99.24%

---

## Overview

**Streams** enable multiplexed communication channels within a single session. Think of a session as a phone line, and streams as multiple conversations over that line.

**STTStream** - Single multiplexed channel  
**StreamManager** - Manages multiple streams per session

---

## Why Use Streams?

Instead of this:

```python
# Multiple sessions for different data types ✗
session1 = await node.connect_udp(peer, 8080)  # For control
session2 = await node.connect_udp(peer, 8081)  # For file transfer
session3 = await node.connect_udp(peer, 8082)  # For video
```

Do this:

```python
# One session, multiple streams ✓
session = await node.connect_udp(peer, 8080)

stream_control = await node.create_stream(session.session_id, stream_id=0)
stream_files = await node.create_stream(session.session_id, stream_id=1)
stream_video = await node.create_stream(session.session_id, stream_id=2)
```

**Benefits**:

- Single handshake (faster setup)
- Shared encryption context (more efficient)
- Priority management across streams
- Flow control per stream

---

## Creating Streams

### Explicit Stream Creation

```python
# Create stream on existing session
stream = await node.create_stream(
    session_id=session.session_id,
    stream_id=1  # Your choice (0-4294967295)
)

# Stream ready to use
print(f"Stream {stream.stream_id} created")
```

### Implicit Stream 0

Every session has **stream 0** automatically:

```python
# When you send without specifying stream
await node.send_to_sessions([session_id], b"Data")

# Uses stream 0 implicitly
```

---

## Sending on Streams

### Small Data (Single Message)

```python
# Send data on stream
await stream.send(b"Hello on stream 1")

# Data automatically:
# 1. Encrypted with stream context
# 2. Fragmented if needed
# 3. Sent with correct stream_id
```

### Large Data (Fragmented)

```python
# Send large file (auto-fragmented)
large_data = open('big_file.bin', 'rb').read()

await stream.send_all(large_data)

# Automatically:
# - Split into 64 KB segments
# - Each segment becomes a frame
# - Sent with sequence numbers
# - Receiver reassembles
```

---

## Receiving from Streams

### Receive Single Message

```python
# Receive next message
data = await stream.receive()

print(f"Received: {data}")
```

### Receive with Timeout

```python
import asyncio

try:
    data = await stream.receive(timeout=5.0)
except asyncio.TimeoutError:
    print("No data received in 5 seconds")
```

### Continuous Reception

```python
# Receive loop
while stream.is_active:
    try:
        data = await stream.receive(timeout=1.0)
        await process_data(data)
    except asyncio.TimeoutError:
        continue  # Keep waiting
```

---

## StreamManager - Managing Multiple Streams

### Accessing StreamManager

```python
# Via STTNode
manager = node.stream_manager
```

### Creating Stream via Manager

```python
stream = await manager.create_stream(
    session_id=session.session_id,
    stream_id=1,
    stc_wrapper=node.stc
)
```

### Getting Existing Stream

```python
# Get stream by ID
stream = manager.get_stream(session_id, stream_id=1)

if stream:
    print("Stream exists")
else:
    print("Stream not found")
```

### Listing All Streams

```python
# Get all streams for a session
streams = manager.get_streams(session_id)

print(f"Active streams: {len(streams)}")
for stream in streams:
    print(f"  Stream {stream.stream_id}: {stream.bytes_sent} bytes sent")
```

### Closing Streams

```python
# Close specific stream
await manager.close_stream(session_id, stream_id=1)

# Close all streams for session
await manager.close_all_streams(session_id)
```

---

## Complete Example: File Transfer

```python
import asyncio
from seigr_toolset_transmissions import STTNode

async def file_transfer_example():
    shared_seed = b"shared_secret_32bytes_minimum!"
    
    # Create nodes
    server = STTNode(
        node_seed=b"server" * 8,
        shared_seed=shared_seed,
        port=8080
    )
    
    client = STTNode(
        node_seed=b"client" * 8,
        shared_seed=shared_seed,
        port=0
    )
    
    await server.start(server_mode=True)
    await client.start()
    
    # Connect
    session = await client.connect_udp("localhost", 8080)
    
    # Create dedicated stream for file transfer
    file_stream = await client.create_stream(session.session_id, stream_id=10)
    
    # Load file
    file_data = b"X" * (1024 * 1024)  # 1 MB file
    
    print(f"Sending {len(file_data)} bytes on stream {file_stream.stream_id}")
    
    # Send (auto-fragmented)
    await file_stream.send_all(file_data)
    
    print(f"Transfer complete!")
    print(f"  Bytes sent: {file_stream.bytes_sent}")
    print(f"  Messages sent: {file_stream.messages_sent}")
    
    # Close stream
    await client.stream_manager.close_stream(session.session_id, stream_id=10)
    
    # Cleanup
    await client.stop()
    await server.stop()

asyncio.run(file_transfer_example())
```

---

## Stream Priority

Control which streams get bandwidth priority:

```python
# Set stream priority (0-1000)
stream.current_priority = 900  # High priority

# Lower priority for background tasks
background_stream.current_priority = 100

# Scheduler sends high-priority streams first
```

### Adaptive Priority

Priority can change dynamically:

```python
# Initial priority
stream.current_priority = 500  # Medium

# Boost for interactive data
if user_interaction:
    stream.current_priority = 900

# Lower for bulk transfer
if bulk_data:
    stream.current_priority = 200
```

---

## Flow Control

Streams have send/receive windows for flow control:

```python
# Check flow control windows
print(f"Send window: {stream.send_window} bytes")
print(f"Receive window: {stream.receive_window} bytes")

# Windows adjust based on network conditions
# (automatic - no manual control needed)
```

---

## Stream Statistics

Get stream performance metrics:

```python
stats = stream.get_statistics()

# Returns dict:
{
    'stream_id': 1,
    'session_id': '1a2b3c4d5e6f7a8b',
    'is_active': True,
    'bytes_sent': 1024000,
    'bytes_received': 512000,
    'messages_sent': 50,
    'messages_received': 25,
    'sequence': 50,
    'expected_sequence': 25,
    'created_at': 1700000000.0,
    'last_activity': 1700000120.0,
    'uptime': 120.0
}
```

---

## Ordered Delivery

Streams ensure messages arrive in order:

```python
# Sender
await stream.send(b"Message 1")  # seq=0
await stream.send(b"Message 2")  # seq=1
await stream.send(b"Message 3")  # seq=2

# Receiver gets them in order
msg1 = await stream.receive()  # seq=0
msg2 = await stream.receive()  # seq=1
msg3 = await stream.receive()  # seq=2
```

**How?** Stream buffers out-of-order messages:

```python
# If messages arrive: 0, 2, 1
# - Message 0: delivered immediately
# - Message 2: buffered (waiting for 1)
# - Message 1: delivered, then message 2 delivered
```

---

## Fragmentation

Large messages are automatically fragmented:

```python
# Send 10 MB data
huge_data = b"X" * (10 * 1024 * 1024)

# Automatically split into 64 KB chunks
await stream.send_all(huge_data)

# Fragments sent as individual frames
# Receiver reassembles automatically
```

### Segment Size

```python
# Default segment size: 64 KB
DEFAULT_SEGMENT_SIZE = 65536

# Configurable in BinaryStreamEncoder
from seigr_toolset_transmissions.binary_streaming import BinaryStreamEncoder

encoder = BinaryStreamEncoder(segment_size=32768)  # 32 KB segments
```

See [Chapter 24: Binary Streaming](24_binary_streaming.md) for details.

---

## Stream States

```python
# Active stream
stream.is_active = True

# Close stream
await stream.close()

# Closed stream
stream.is_active = False

# Attempt to use closed stream
try:
    await stream.send(b"Data")
except STTStreamError:
    print("Stream is closed!")
```

---

## Common Patterns

### Stream Pool

```python
class StreamPool:
    def __init__(self, node, session_id):
        self.node = node
        self.session_id = session_id
        self.next_stream_id = 1
    
    async def acquire(self):
        """Get available stream"""
        stream_id = self.next_stream_id
        self.next_stream_id += 1
        
        return await self.node.create_stream(
            self.session_id,
            stream_id
        )
    
    async def release(self, stream_id):
        """Return stream to pool"""
        await self.node.stream_manager.close_stream(
            self.session_id,
            stream_id
        )

# Usage
pool = StreamPool(node, session.session_id)
stream = await pool.acquire()
await stream.send(b"Data")
await pool.release(stream.stream_id)
```

### Request-Response Pattern

```python
async def rpc_call(node, session_id, request: bytes):
    """RPC over dedicated stream"""
    # Create ephemeral stream
    stream_id = random.randint(1000, 9999)
    stream = await node.create_stream(session_id, stream_id)
    
    # Send request
    await stream.send(request)
    
    # Wait for response
    response = await stream.receive(timeout=10.0)
    
    # Close stream
    await node.stream_manager.close_stream(session_id, stream_id)
    
    return response
```

### Broadcast to All Streams

```python
async def broadcast_to_streams(node, session_id, data: bytes):
    """Send to all active streams"""
    streams = node.stream_manager.get_streams(session_id)
    
    tasks = []
    for stream in streams:
        tasks.append(stream.send(data))
    
    # Send concurrently
    await asyncio.gather(*tasks)
```

---

## Troubleshooting

### "Stream not found"

**Problem**: `manager.get_stream()` returns `None`

**Causes**:

- Stream not created yet
- Stream already closed
- Wrong stream_id

**Solution**: Create stream before use:

```python
stream = manager.get_stream(session_id, stream_id=1)
if not stream:
    stream = await manager.create_stream(session_id, 1, node.stc)
```

### Receive Timeout

**Problem**: `stream.receive()` times out

**Causes**:

- No data sent on stream
- Stream closed by peer
- Network issue

**Solution**: Check stream state:

```python
if not stream.is_active:
    print("Stream closed!")
else:
    # Network issue or no data
    pass
```

### Out-of-Order Messages

**Problem**: Messages buffered but not delivered

**Cause**: Missing sequence number (packet loss)

**Solution**: Stream will deliver when gap filled, but you can detect:

```python
# Check for buffering
if stream.out_of_order_buffer:
    print(f"Waiting for {len(stream.out_of_order_buffer)} messages")
```

---

## Performance Considerations

**Stream Overhead**:

- Stream object: ~500 bytes
- Per-message: 4 bytes (stream_id in frame header)
- No additional encryption cost (shared session key)

**Concurrency**:

- Unlimited concurrent streams per session
- Each stream independent send/receive
- Priority scheduler manages bandwidth

**Throughput**:

- Per-stream: Limited by session throughput (~100 MB/s)
- Multiple streams: Share session bandwidth
- Priority affects scheduling, not total bandwidth

**Memory**:

- Receive buffer: ~64 KB per stream (for out-of-order messages)
- Send buffer: Minimal (streams send immediately)

---

## Related Documentation

- **[Chapter 16: STTNode](16_sttnode.md)** - Creates streams
- **[Chapter 17: Sessions](17_sessions.md)** - Streams belong to sessions
- **[Chapter 19: Frames](19_frames.md)** - Stream data sent in frames
- **[Chapter 24: Binary Streaming](24_binary_streaming.md)** - Fragmentation details
- **[API Reference](../api/API.md#streams)** - Complete API

---

**Document Version**: 0.2.0a0 (unreleased)  
**Last Updated**: November 25, 2025
