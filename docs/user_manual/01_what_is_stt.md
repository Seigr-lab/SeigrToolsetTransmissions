# Chapter 1: What is STT?

## Introduction

STT (Seigr Toolset Transmissions) is a **binary transport protocol**. It moves encrypted bytes between peers. That's it.

STT does NOT know what your data means. It doesn't care if you're sending video, sensor readings, files, messages, or custom protocols. It provides **agnostic primitives** that YOU compose into whatever application you need.

**Core Philosophy**: Zero semantic assumptions. Maximum flexibility.

## What Problem Does STT Solve?

### The Transport Challenge

When two computers want to exchange binary data securely, they need:

1. **Direct Connection**: Find and connect to peers
2. **Security**: Encrypt bytes end-to-end (no middleman can read)
3. **Streaming**: Send bytes as they're generated (live data) or in batches
4. **Reliability**: Handle network problems, out-of-order delivery, packet loss
5. **Multiplexing**: Multiple independent byte streams over one connection
6. **Storage**: Hash-addressed encrypted byte buckets (content-addressable)
7. **Routing**: Send different data to different endpoints
8. **Extensibility**: User-defined frame types and events

STT provides **low-level primitives** for all of these. You define the semantics.

### Agnostic Design in Practice

**Same primitives, different applications:**

```text
Video Streaming App:
  - BinaryStreamEncoder: Generate video frames as bytes
  - BinaryStreamDecoder: Receive frames, YOU decode H.264/VP9
  - STT just moves encrypted bytes, doesn't know it's video

IoT Sensor Network:
  - BinaryStorage: Store sensor readings by hash
  - EventEmitter: Emit "temperature_reading" events (you define)
  - STT just stores/retrieves bytes, doesn't know it's sensor data

P2P Messaging:
  - EndpointManager: Route messages to different peers
  - Custom Frames (0x80-0xFF): Your own message protocol
  - STT just routes bytes, doesn't know they're messages
```

**The pattern**: STT provides transport/storage/routing. YOU provide semantics.

## What Makes STT Different?

### Agnostic Primitives, Not Application Layers

**Most protocols embed assumptions:**

- HTTP assumes request/response documents
- SMTP assumes email messages
- BitTorrent assumes files and torrents
- WebRTC assumes multimedia streams

**STT assumes NOTHING about your data:**

- Binary bytes in, binary bytes out
- YOU decide if it's video, sensors, files, messages, or something completely new
- Same primitives work for live streaming AND static storage
- No "file transfer" vs "streaming" distinction - just bytes flowing through agnostic components

### Peer-to-Peer Architecture

Most internet communication works like this:

```text
You → Server → Friend
```

Your data goes to a central server, which forwards it to your friend.

STT works like this:

```text
You ←→ Friend
```

Your computer talks directly to your friend's computer. No middleman needed.

**Benefits of peer-to-peer:**

- Faster (no extra hops for direct communication)
- More private (no mandatory central server)
- More resilient (no central point of failure)
- Distributed (content can be replicated across many peers)

**Features:**

- DHT-based peer discovery (Kademlia with STC.hash)
- NAT traversal with STUN-like functionality
- Pre-shared seeds for authentication (current design choice)
- Server mode for accepting multiple incoming connections

### Binary Protocol

STT uses binary data, not text. Think of it like this:

**Text-based protocol** (like HTTP):

```text
"Please send me file number 42"
```

**Binary protocol** (like STT):

```text
[01010011][00101010][11000011]...
```

Binary is more efficient because:

- Smaller size (less data to transmit)
- Faster processing (computers naturally work with binary)
- More precise (no ambiguity in interpretation)

But binary is harder for humans to read, which is why we have tools to inspect it.

### Strong Encryption with STC

STT uses STC (Seigr Toolset Crypto) for all encryption. STC is different from common cryptography:

**Common crypto (like in HTTPS):**

- Deterministic: Same input always produces same output
- Example: Hashing "hello" always gives the same result

**STC:**

- Probabilistic: Same input can produce different outputs
- Example: Encrypting "hello" twice gives two different results (both valid)

This difference requires special handling, which STT provides through its handshake protocol.

## Who Uses STT?

### Agnostic Use Cases

STT is designed for **any binary data transport scenario**:

**1. Live Streaming**
   - Video/audio encoding → binary frames → BinaryStreamEncoder
   - Receiver gets bytes → YOU decode H.264/VP9/Opus/etc.
   - STT doesn't know it's video, just encrypted byte segments

**2. Distributed Storage**
   - Store arbitrary binary data in hash-addressed buckets
   - BinaryStorage: SHA3-256 hash → encrypted bytes
   - Could be images, documents, sensor logs, anything

**3. Real-Time Sensors**
   - IoT devices generate readings → serialize to bytes
   - BinaryStreamEncoder sends live data stream
   - YOU define the sensor data format, STT just transports

**4. P2P Messaging**
   - Serialize messages → bytes → EndpointManager routes to peers
   - Custom frame types (0x80-0xFF) for your protocol
   - STT doesn't know they're "messages", just binary frames

**5. Custom Binary Protocols**
   - Define your own handshake/data exchange format
   - Use FrameDispatcher for application-specific frame handling
   - EventEmitter for custom event types YOU define

**6. Seigr Ecosystem (Primary Target)**
   - Content-addressed storage across many peers
   - DHT-based content discovery with Kademlia
   - Decentralized data distribution
   - No central server required

### What STT Is NOT

**Not a File Transfer Protocol**
   - No concept of "files" or "directories"
   - If you want file transfer, YOU implement it using STT primitives

**Not a Messaging System**
   - No "messages" or "chats" built-in
   - If you want messaging, YOU define message format and use STT to transport bytes

**Not a Media Streaming Library**
   - No video/audio codecs built-in
   - If you want media streaming, YOU encode/decode, STT transports encrypted bytes

**Not Application-Specific**
   - Zero built-in assumptions about data semantics
   - YOU decide what the bytes mean

### When NOT to Use STT

STT may not be suitable for:

**1. Web Browsing**

- HTTP/HTTPS is standard and universally supported in browsers
- STT is not a web protocol

**2. Email-Style Store-and-Forward**

- Email works when recipient is offline
- STT requires active peer connectivity (though DHT allows finding content later)

**3. Simple Request-Response APIs**

- If you just need basic client-server RESTful API, HTTP is simpler
- STT's peer-to-peer architecture is unnecessary overhead

**4. Systems Requiring Standard TLS Cryptography**

- STT uses STC exclusively
- If you need standard PKI/certificate-based auth, use TLS protocols

## How STT Compares to Other Technologies

### STT vs HTTPS

**HTTPS** (web browsing):

- Client-server model
- Standardized everywhere
- Works when server is offline (cached)
- Uses deterministic crypto

**STT**:

- Peer-to-peer model
- Requires both peers online
- Uses probabilistic crypto (STC)
- Better for direct device communication

### STT vs WebRTC

**WebRTC** (browser video calls):

- Built into browsers
- Uses standard crypto (DTLS/SRTP)
- Requires signaling server
- Optimized for multimedia

**STT**:

- Standalone protocol
- Uses STC crypto
- Direct peer connection
- Optimized for binary data of any type

### STT vs BitTorrent

**BitTorrent** (file sharing):

- Many-to-many file distribution
- Optimized for sharing large files
- No built-in encryption (optional extension)
- Uses SHA-1 hashes

**STT**:

- Designed for Seigr ecosystem (many-to-many capable)
- DHT-based content distribution with Kademlia
- STC encryption built-in
- Real-time streaming AND file distribution
- Uses STC hashes (probabilistic)

## Technical Overview (Simplified)

### Agnostic Primitives Architecture

STT provides **8 core primitives** that you compose:

**1. BinaryStreamEncoder (Streaming)**

```python
encoder = BinaryStreamEncoder(data_source, stc_context)
async for encrypted_segment in encoder:
    # Yields encrypted byte segments (MTU-optimized)
    # Live mode: generates as data arrives
    # Bounded mode: streams known-size data
```

**2. BinaryStreamDecoder (Streaming)**

```python
decoder = BinaryStreamDecoder(stc_context)
decoder.receive_segment(encrypted_segment, sequence_num)
decrypted_bytes = await decoder.receive_all()  # Handles out-of-order
```

**3. BinaryStorage (Storage)**

```python
storage = BinaryStorage(stc_wrapper)
hash_address = await storage.store(arbitrary_bytes)  # SHA3-256 hash
retrieved = await storage.retrieve(hash_address)     # Deduplication
```

**4. EndpointManager (Routing)**

```python
endpoint_mgr = EndpointManager()
await endpoint_mgr.route_to_endpoint("endpoint_id", data_bytes)
# Per-endpoint queues, multi-peer routing
```

**5. EventEmitter (User Events)**

```python
emitter = EventEmitter()
emitter.on("your_custom_event", handler)
await emitter.emit("your_custom_event", data)
# YOU define event types, STT just dispatches
```

**6. FrameDispatcher (Custom Frames)**

```python
dispatcher = FrameDispatcher()
dispatcher.register_handler(0x80, your_custom_handler)  # Frame types 0x80-0xFF
# Define your own binary protocol on top of STT
```

**7. STTSession (Connection)**

```python
session = await node.connect_udp(peer_host, peer_port)
# 4-step handshake, STC-encrypted, multiplexed streams
```

**8. STTNode (Runtime)**

```python
node = STTNode(node_seed, shared_seed, host, port)
await node.start()  # DHT, session management, transport
```

### How YOU Combine Them

**Example: Live Video Streaming**

```python
# 1. Encode video frames with YOUR codec (H.264, VP9, etc.)
video_frame_bytes = your_video_encoder.encode_frame(raw_pixels)

# 2. Stream bytes with STT (doesn't know it's video)
encoder = BinaryStreamEncoder(video_frame_bytes, stc_context, mode="live")
async for encrypted_segment in encoder:
    await session.stream_manager.send_on_stream(stream_id, encrypted_segment)

# 3. Receiver decodes (STT just gave them encrypted bytes)
decoder = BinaryStreamDecoder(stc_context)
decoder.receive_segment(encrypted_segment, seq)
decrypted_bytes = await decoder.receive_all()

# 4. YOU decode video (STT's job is done)
raw_pixels = your_video_decoder.decode(decrypted_bytes)
```

**Example: IoT Sensor Storage**

```python
# 1. Serialize sensor reading to bytes (YOUR format: JSON, protobuf, custom)
sensor_data = {"temp": 25.3, "humidity": 60}
sensor_bytes = json.dumps(sensor_data).encode()

# 2. Store in hash-addressed bucket (STT doesn't know it's sensor data)
storage = BinaryStorage(stc_wrapper)
hash_addr = await storage.store(sensor_bytes)  # SHA3-256 deterministic

# 3. Retrieve later (deduplication: same data = same hash)
retrieved_bytes = await storage.retrieve(hash_addr)

# 4. YOU deserialize (STT just stored/retrieved bytes)
sensor_data = json.loads(retrieved_bytes.decode())
```

### The Pattern: Agnostic Composition

```text
Your Application Layer (Semantics)
    ↓
STT Primitives (Transport/Storage/Routing)
    ↓
STC Encryption Layer (Probabilistic Crypto)
    ↓
Network Layer (UDP/WebSocket)
```

STT sits between YOUR application logic and the network. It never interprets your data.

## Key Concepts to Remember

**1. Agnostic Transport**: STT moves encrypted bytes. YOU define what they mean.

**2. Primitives, Not Applications**: BinaryStreamEncoder, BinaryStorage, EndpointManager, etc. are building blocks.

**3. Composition Over Assumption**: Same primitives work for video, sensors, files, messages, custom protocols.

**4. Hash-Based Addressing**: SHA3-256 deterministic hashing for content deduplication (BinaryStorage).

**5. Streaming Modes**: Live (unknown size, generates as data arrives) vs Bounded (known size, batch streaming).

**6. Custom Extension Points**: Frame types 0x80-0xFF, user-defined events, per-endpoint routing.

**7. STC Encryption**: All data encrypted with Seigr Toolset Crypto (probabilistic cryptography).

**8. Peer-to-Peer**: Direct connections, DHT-based discovery, no mandatory central server.

## Testing Status

STT is currently in pre-release (v0.2.0-alpha) with 90.03% test coverage:

- Core session management: 100% tested
- Stream operations: 99.24% tested
- Handshake protocol: 87.36% tested
- Transport layers: 84-90% tested

This means the core functionality is well-tested and reliable, though some edge cases and error paths are still being refined.

## Summary

STT is a **binary transport protocol with agnostic primitives**:

- **Streaming**: BinaryStreamEncoder/Decoder (live or bounded modes)
- **Storage**: BinaryStorage (hash-addressed encrypted byte buckets)
- **Routing**: EndpointManager (multi-endpoint, per-endpoint queues)
- **Events**: EventEmitter (user-defined event types)
- **Frames**: FrameDispatcher (custom frame types 0x80-0xFF)
- **Sessions**: STC-encrypted peer connections
- **Nodes**: P2P runtime with DHT discovery

**Zero assumptions about your data.** YOU provide semantics (video, sensors, files, messages, protocols).

STT is the **transport layer**. You are the **application layer**.

In the next chapter, we'll explore the core concepts in more detail, explaining nodes, sessions, streams, and encryption without assuming any technical background.

## Next Steps

Continue to [Chapter 2: Core Concepts Explained](02_core_concepts.md) to learn about the building blocks of STT.

---

**Questions to think about:**

- Do you understand the difference between peer-to-peer and client-server?
- Can you explain why binary protocols are more efficient than text?
- What use cases might benefit from STT in your context?
