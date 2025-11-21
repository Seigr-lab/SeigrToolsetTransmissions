# Chapter 7: Streams and Multiplexing

## Introduction

**Streams** allow multiple independent data flows within a single STT session. This chapter explains how STT multiplexes streams, guarantees ordering, handles flow control, and enables efficient concurrent communication.

**Key insight:** One session can carry many streams simultaneously - like multiple phone conversations on the same phone line using different "channels."

## What Are Streams?

### The Basic Concept

**Stream** = Ordered sequence of data within a session

```
         Session (Encrypted Channel)
+--------------------------------------------------+
|  Stream 1: Video frames →→→                     |
|  Stream 2: Audio samples →→→                    |
|  Stream 3: Chat messages →→→                    |
+--------------------------------------------------+
            All encrypted, multiplexed
```

**Properties:**

- **Ordered**: Data arrives in same order sent (per stream)
- **Independent**: Stream 1 doesn't block Stream 2
- **Bidirectional**: Both peers can send on any stream
- **Lightweight**: Minimal overhead per stream

**Analogy:** Streams are like lanes on a highway - vehicles (data) in each lane proceed independently, don't interfere with other lanes.

### Why Multiple Streams?

**Problem without streams:**

```
Send video frame (10 KB) → blocked until sent
Send audio sample (1 KB) → waiting...
Send chat message (100 bytes) → waiting...
```

**Head-of-line blocking**: Large data blocks small data

**Solution with streams:**

```
Stream 1: Send video frame (10 KB) → sending...
Stream 2: Send audio sample (1 KB) → sent! (not blocked)
Stream 3: Send chat message (100 bytes) → sent! (not blocked)
```

**Multiplexing**: Interleave frames from all streams

## Stream Lifecycle

### Opening a Stream

```python
# Open stream (either peer can initiate)
stream = session.open_stream(
    stream_id=1,              # Optional: specific ID (auto-assigned if omitted)
    purpose='video_transfer'  # Optional: human-readable label
)
```

**Stream ID:**

- 16-bit integer (0-65535 range)
- Unique per session
- Both peers must agree (handshake on first frame)

**Auto-assignment:**

```python
stream1 = session.open_stream()  # Gets stream_id=1 (auto)
stream2 = session.open_stream()  # Gets stream_id=2 (auto)
```

### Sending Data

```python
# Send bytes on stream
await stream.send(b"Hello, world!")

# Send large data (automatic chunking)
await stream.send(large_file_bytes)  # 100 MB - chunked into frames
```

**Chunking** (automatic):

- STT splits large data into frames (default 16 KB)
- Sends frames sequentially
- Receiver reassembles automatically

**Non-blocking** (async):

- `await stream.send()` returns when data buffered (not necessarily sent)
- Use `await stream.flush()` to ensure transmission

### Receiving Data

```python
# Receive next chunk
data = await stream.receive()  # Blocks until data available

# Receive with timeout
try:
    data = await asyncio.wait_for(stream.receive(), timeout=5.0)
except asyncio.TimeoutError:
    print("No data received in 5 seconds")
```

**Ordering guarantee:**

```python
await stream.send(b"First")
await stream.send(b"Second")
await stream.send(b"Third")

# Receiver gets:
data1 = await stream.receive()  # b"First"
data2 = await stream.receive()  # b"Second"
data3 = await stream.receive()  # b"Third"
```

**Always in order** (per stream) - even if network reorders packets.

### Closing a Stream

```python
# Graceful close (sends all buffered data first)
await stream.close()

# Check if stream closed
if stream.is_closed():
    print("Stream closed")
```

**Bidirectional close:**

- Either peer can close stream
- Closing sends `STREAM_FIN` frame to peer
- Peer acknowledges, closes their end
- Both ends cleaned up

**Session remains open** - can open new streams on same session.

## Multiplexing Mechanism

### Frame Interleaving

**STT sends frames from all streams interleaved:**

```
Time →

Frame: Stream 1, Seq 1, 16 KB video
Frame: Stream 2, Seq 1, 1 KB audio
Frame: Stream 1, Seq 2, 16 KB video
Frame: Stream 3, Seq 1, 100 bytes chat
Frame: Stream 1, Seq 3, 16 KB video
Frame: Stream 2, Seq 2, 1 KB audio
...
```

**Receiver demultiplexes:**

- Uses `stream_id` field in frame header
- Routes to correct stream
- Reassembles in order (using `sequence_number`)

### Frame Priority

**Current v0.2.0-alpha:** Simple round-robin (fair)

**Future (v0.6.0+):** Priority levels

```python
stream_video = session.open_stream(priority=10)  # High priority
stream_chat = session.open_stream(priority=1)    # Low priority
```

**Priority affects send order** (high-priority streams get more frames sent first).

### Flow Control

**Per-stream flow control** prevents fast sender overwhelming slow receiver:

```python
# Sender (fast)
for i in range(1000):
    await stream.send(large_chunk)
    # If receiver slow, send() blocks automatically (backpressure)
```

**Mechanism:**

- Receiver advertises "window size" (how much data it can buffer)
- Sender tracks window, pauses if full
- Receiver consumes data, sends window updates
- Sender resumes

**Automatic** - application doesn't manage windows manually.

## Stream Patterns

### Unidirectional Streams

**One-way data flow:**

```python
# Sender
stream = session.open_stream()
await stream.send(b"Data")
await stream.send(b"More data")
await stream.close()

# Receiver
stream = session.get_stream(stream_id=1)  # Get when first frame arrives
data1 = await stream.receive()
data2 = await stream.receive()
# stream.receive() blocks forever if sender doesn't close
```

**Use case:** File transfer (sender sends file, receiver saves)

### Bidirectional Streams

**Both peers send and receive:**

```python
# Peer A
stream = session.open_stream()
await stream.send(b"Request: GET /file")
response = await stream.receive()
await stream.close()

# Peer B (simultaneously)
stream = session.get_stream(stream_id=1)
request = await stream.receive()
await stream.send(b"Response: Here's the file")
```

**Use case:** RPC (request-response pattern)

### Long-Lived Streams

**Keep stream open indefinitely:**

```python
# Streaming video
stream = session.open_stream()
while True:
    frame = capture_video_frame()
    await stream.send(frame)
    await asyncio.sleep(0.033)  # 30 FPS
```

**Receiver:**

```python
stream = session.get_stream(stream_id=1)
while True:
    frame = await stream.receive()
    display_video_frame(frame)
```

**Never closed** (until session ends) - continuous streaming.

## Stream Ordering and Reliability

### Sequence Numbers

**Each frame has sequence number:**

```
Stream 1, Seq 0, Data: "Hello"
Stream 1, Seq 1, Data: " World"
Stream 1, Seq 2, Data: "!"
```

**Receiver reorders if needed:**

```
Received: Seq 1, Seq 0, Seq 2 (out of order)
Reordered: Seq 0, Seq 1, Seq 2 (correct order)
Delivered: "Hello World!" ✓
```

**Transparent to application** - always receives in order.

### Retransmission

**Lost frames automatically retransmitted:**

```
Sender: Send Seq 0, Seq 1, Seq 2
Network: Seq 1 lost! (packet drop)
Receiver: Receives Seq 0, Seq 2 (gap detected)
Receiver: Sends NACK for Seq 1
Sender: Retransmits Seq 1
Receiver: Receives Seq 1, delivers all in order
```

**NACK (Negative Acknowledgment):**

- Receiver requests missing frames
- Faster than timeout-based retransmission

**Configurable timeout:**

```python
stream = session.open_stream(
    retransmit_timeout=0.1  # 100ms (default)
)
```

### Acknowledgments

**STT uses selective acknowledgments (SACK):**

```
Received: Seq 0, 1, 2, 3, 4, 5
Send ACK: "I have 0-5"

Received: Seq 6, 8, 9 (missing 7)
Send SACK: "I have 0-6, 8-9, missing 7"
```

**Efficient** - avoids retransmitting already-received frames.

## Performance Optimization

### Frame Size Tuning

**Trade-off:**

**Small frames (4 KB):**

- ✅ Low latency (quick to send)
- ✅ Better multiplexing (more interleaving)
- ❌ Higher overhead (more headers)

**Large frames (64 KB):**

- ✅ Higher throughput (less overhead)
- ✅ Fewer frames to track
- ❌ Higher latency per frame
- ❌ Head-of-line blocking (large frame blocks others)

**Recommendation:**

```python
# Low-latency chat
stream_chat = session.open_stream(max_frame_size=4096)  # 4 KB

# High-throughput file transfer
stream_file = session.open_stream(max_frame_size=65536)  # 64 KB

# Balanced video streaming
stream_video = session.open_stream(max_frame_size=16384)  # 16 KB (default)
```

### Send Buffering

**STT buffers data before framing:**

```python
stream = session.open_stream(send_buffer_size=1048576)  # 1 MB buffer

# Send small chunks (buffered)
for chunk in small_chunks:
    await stream.send(chunk)  # Returns immediately (buffered)

# Force transmission
await stream.flush()  # Actually sends buffered data
```

**Nagle-like algorithm:**

- Buffers small writes
- Sends full frames when possible
- Reduces overhead

**Disable buffering** (for low-latency):

```python
stream = session.open_stream(no_delay=True)  # Send immediately
```

### Receive Buffering

**Receiver buffers frames until application reads:**

```python
stream = session.open_stream(recv_buffer_size=2097152)  # 2 MB buffer

# Slow consumer
while True:
    data = await stream.receive()
    process_data_slowly(data)  # Takes time
```

**Backpressure:**

- If buffer fills, flow control stops sender
- Prevents memory overflow

**Larger buffer = less backpressure** (more tolerance for bursts)

## Stream Limits

### Maximum Concurrent Streams

**STT limits concurrent streams per session:**

```python
node = STTNode(
    max_concurrent_streams=256  # Default: 256
)
```

**Why limit?**

- Memory usage (each stream has buffers)
- CPU overhead (demultiplexing)
- Fairness (prevent one session monopolizing resources)

**Exceeding limit:**

```python
try:
    stream = session.open_stream()
except TooManyStreamsError:
    print("Max concurrent streams reached")
    # Wait for some streams to close, then retry
```

### Stream Data Limits

**No inherent limit on stream size** - can transfer gigabytes on one stream:

```python
# Transfer 10 GB file
with open('10GB_file.dat', 'rb') as f:
    stream = session.open_stream()
    while True:
        chunk = f.read(1048576)  # 1 MB chunks
        if not chunk:
            break
        await stream.send(chunk)
    await stream.close()
```

**Practical limits:**

- Network bandwidth (takes time)
- Session timeout (if transfer too slow)
- Disk space (receiver must store)

## Error Handling

### Stream-Level Errors

```python
try:
    await stream.send(data)
except StreamClosedError:
    print("Stream closed (peer or local)")
except SessionClosedError:
    print("Entire session closed (fatal)")
except TimeoutError:
    print("Send timeout (no acknowledgment)")
```

**StreamClosedError:**

- Specific stream closed (others may still work)
- Can open new stream on same session

**SessionClosedError:**

- Entire session dead (all streams closed)
- Must create new session

### Handling Backpressure

```python
# Send with timeout (avoid infinite blocking)
try:
    await asyncio.wait_for(stream.send(data), timeout=30.0)
except asyncio.TimeoutError:
    print("Send blocked for 30s (receiver slow)")
    # Either wait longer or abort
```

**Receiver-side backpressure:**

- Consume data faster
- Increase `recv_buffer_size`
- Use multiple streams (spread load)

### Partial Sends

**STT guarantees all-or-nothing send:**

```python
await stream.send(b"123456789")

# Either:
# A) Entire b"123456789" delivered to receiver
# B) StreamClosedError/SessionClosedError raised (nothing delivered)

# Never partial: receiver never gets b"1234" without b"56789"
```

**Framing handles this** - frames are atomic units.

## Advanced Patterns

### Stream Multiplexing Example

```python
# Video conferencing: video + audio + chat
session = await node.connect(peer_address, peer_node_id)

stream_video = session.open_stream(stream_id=1, max_frame_size=32768)
stream_audio = session.open_stream(stream_id=2, max_frame_size=8192)
stream_chat = session.open_stream(stream_id=3, max_frame_size=4096)

# Send concurrently
async def send_video():
    while True:
        frame = capture_video()
        await stream_video.send(frame)
        await asyncio.sleep(0.033)  # 30 FPS

async def send_audio():
    while True:
        sample = capture_audio()
        await stream_audio.send(sample)
        await asyncio.sleep(0.02)  # 50 Hz

async def send_chat():
    while True:
        msg = await get_user_message()
        await stream_chat.send(msg.encode())

await asyncio.gather(send_video(), send_audio(), send_chat())
```

**All streams share one encrypted session** - efficient!

### Request-Response with Timeout

```python
# RPC-style request with timeout
stream = session.open_stream()
await stream.send(b"GET /resource")

try:
    response = await asyncio.wait_for(stream.receive(), timeout=5.0)
except asyncio.TimeoutError:
    print("Server did not respond in 5 seconds")
finally:
    await stream.close()
```

### Streaming File Transfer

```python
# Sender
with open('large_file.bin', 'rb') as f:
    stream = session.open_stream(max_frame_size=65536)
    while True:
        chunk = f.read(1048576)  # 1 MB
        if not chunk:
            break
        await stream.send(chunk)
    await stream.close()

# Receiver
stream = session.get_stream(stream_id=1)
with open('received_file.bin', 'wb') as f:
    while True:
        try:
            data = await stream.receive()
            f.write(data)
        except StreamClosedError:
            break  # Sender finished
```

## Future: Priority and QoS

### Planned v0.6.0: Stream Priorities

```python
# Future API (not yet implemented)
stream_critical = session.open_stream(priority=10, qos='guaranteed')
stream_besteffort = session.open_stream(priority=1, qos='best_effort')
```

**Priority scheduling:**

- High-priority streams get more bandwidth
- Low-priority streams use leftover capacity

**QoS classes:**

- `'guaranteed'`: Never drop frames (retransmit aggressively)
- `'best_effort'`: Drop frames if congested (lower latency)

### Planned v0.7.0: Unreliable Streams

```python
# Future API (not yet implemented)
stream_realtime = session.open_stream(
    delivery='unreliable',  # No retransmissions
    ordered=False           # Out-of-order OK
)
```

**Use case:** Real-time video (old frames useless, skip them)

**Trade-off:** Lower latency, but data loss possible

## Visual Summary

```
         Stream Multiplexing in STT

Session (Encrypted Channel)
+--------------------------------------------------+
|                                                  |
|  Stream 1 (Video)                               |
|  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐               |
|  │ S1F0│ │ S1F1│ │ S1F2│ │ S1F3│ →→→           |
|  └─────┘ └─────┘ └─────┘ └─────┘               |
|                                                  |
|  Stream 2 (Audio)                               |
|  ┌─────┐ ┌─────┐ ┌─────┐                       |
|  │ S2F0│ │ S2F1│ │ S2F2│ →→→                   |
|  └─────┘ └─────┘ └─────┘                       |
|                                                  |
|  Stream 3 (Chat)                                |
|  ┌─────┐ ┌─────┐                               |
|  │ S3F0│ │ S3F1│ →→→                           |
|  └─────┘ └─────┘                               |
|                                                  |
+--------------------------------------------------+
            ↓ Multiplexed & Encrypted ↓
+--------------------------------------------------+
|  Network Transmission (Interleaved Frames)       |
|  S1F0 → S2F0 → S1F1 → S3F0 → S1F2 → S2F1 → ... |
+--------------------------------------------------+
            ↓ Received & Demultiplexed ↓
+--------------------------------------------------+
|  Receiver reconstructs streams in order          |
|  Stream 1: F0, F1, F2, F3 (video) ✓             |
|  Stream 2: F0, F1, F2 (audio) ✓                 |
|  Stream 3: F0, F1 (chat) ✓                      |
+--------------------------------------------------+
```

## Testing Your Understanding

1. **Can frames from Stream 1 arrive out of order to the application?**
   - No - STT reorders frames, delivers in sequence

2. **Does closing one stream close the entire session?**
   - No - session remains open, other streams unaffected

3. **What happens if sender sends faster than receiver can process?**
   - Flow control applies backpressure, sender blocks automatically

4. **How many streams can one session handle?**
   - Default 256 concurrent (configurable with `max_concurrent_streams`)

5. **Is XOR used for stream multiplexing?**
   - No - streams identified by `stream_id` field in frame header

6. **Can both peers open streams on the same session?**
   - Yes - bidirectional stream creation (both initiators)

## Common Pitfalls

**Problem:** Blocking on one slow stream  
**Solution:** Use multiple streams (multiplexing prevents head-of-line blocking)

**Problem:** Running out of stream IDs  
**Solution:** Close unused streams (IDs recycled), or increase `max_concurrent_streams`

**Problem:** High latency despite multiplexing  
**Solution:** Reduce frame size (smaller frames = better interleaving)

**Problem:** Backpressure causing timeouts  
**Solution:** Increase `recv_buffer_size` on receiver, or slow down sender

**Problem:** Out-of-order data within stream  
**Solution:** Not possible - STT guarantees ordering (check your application logic)

## Next Steps

- **Chapter 8**: Transport Layer (UDP vs WebSocket, how frames are transmitted)
- **Chapter 10**: Common Usage Patterns (real-world examples using streams)
- **Chapter 12**: Performance and Optimization (tuning stream parameters)

**Key Takeaways:**

- Streams = independent ordered data flows within session
- Multiplexing = interleaving frames from all streams (no head-of-line blocking)
- Flow control = automatic backpressure (prevents overflow)
- Ordering = guaranteed per stream (sequence numbers + reordering)
- Reliability = automatic retransmission (NACKs + timeouts)
- Flexible = unidirectional, bidirectional, long-lived, RPC patterns all supported
- Future = priority scheduling, unreliable streams, QoS classes (v0.6.0+)
