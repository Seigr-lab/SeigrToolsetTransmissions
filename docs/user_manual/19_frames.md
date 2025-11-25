# Chapter 19: Frames & FrameDispatcher

**Version**: 0.2.0a0 (unreleased)  
**Components**: `STTFrame`, `FrameDispatcher`  
**Test Coverage**: 98.26%

---

## Overview

**Frames** are the fundamental unit of communication in STT. Every packet sent over the network is a frame.

**STTFrame** - Binary protocol structure  
**FrameDispatcher** - Routes frames to handlers

Think of frames like envelopes: they carry encrypted data, metadata, and routing information.

---

## Frame Structure

### Binary Layout

```
┌─────────────────────────────────────────────────┐
│ Magic (2 bytes)          │ 0x5354 ("ST")        │
├─────────────────────────────────────────────────┤
│ Length (varint)          │ Total frame length   │
├─────────────────────────────────────────────────┤
│ Type (1 byte)            │ Frame type           │
│ Flags (1 byte)           │ Control flags        │
├─────────────────────────────────────────────────┤
│ Session ID (8 bytes)     │ Session identifier   │
│ Sequence (8 bytes)       │ Frame sequence #     │
│ Timestamp (8 bytes)      │ Milliseconds         │
│ Stream ID (4 bytes)      │ Stream identifier    │
├─────────────────────────────────────────────────┤
│ Meta Length (varint)     │ Crypto metadata size │
│ Crypto Metadata (var)    │ STC encryption data  │
├─────────────────────────────────────────────────┤
│ Payload (variable)       │ Encrypted data       │
└─────────────────────────────────────────────────┘
```

**Fixed Header**: 32 bytes  
**Variable Parts**: Metadata + Payload

### Frame Types

STT reserves frame types for protocol control:

```python
# STT protocol frames (0x00-0x7F)
STT_FRAME_TYPE_HANDSHAKE = 0x01  # Handshake messages
STT_FRAME_TYPE_DATA      = 0x02  # User data
STT_FRAME_TYPE_STREAM    = 0x03  # Stream control
STT_FRAME_TYPE_CONTROL   = 0x04  # Protocol control
STT_FRAME_TYPE_ACK       = 0x05  # Acknowledgment

# Custom frames (0x80-0xFF)
# Your application can define these
CUSTOM_FRAME_TYPE_FILE   = 0x80
CUSTOM_FRAME_TYPE_RPC    = 0x81
```

**Design**: STT never interprets custom frame payloads (0x80-0xFF) - you register handlers via FrameDispatcher.

---

## Creating Frames

### Basic Data Frame

```python
from seigr_toolset_transmissions.frame import STTFrame
from seigr_toolset_transmissions.utils.constants import STT_FRAME_TYPE_DATA

frame = STTFrame(
    frame_type=STT_FRAME_TYPE_DATA,
    session_id=session.session_id,      # 8 bytes
    sequence=next_sequence_number,      # Incrementing counter
    stream_id=0,                         # Default stream
    payload=b"Hello, world!",            # Your data
    flags=0,                             # Optional flags
    timestamp=int(time.time() * 1000)   # Auto-filled if omitted
)
```

### Encrypting Frame

Before sending, encrypt the payload:

```python
# Encrypt using STCWrapper
encrypted_payload = frame.encrypt_payload(stc_wrapper)

# Frame now contains:
# - payload: encrypted bytes
# - crypto_metadata: STC metadata
# - _is_encrypted: True
```

**Important**: Always encrypt before sending over network!

### Serializing Frame

Convert frame to bytes for transmission:

```python
# Serialize to binary
frame_bytes = frame.to_bytes()

# Send over transport
await transport.send_frame(frame_bytes, peer_addr)
```

---

## Receiving Frames

### Deserializing Frame

Convert received bytes back to STTFrame:

```python
# Receive from transport
frame_data = await transport.receive()

# Deserialize
frame = STTFrame.from_bytes(frame_data)

# Frame is ready (but still encrypted)
```

### Decrypting Frame

```python
# Decrypt using STCWrapper
decrypted_payload = frame.decrypt_payload(stc_wrapper)

# Use the data
message = decrypted_payload.decode('utf-8')
print(f"Received: {message}")
```

---

## FrameDispatcher - Routing Frames

FrameDispatcher routes incoming frames to appropriate handlers.

### Default Handlers

STT has built-in handlers for protocol frames:

```python
# In STTNode
dispatcher = FrameDispatcher()

# Built-in handlers
dispatcher.register_handler(STT_FRAME_TYPE_HANDSHAKE, handle_handshake)
dispatcher.register_handler(STT_FRAME_TYPE_DATA, handle_data)
dispatcher.register_handler(STT_FRAME_TYPE_STREAM, handle_stream)
```

### Custom Frame Handlers

Register your own handlers for custom frame types:

```python
from seigr_toolset_transmissions.frame import FrameDispatcher

dispatcher = node.frame_dispatcher

# Define handler
async def handle_file_transfer(frame: STTFrame, session_id: bytes):
    """Handle file transfer frames"""
    # Decrypt
    file_data = frame.decrypt_payload(node.stc)
    
    # Process
    print(f"Received file chunk: {len(file_data)} bytes")
    await save_file_chunk(file_data)

# Register for custom type 0x80
dispatcher.register_handler(0x80, handle_file_transfer)
```

### Dispatching Frames

```python
# Dispatcher automatically routes frames
await dispatcher.dispatch(frame, session_id)

# Calls registered handler for frame.frame_type
```

---

## Complete Example: Custom Frame Type

```python
import asyncio
from seigr_toolset_transmissions import STTNode
from seigr_toolset_transmissions.frame import STTFrame

# Custom frame type
FRAME_TYPE_CHAT = 0x80

async def custom_frame_example():
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
    
    # Custom handler for chat messages
    async def handle_chat(frame: STTFrame, session_id: bytes):
        # Decrypt message
        message = frame.decrypt_payload(server.stc).decode('utf-8')
        print(f"[CHAT] {message}")
    
    # Register handler on server
    server.frame_dispatcher.register_handler(FRAME_TYPE_CHAT, handle_chat)
    
    # Start nodes
    await server.start(server_mode=True)
    await client.start()
    
    # Connect
    session = await client.connect_udp("localhost", 8080)
    
    # Send custom chat frame
    chat_frame = STTFrame(
        frame_type=FRAME_TYPE_CHAT,
        session_id=session.session_id,
        sequence=1,
        stream_id=0,
        payload=b"Hello from custom frame!"
    )
    
    # Encrypt and send
    chat_frame.encrypt_payload(client.stc)
    frame_bytes = chat_frame.to_bytes()
    await client.udp_transport.send_frame(frame_bytes, ("localhost", 8080))
    
    # Wait for delivery
    await asyncio.sleep(0.5)
    
    # Cleanup
    await client.stop()
    await server.stop()

asyncio.run(custom_frame_example())
```

---

## Frame Encryption

### Encryption Process

```python
# Before encryption
frame.payload = b"plaintext data"
frame.crypto_metadata = None
frame._is_encrypted = False

# Encrypt
frame.encrypt_payload(stc_wrapper)

# After encryption
frame.payload = b"\x9a\x2f\x1c..."  # Encrypted bytes
frame.crypto_metadata = b"\x01\x02..."  # STC metadata
frame._is_encrypted = True
```

### Associated Data

Frame metadata is bound to encryption:

```python
associated_data = {
    'frame_type': frame.frame_type,
    'flags': frame.flags,
    'session_id': frame.session_id,
    'sequence': frame.sequence,
    'timestamp': frame.timestamp,
    'stream_id': frame.stream_id
}

# Used during encryption
encrypted, metadata = stc.encrypt_frame(payload, associated_data)
```

**Why?** Prevents tampering with frame headers - any modification causes decryption to fail.

---

## Frame Flags

Control frame behavior with flags:

```python
# Example flags (you can define your own)
FLAG_COMPRESSED  = 0x01  # Payload is compressed
FLAG_PRIORITY    = 0x02  # High priority
FLAG_FRAGMENTED  = 0x04  # Part of multi-frame message

# Set flags
frame.flags = FLAG_COMPRESSED | FLAG_PRIORITY

# Check flags
if frame.flags & FLAG_COMPRESSED:
    payload = decompress(frame.payload)
```

---

## Sequence Numbers

Track frame order with sequence numbers:

```python
class SequenceCounter:
    def __init__(self):
        self._seq = 0
    
    def next(self) -> int:
        seq = self._seq
        self._seq += 1
        return seq

# Usage
counter = SequenceCounter()

frame1 = STTFrame(sequence=counter.next(), ...)  # 0
frame2 = STTFrame(sequence=counter.next(), ...)  # 1
frame3 = STTFrame(sequence=counter.next(), ...)  # 2
```

**Why?** Detect:

- Out-of-order delivery
- Missing frames
- Duplicate frames

---

## Stream Multiplexing

Use stream_id to multiplex multiple streams over one session:

```python
# Stream 0: Control messages
control_frame = STTFrame(stream_id=0, payload=b"PING")

# Stream 1: File transfer
file_frame = STTFrame(stream_id=1, payload=file_chunk)

# Stream 2: Video stream
video_frame = STTFrame(stream_id=2, payload=video_data)

# All go over same session, different streams
```

See [Chapter 20: Streams](20_streams.md) for detailed stream management.

---

## Frame Size Limits

### Maximum Frame Size

```python
from seigr_toolset_transmissions.utils.constants import STT_MAX_FRAME_SIZE

# Default: 1 MB
STT_MAX_FRAME_SIZE = 1024 * 1024

# Enforced during serialization
frame_bytes = frame.to_bytes()  # Raises STTFrameError if > 1 MB
```

### MTU Considerations

UDP transport has MTU limits:

```python
# UDP MTU (default 1472 bytes)
UDPConfig.max_packet_size = 1472

# Large frames fragmented at stream layer
# See Chapter 20 for stream fragmentation
```

---

## Common Patterns

### Frame Factory

```python
class FrameFactory:
    def __init__(self, session_id: bytes, stc_wrapper):
        self.session_id = session_id
        self.stc = stc_wrapper
        self.sequence = 0
    
    def create_data_frame(self, payload: bytes, stream_id: int = 0):
        frame = STTFrame(
            frame_type=STT_FRAME_TYPE_DATA,
            session_id=self.session_id,
            sequence=self.sequence,
            stream_id=stream_id,
            payload=payload
        )
        self.sequence += 1
        
        # Encrypt
        frame.encrypt_payload(self.stc)
        
        return frame

# Usage
factory = FrameFactory(session.session_id, node.stc)
frame = factory.create_data_frame(b"Hello")
```

### Frame Validation

```python
def validate_frame(frame: STTFrame, expected_session: bytes) -> bool:
    """Validate frame before processing"""
    
    # Check session ID
    if frame.session_id != expected_session:
        return False
    
    # Check frame type range
    if frame.frame_type > 0xFF:
        return False
    
    # Check timestamp (not too old)
    now = int(time.time() * 1000)
    if abs(now - frame.timestamp) > 60000:  # 60 seconds
        return False
    
    return True
```

### Batch Frame Processing

```python
async def process_frame_batch(frames: list[STTFrame], stc_wrapper):
    """Process multiple frames efficiently"""
    
    # Decrypt all frames
    decrypted = []
    for frame in frames:
        try:
            payload = frame.decrypt_payload(stc_wrapper)
            decrypted.append((frame, payload))
        except Exception as e:
            print(f"Decrypt failed: {e}")
    
    # Process decrypted data
    for frame, payload in decrypted:
        await handle_payload(frame.stream_id, payload)
```

---

## Troubleshooting

### "Frame too large"

**Problem**: `STTFrameError: Frame exceeds maximum size`

**Cause**: Payload > 1 MB

**Solution**: Use streams to fragment large data:

```python
# Instead of one huge frame
# huge_frame = STTFrame(payload=big_data)  # ✗ Fails

# Use stream to send in chunks
stream = await node.create_stream(session_id)
await stream.send_all(big_data)  # ✓ Automatic fragmentation
```

### "Invalid magic number"

**Problem**: `STTFrameError: Invalid magic number`

**Cause**: Corrupted frame data or wrong protocol

**Solution**: Verify transport integrity:

```python
# Check received data
if data[:2] != b'ST':  # Magic = 0x5354
    print("Not an STT frame!")
```

### Decryption Failures

**Problem**: `decrypt_payload()` raises exception

**Causes**:

- Wrong STCWrapper (different seed)
- Corrupted crypto_metadata
- Frame tampered with

**Solution**: Verify session and encryption:

```python
try:
    payload = frame.decrypt_payload(stc)
except Exception as e:
    print(f"Decryption failed: {e}")
    # Check if frame.crypto_metadata exists
    # Verify using correct session's STCWrapper
```

---

## Performance Considerations

**Frame Overhead**:

- Fixed header: 32 bytes
- Crypto metadata: ~100 KB (first frame with metadata exchange)
- Subsequent frames: ~32 bytes overhead
- Varint encoding: 1-9 bytes per field

**Encryption Cost**:

- STC encryption: ~0.5ms per frame
- Serialization: ~0.1ms
- Total: ~0.6ms per frame

**Throughput**:

- Small frames (100 bytes payload): ~1,600 frames/sec
- Large frames (64 KB payload): ~100 MB/sec
- Limited by encryption, not serialization

**Memory**:

- Frame object: ~200 bytes
- Crypto metadata: ~100 KB (cached per session)
- Payload: Variable

---

## Related Documentation

- **[Chapter 16: STTNode](16_sttnode.md)** - Uses frames for communication
- **[Chapter 17: Sessions](17_sessions.md)** - Frames belong to sessions
- **[Chapter 20: Streams](20_streams.md)** - Multiplexed streams over frames
- **[Chapter 23: Cryptography](23_cryptography.md)** - Frame encryption details
- **[API Reference](../api/API.md#frames)** - Complete API

---

**Document Version**: 0.2.0a0 (unreleased)  
**Last Updated**: November 25, 2025
