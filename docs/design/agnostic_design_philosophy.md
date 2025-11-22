# Agnostic Design Philosophy

**Last Updated**: Phase 0 Refactoring (v0.2.0-alpha)

---

## Core Principle

**STT is a binary transport protocol. It does NOT interpret your data.**

STT provides **agnostic primitives** that work for ANY binary data:

- Video streaming
- Sensor networks
- File transfer
- P2P messaging
- Custom binary protocols
- Anything else you can encode as bytes

**Zero assumptions about data semantics = Maximum flexibility.**

---

## What This Means

### STT Knows

- **Bytes**: Binary data flowing through the system
- **Segments**: MTU-optimized byte chunks for network transmission
- **Encryption**: STC-encrypted payloads
- **Sequence Numbers**: Ordering segments for delivery
- **Hash Addresses**: SHA3-256 content addressing
- **Endpoints**: Routing destinations (names YOU choose)
- **Frame Types**: 0x01-0x7F (STT protocol), 0x80-0xFF (YOUR custom types)

### STT Does NOT Know

- **Content Type**: Video? Sensor data? Files? Messages? Doesn't care.
- **Data Format**: H.264? JSON? Protobuf? Custom binary? Not STT's concern.
- **Application Semantics**: What the bytes "mean" to your application
- **File Systems**: No "files", "directories", "paths" concepts
- **Messaging Protocols**: No "messages", "chats", "conversations"
- **Media Codecs**: No video/audio encoding/decoding

---

## The Eight Agnostic Primitives

### 1. BinaryStreamEncoder

**What it is:** Async generator yielding encrypted byte segments

**Modes:**

- **Live**: Unknown size, generates as data arrives (real-time streaming)
- **Bounded**: Known size, batch processing (static data)

**Example use cases:**

```python
# Video streaming (STT doesn't know it's video)
video_bytes = h264_encoder.encode(frame)
encoder = BinaryStreamEncoder(video_bytes, stc_ctx, mode="live")

# Sensor data (STT doesn't know it's sensor readings)
sensor_bytes = json.dumps({"temp": 25.3}).encode()
encoder = BinaryStreamEncoder(sensor_bytes, stc_ctx, mode="bounded")

# File transfer (STT doesn't know it's a file)
file_bytes = open("document.pdf", "rb").read()
encoder = BinaryStreamEncoder(file_bytes, stc_ctx, mode="bounded")
```

**Same primitive, different semantics. YOU define meaning.**

---

### 2. BinaryStreamDecoder

**What it is:** Async iterator handling out-of-order encrypted segments

**What it does:**

- Buffers out-of-order segments
- Reorders by sequence number
- Decrypts with STC
- Returns complete byte stream

**Example:**

```python
decoder = BinaryStreamDecoder(stc_ctx)

# Network delivers segments out-of-order
decoder.receive_segment(segment_5, seq=5)
decoder.receive_segment(segment_2, seq=2)
decoder.receive_segment(segment_1, seq=1)  # Fills gap
decoder.receive_segment(segment_3, seq=3)
decoder.receive_segment(segment_4, seq=4)  # Now complete

# Get ordered, decrypted bytes
bytes_data = await decoder.receive_all()

# YOU interpret (video? sensor? file? YOUR decision)
if is_video_stream:
    frame = h264_decoder.decode(bytes_data)
elif is_sensor_data:
    reading = json.loads(bytes_data.decode())
elif is_file:
    save_file("document.pdf", bytes_data)
```

---

### 3. BinaryStorage

**What it is:** Hash-addressed encrypted byte buckets

**Properties:**

- **Deterministic Addressing**: SHA3-256 hash of content
- **Deduplication**: Same bytes = same hash = same storage
- **Content-Agnostic**: Stores ANY binary data

**Example:**

```python
storage = BinaryStorage(stc_wrapper)

# Store image (STT doesn't know it's an image)
image_bytes = open("photo.jpg", "rb").read()
image_hash = await storage.store(image_bytes)

# Store sensor reading (STT doesn't know it's sensor data)
sensor_bytes = json.dumps({"temp": 25.3, "time": 1234567890}).encode()
sensor_hash = await storage.store(sensor_bytes)

# Store video frame (STT doesn't know it's video)
frame_bytes = h264_encoder.encode(frame)
frame_hash = await storage.store(frame_bytes)

# Retrieve by hash (YOU remember what it was)
retrieved_image = await storage.retrieve(image_hash)
retrieved_sensor = await storage.retrieve(sensor_hash)
retrieved_frame = await storage.retrieve(frame_hash)

# Deduplication: storing same bytes again returns same hash
duplicate_hash = await storage.store(image_bytes)
assert duplicate_hash == image_hash  # Same content = same address
```

**YOU maintain metadata mapping (what each hash represents). STT just stores/retrieves bytes.**

---

### 4. EndpointManager

**What it is:** Multi-endpoint routing with per-endpoint queues

**What it does:**

- Routes bytes to named endpoints (YOU choose names)
- Maintains independent queue per endpoint
- Supports concurrent routing

**Example:**

```python
endpoint_mgr = EndpointManager()

# Video streaming to multiple viewers
await endpoint_mgr.route_to_endpoint("viewer_alice", video_frame_bytes)
await endpoint_mgr.route_to_endpoint("viewer_bob", video_frame_bytes)

# Sensor data to different processors
await endpoint_mgr.route_to_endpoint("analytics_engine", sensor_bytes)
await endpoint_mgr.route_to_endpoint("realtime_dashboard", sensor_bytes)

# P2P messaging to peers
await endpoint_mgr.route_to_endpoint("peer_charlie", message_bytes)

# STT doesn't know WHY you're routing (replication? fanout? load balancing?)
# It just routes bytes to named destinations
```

**YOU define endpoint naming scheme and routing logic. STT provides the mechanism.**

---

### 5. EventEmitter

**What it is:** User-defined event system

**What it does:**

- Dispatches events to registered handlers
- Supports async handlers
- Allows multiple handlers per event type

**Example:**

```python
emitter = EventEmitter()

# Define YOUR event types (STT has ZERO built-in event semantics)
emitter.on("temperature_threshold_exceeded", handle_temp_alert)
emitter.on("video_frame_received", handle_frame_display)
emitter.on("peer_connected", handle_new_peer)
emitter.on("custom_protocol_handshake_complete", handle_handshake)

# Emit YOUR events with YOUR data
await emitter.emit("temperature_threshold_exceeded", {
    "sensor": "cpu",
    "temp": 95.3,
    "threshold": 80.0
})

await emitter.emit("video_frame_received", {
    "frame_num": 42,
    "timestamp": 1234567890,
    "bytes": frame_bytes
})

# STT just dispatches. YOU define event types, payloads, semantics.
```

**No built-in events. Everything is user-defined.**

---

### 6. FrameDispatcher

**What it is:** Custom frame type handler (0x80-0xFF)

**What it does:**

- Routes frames to type-specific handlers
- Supports custom frame types 0x80-0xFF (STT reserves 0x01-0x7F)
- Calls your handlers with frame payloads

**Example:**

```python
dispatcher = FrameDispatcher()

# Define YOUR binary protocol with custom frame types
dispatcher.register_handler(0x80, handle_custom_handshake)
dispatcher.register_handler(0x81, handle_custom_data)
dispatcher.register_handler(0x82, handle_custom_ack)
dispatcher.register_handler(0xFF, handle_custom_error)

# When frames arrive, STT calls your handlers
# YOU parse the payload according to YOUR protocol

async def handle_custom_handshake(payload: bytes):
    # YOUR protocol: first 4 bytes = version, rest = peer_name
    version = int.from_bytes(payload[:4], 'big')
    peer_name = payload[4:].decode('utf-8')
    print(f"Handshake from {peer_name}, protocol v{version}")

async def handle_custom_data(payload: bytes):
    # YOUR protocol: your custom binary format
    data = your_custom_deserializer(payload)
    process_data(data)
```

**STT provides frame type routing. YOU define protocol semantics.**

---

### 7. STTSession (Connection Primitive)

**What it is:** STC-encrypted peer-to-peer connection

**What it does:**

- 4-step handshake with pre-shared seeds
- STC encryption for all data
- Multiplexed streams
- Key rotation support

**Agnostic aspect:**

- Session doesn't care what you send (video? files? messages? doesn't matter)
- Same session can carry multiple different data types on different streams
- YOU define stream purposes

---

### 8. STTNode (Runtime Primitive)

**What it is:** P2P node with DHT, session management, transport

**What it does:**

- DHT-based peer discovery (Kademlia)
- Session lifecycle management
- UDP/WebSocket transport
- Multi-peer concurrent connections

**Agnostic aspect:**

- Node doesn't know what application you're building
- Same node can run video streaming, sensor network, file sharing simultaneously
- YOU define application logic

---

## Design Patterns

### Pattern 1: Live Streaming

**Scenario**: Real-time video streaming

```python
# 1. YOUR encoder (H.264, VP9, whatever)
video_bytes = your_encoder.encode_frame(raw_pixels)

# 2. STT streaming primitive (live mode)
encoder = BinaryStreamEncoder(video_bytes, stc_ctx, mode="live")
async for seq, encrypted_segment in encoder:
    await session.send_on_stream(video_stream_id, encrypted_segment)

# 3. Receiver (STT just gives bytes)
decoder = BinaryStreamDecoder(stc_ctx)
decoder.receive_segment(encrypted_segment, seq)
decrypted_bytes = await decoder.receive_all()

# 4. YOUR decoder (STT's job is done)
raw_pixels = your_decoder.decode(decrypted_bytes)
display_frame(raw_pixels)
```

**STT's role**: Transport encrypted bytes from encoder to decoder.

**YOUR role**: Video encoding/decoding, codec selection, frame handling.

---

### Pattern 2: Hash-Addressed Storage

**Scenario**: Store sensor readings for later retrieval

```python
# 1. YOUR data format (JSON, protobuf, custom binary)
sensor_data = {
    "sensor_id": "temp_sensor_01",
    "timestamp": 1234567890,
    "temperature": 25.3,
    "humidity": 60.0
}
sensor_bytes = json.dumps(sensor_data).encode()

# 2. STT storage primitive
storage = BinaryStorage(stc_wrapper)
hash_address = await storage.store(sensor_bytes)

# 3. YOU maintain index (hash -> metadata)
your_index["temp_sensor_01"][1234567890] = hash_address

# 4. Retrieve later
retrieved_bytes = await storage.retrieve(hash_address)

# 5. YOUR deserialization (STT just returned bytes)
sensor_data = json.loads(retrieved_bytes.decode())
```

**STT's role**: Hash-addressed encrypted storage/retrieval.

**YOUR role**: Data serialization, indexing, metadata management.

---

### Pattern 3: Multi-Endpoint Routing

**Scenario**: Fanout video stream to multiple viewers

```python
# 1. Encode frame (YOUR codec)
frame_bytes = h264_encoder.encode(frame)

# 2. Encrypt segment
encoder = BinaryStreamEncoder(frame_bytes, stc_ctx, mode="live")
async for seq, encrypted_segment in encoder:
    
    # 3. Route to multiple endpoints
    endpoint_mgr = EndpointManager()
    await endpoint_mgr.route_to_endpoint("viewer_alice", encrypted_segment)
    await endpoint_mgr.route_to_endpoint("viewer_bob", encrypted_segment)
    await endpoint_mgr.route_to_endpoint("viewer_charlie", encrypted_segment)
    
    # 4. Emit custom event (YOUR event type)
    await emitter.emit("frame_broadcast", {
        "frame_num": seq,
        "viewers": ["alice", "bob", "charlie"]
    })
```

**STT's role**: Routing bytes to named endpoints, event dispatch.

**YOUR role**: Endpoint naming, routing logic, viewer management.

---

### Pattern 4: Custom Binary Protocol

**Scenario**: Define your own handshake/data exchange protocol

```python
# 1. Define YOUR frame types
FRAME_CUSTOM_HELLO = 0x80
FRAME_CUSTOM_DATA = 0x81
FRAME_CUSTOM_ACK = 0x82

# 2. Register handlers
dispatcher = FrameDispatcher()
dispatcher.register_handler(FRAME_CUSTOM_HELLO, handle_hello)
dispatcher.register_handler(FRAME_CUSTOM_DATA, handle_data)
dispatcher.register_handler(FRAME_CUSTOM_ACK, handle_ack)

# 3. YOUR protocol logic
async def handle_hello(payload: bytes):
    # YOUR format: [4 bytes version][N bytes peer_name]
    version = int.from_bytes(payload[:4], 'big')
    peer_name = payload[4:].decode('utf-8')
    
    # YOUR response logic
    response = build_custom_hello_response(version, peer_name)
    await send_custom_frame(FRAME_CUSTOM_ACK, response)

# 4. Send custom frames
hello_payload = build_custom_hello_payload(version=1, name="alice")
await send_custom_frame(FRAME_CUSTOM_HELLO, hello_payload)
```

**STT's role**: Frame type routing (0x80-0xFF), delivery mechanism.

**YOUR role**: Protocol design, payload format, handshake logic.

---

## Anti-Patterns (What NOT To Do)

### ❌ Assuming STT Knows About Files

**Wrong:**

```python
# This assumes STT has "file transfer" semantics
await stt_session.send_file("document.pdf")  # NO SUCH API
```

**Correct:**

```python
# YOU handle file semantics, STT handles bytes
file_bytes = open("document.pdf", "rb").read()
encoder = BinaryStreamEncoder(file_bytes, stc_ctx, mode="bounded")
async for seq, segment in encoder:
    await session.send_on_stream(stream_id, segment)
```

---

### ❌ Assuming STT Validates Content

**Wrong:**

```python
# Expecting STT to validate JSON
sensor_bytes = json.dumps({"temp": 25.3}).encode()
await storage.store(sensor_bytes)  # STT doesn't validate JSON
```

**Correct:**

```python
# YOU validate before storing
sensor_data = {"temp": 25.3}
validate_sensor_schema(sensor_data)  # YOUR validation
sensor_bytes = json.dumps(sensor_data).encode()
await storage.store(sensor_bytes)  # STT just stores bytes
```

---

### ❌ Assuming STT Defines Events

**Wrong:**

```python
# Expecting built-in "file_received" event
emitter.on("file_received", handler)  # No built-in events
```

**Correct:**

```python
# YOU define ALL event types
emitter.on("my_custom_file_received_event", handler)
await emitter.emit("my_custom_file_received_event", file_data)
```

---

### ❌ Assuming BinaryStorage Organizes Data

**Wrong:**

```python
# Expecting filesystem-like organization
hash = await storage.store_in_folder("images/photo.jpg", bytes)  # NO
```

**Correct:**

```python
# YOU maintain organization metadata
hash = await storage.store(photo_bytes)

# YOUR metadata index
your_metadata_db["images"]["photo.jpg"] = {
    "hash": hash,
    "created": timestamp,
    "size": len(photo_bytes)
}
```

---

## Terminology: Agnostic Language

### ✅ Use These Terms

- **Bytes**: Binary data
- **Segments**: MTU-optimized byte chunks (network transmission)
- **Hash-based addressing**: SHA3-256 content addressing
- **Encrypted payload**: STC-encrypted bytes
- **Endpoint**: Routing destination (user-defined name)
- **Stream**: Multiplexed byte channel within session
- **Frame**: Binary protocol unit with type/payload

### ❌ Avoid These Terms (Imply Semantics)

- ~~Content~~ → Use "bytes" or "data"
- ~~Chunks~~ → Use "segments" (MTU optimization, not semantic chunks)
- ~~Files~~ → STT doesn't know about files
- ~~Messages~~ → STT doesn't know about messaging
- ~~Videos/Audio~~ → STT doesn't know about media types
- ~~Documents~~ → STT doesn't know about document formats

---

## Key Takeaways

**1. STT = Transport Layer**

You are the application layer. STT sits below you, providing byte transport/storage/routing.

**2. Zero Built-in Semantics**

No files. No messages. No media types. Just bytes.

**3. Primitives Compose**

Same BinaryStreamEncoder works for video, sensors, files, anything binary.

**4. You Define Meaning**

- Event types: YOU choose
- Endpoint names: YOU choose
- Frame types 0x80-0xFF: YOU define
- Data formats: YOU design
- Metadata: YOU maintain

**5. Agnostic = Flexible**

Same STT node can run:

- Video streaming app
- Sensor network
- File sharing system
- P2P messaging
- Custom protocol

...all simultaneously. No conflicts. Each uses primitives differently.

---

## Summary

**STT Philosophy:**

> "Provide agnostic primitives for binary transport, storage, and routing. Never assume what the bytes mean. Let developers compose primitives into whatever application they need."

**Developer's Job:**

> "Choose codecs, define protocols, design data formats, maintain metadata, validate inputs. Use STT primitives as building blocks."

**Result:**

> Maximum flexibility. Zero constraints. Build anything that moves bytes.

---

**Next Steps:**

- See `examples/agnostic_design.py` for complete working examples
- See API Reference for detailed primitive documentation
- See User Manual for practical usage patterns
