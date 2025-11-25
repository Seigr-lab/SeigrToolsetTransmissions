# Chapter 2: Core Concepts Explained

## Introduction

This chapter explains the fundamental building blocks of STT in plain language. By the end, you'll understand how **agnostic primitives** compose into complete applications.

**Remember**: STT provides primitives. YOU define semantics.

## Agnostic Primitives: The Building Blocks

Before diving into sessions and streams, understand STT's **agnostic design philosophy**:

### The Agnostic Principle

**STT does NOT interpret your data.** It provides primitives that work for ANY binary data:

- **BinaryStreamEncoder**: Yields encrypted byte segments (doesn't know if it's video, sensor data, or messages)
- **BinaryStreamDecoder**: Receives encrypted segments, handles out-of-order delivery (doesn't care what the bytes represent)
- **BinaryStorage**: Hash-addressed encrypted byte buckets (no assumptions about content)
- **EndpointManager**: Routes bytes to different endpoints (doesn't know why you're routing)
- **EventEmitter**: Dispatches user-defined events (YOU choose event types)
- **FrameDispatcher**: Handles custom frame types 0x80-0xFF (YOUR protocol on top of STT)

**YOU define semantics. STT provides transport/storage/routing.**

### Primitive 1: BinaryStreamEncoder

**Purpose**: Convert arbitrary byte streams into encrypted segments

**Modes:**

- **Live Mode**: Stream data as it arrives (unknown total size) - for real-time video, sensors, live events
- **Bounded Mode**: Stream known-size data in batches - for files, static datasets

```python
# Live streaming (video frames, sensor readings, real-time data)
encoder = BinaryStreamEncoder(
    data_source=your_byte_generator,
    stc_context=streaming_context,
    mode="live"
)

async for encrypted_segment in encoder:
    # Yields encrypted bytes, STT doesn't know what they represent
    await send_to_peer(encrypted_segment)
```

**What encoder does:**

- Splits bytes into MTU-optimized segments (NOT semantic chunks)
- Encrypts each segment with STC
- Yields segments as async generator

**What encoder does NOT do:**

- Parse your data format (doesn't know about H.264, JSON, protobuf, etc.)
- Assume data type (could be video, sensors, files, anything)
- Care about application semantics

### Primitive 2: BinaryStreamDecoder

**Purpose**: Receive encrypted segments, handle out-of-order delivery, decrypt bytes

```python
decoder = BinaryStreamDecoder(stc_context=streaming_context)

# Receive segments (possibly out-of-order)
decoder.receive_segment(encrypted_segment, sequence_number)

# Get all bytes when ready (decoder handles reordering)
decrypted_bytes = await decoder.receive_all()

# YOU interpret the bytes (video frame? sensor reading? message?)
your_application_data = your_deserializer(decrypted_bytes)
```

**What decoder does:**

- Buffer out-of-order segments
- Reorder by sequence number
- Decrypt with STC
- Return complete byte stream

**What decoder does NOT do:**

- Know what the bytes mean
- Deserialize application data
- Validate against schemas

### Primitive 3: BinaryStorage

**Purpose**: Hash-addressed encrypted byte buckets (content-addressable storage)

```python
storage = BinaryStorage(stc_wrapper)

# Store arbitrary bytes (could be images, documents, sensor logs, anything)
hash_address = await storage.store(arbitrary_bytes)
# Returns SHA3-256 hash (deterministic, same bytes = same hash)

# Retrieve by hash
retrieved_bytes = await storage.retrieve(hash_address)

# Deduplication: storing same bytes twice returns same hash, uses same storage
```

**What storage does:**

- Hash bytes with SHA3-256 (deterministic, content-based addressing)
- Encrypt with STC before storing
- Deduplicate (same content = same hash = same storage location)
- Retrieve by hash address

**What storage does NOT do:**

- Know what's stored (image? document? sensor data? doesn't care)
- Validate file types
- Organize into folders/directories
- Maintain metadata (YOU add metadata if needed)

### Primitive 4: EndpointManager

**Purpose**: Route bytes to different endpoints (multi-peer, multi-destination)

```python
endpoint_mgr = EndpointManager()

# Route data to specific endpoint (could be peer, service, destination)
await endpoint_mgr.route_to_endpoint("video_sink", video_frame_bytes)
await endpoint_mgr.route_to_endpoint("telemetry_sink", sensor_bytes)

# Each endpoint has independent queue
```

**What endpoint manager does:**

- Maintain per-endpoint queues
- Route bytes to correct destination
- Handle multiple concurrent endpoints

**What endpoint manager does NOT do:**

- Know why you're routing (load balancing? replication? fanout? doesn't matter)
- Interpret endpoint names (YOU choose naming scheme)
- Validate data going to endpoints

### Primitive 5: EventEmitter

**Purpose**: User-defined event system (YOU define event types)

```python
emitter = EventEmitter()

# Define YOUR event types (STT has no built-in event semantics)
emitter.on("temperature_threshold_exceeded", handle_temp_alert)
emitter.on("video_frame_received", handle_frame)
emitter.on("peer_connected", handle_new_peer)

# Emit YOUR events
await emitter.emit("temperature_threshold_exceeded", {"temp": 95.3, "sensor": "cpu"})
```

**What event emitter does:**

- Dispatch events to registered handlers
- Support async handlers
- Allow multiple handlers per event type

**What event emitter does NOT do:**

- Define event types (YOU define them)
- Validate event payloads
- Enforce event schemas

### Primitive 6: FrameDispatcher

**Purpose**: Handle custom frame types 0x80-0xFF (YOUR binary protocol)

```python
dispatcher = FrameDispatcher()

# Register handlers for YOUR frame types
dispatcher.register_handler(0x80, handle_custom_handshake)
dispatcher.register_handler(0x81, handle_custom_data)
dispatcher.register_handler(0xFF, handle_custom_control)

# STT calls your handlers when those frame types arrive
```

**What frame dispatcher does:**

- Route frames to type-specific handlers
- Support custom frame types 0x80-0xFF (STT reserves 0x01-0x7F)
- Call your handlers with frame payloads

**What frame dispatcher does NOT do:**

- Define frame semantics (YOU define what 0x80 means)
- Parse frame payloads (YOU parse your format)
- Validate custom protocols

### The Composition Pattern

**All primitives compose together:**

```python
# Example: Live video streaming to multiple peers with storage

# 1. Encode video frames (YOU encode with YOUR codec)
video_bytes = your_h264_encoder.encode(raw_frame)

# 2. Stream via BinaryStreamEncoder (live mode)
encoder = BinaryStreamEncoder(video_bytes, stc_ctx, mode="live")
async for segment in encoder:
    
    # 3. Store segments for later retrieval (hash-addressed)
    hash_addr = await storage.store(segment)
    
    # 4. Route to multiple endpoints (live viewers)
    await endpoint_mgr.route_to_endpoint("viewer_alice", segment)
    await endpoint_mgr.route_to_endpoint("viewer_bob", segment)
    
    # 5. Emit custom event (YOUR event type)
    await emitter.emit("frame_sent", {"hash": hash_addr, "viewers": 2})

# STT just moved bytes. YOU defined: video format, routing logic, events, storage strategy
```

**Key Insight**: Same primitives work for completely different applications:

- **Video streaming**: BinaryStreamEncoder (live) + EndpointManager (fanout to viewers)
- **Sensor network**: BinaryStorage (hash-addressed readings) + EventEmitter (threshold alerts)
- **P2P messaging**: Custom frames (0x80 = chat message) + EndpointManager (peer routing)
- **File transfer**: BinaryStreamEncoder (bounded) + BinaryStorage (deduplication)

**Zero assumptions. Maximum flexibility.**

## Nodes: The Participants

### What is a Node?

A **node** is any device or program running the STT protocol. Think of nodes as participants in a conversation.

**Examples of nodes:**

- Your laptop running an STT application
- A server running STT software
- A mobile phone with STT enabled
- An IoT device using STT for communication

### Node Identity

Each node has a unique identity:

```
Node ID: A 32-byte unique identifier (like a fingerprint)
```

**How it's created:**

1. You provide a "node seed" (random bytes, at least 32 bytes)
2. STT uses STC cryptography to generate a node ID from this seed
3. The node ID uniquely identifies this node

**Analogy**: Think of the node seed as your DNA, and the node ID as your fingerprint - derived from your DNA, unique to you, but not the DNA itself.

### Node Lifecycle

A node goes through these states:

```
[Created] → [Started] → [Running] → [Stopped]
```

**Created**: Node exists in memory but isn't communicating yet  
**Started**: Node is listening for connections and can connect to others  
**Running**: Node is actively communicating with peers  
**Stopped**: Node has shut down cleanly

## Peers: Who You're Talking To

### What is a Peer?

A **peer** is any other node you're communicating with. If your laptop's node connects to your phone's node, they are peers to each other.

**Important**: The relationship is symmetric. There's no inherent "client" or "server" - both nodes are equal peers.

### Peer Discovery

Before connecting, nodes need to know:

1. The peer's IP address (like a postal address)
2. The peer's port number (like an apartment number)

## Sessions: The Connections

### What is a Session?

A **session** is an active, encrypted connection between two peers. Think of it as a secure phone call.

**Session characteristics:**

- **Encrypted**: All data is encrypted with STC
- **Authenticated**: Both peers verify each other's identity
- **Stateful**: The session maintains state (sequence numbers, statistics, etc.)
- **Isolated**: Each session is independent

### Session ID

Each session has a unique 8-byte identifier:

```
Session ID: 8 bytes derived from handshake
```

**How it's created:**
During the handshake, both peers contribute random nonces (numbers used once). The session ID is calculated using XOR:

```
session_id = XOR(nonce_initiator, nonce_responder, node_id_initiator, node_id_responder)[0:8]
```

This ensures:

- Both peers derive the same session ID
- The ID is unique to this connection
- The ID is deterministic (same inputs = same output)

### Session Lifecycle

```
[Handshake] → [Active] → [Closing] → [Closed]
```

**Handshake**: The 4-message setup to establish the session  
**Active**: Session is ready for data transmission  
**Closing**: One peer initiated shutdown  
**Closed**: Session is terminated, resources freed

### Session Statistics

Each session tracks:

- Bytes sent/received
- Messages sent/received
- Time created
- Time last active
- Number of active streams

These statistics help with monitoring and debugging.

## Streams: Multiplexed Channels

### What is a Stream?

A **stream** is a channel for data within a session. Multiple streams can exist in one session simultaneously.

**Analogy**: If a session is a phone call, streams are like being able to talk AND send pictures AND share screen simultaneously during that one call.

### Why Streams?

Without streams:

```
Session 1: Sending a file
Session 2: Sending chat messages
Session 3: Sending video
```

You'd need separate sessions for different data types.

With streams:

```
Session 1:
  - Stream 1: Sending a file
  - Stream 2: Sending chat messages
  - Stream 3: Sending video
```

All data shares the same encrypted session, but is logically separated.

### Stream IDs

Each stream has an integer ID:

```
Stream ID 0: Reserved for control messages
Stream ID 1-65535: Available for user data
```

**Implementation detail**: Stream IDs are encoded using "varint" (variable-length integers) to save space. Small numbers use fewer bytes.

### Stream Ordering

Within a stream, data arrives in order:

```
Send: [Message 1] → [Message 2] → [Message 3]
Receive: [Message 1] → [Message 2] → [Message 3]
```

But different streams are independent:

```
Stream 1: [A] → [B] → [C]
Stream 2: [X] → [Y] → [Z]

Network delivery might be: [A] [X] [B] [Y] [C] [Z]
But each stream sees its own order preserved.
```

### Stream States

```
[Created] → [Open] → [Closing] → [Closed]
```

**Created**: Stream exists but not yet transmitting  
**Open**: Stream is actively sending/receiving  
**Closing**: Stream is shutting down (flush remaining data)  
**Closed**: Stream is fully terminated

## Encryption and Keys

### The Seed System

STT uses a "pre-shared seed" model. Both peers must have the same secret seed before they can communicate.

**Seeds in STT:**

1. **Node Seed** (per-node)
   - Used to generate node ID
   - Initializes STC cryptography for this node
   - Should be unique to each node

2. **Shared Seed** (per-peer-pair)
   - Both peers must have the same shared seed
   - Used during handshake to authenticate
   - Required to decrypt handshake messages

**Important**: Seeds must be distributed out-of-band (outside STT). For example:

- Physically transfer (USB drive)
- Secure channel (in-person exchange)
- Pre-configuration (built into devices)

### Session Keys

Once handshake completes, a session key is derived. This key is used for encrypting all data in the session.

**Session key properties:**

- Unique to this session
- Derived from both peers' contributions
- Never transmitted over the network
- Can be rotated during long sessions

### Key Rotation

For long-running sessions, keys can be rotated to improve security:

```
Initial Key → [After 1GB data] → Rotated Key 1 → [After 1 hour] → Rotated Key 2
```

**Triggers for rotation:**

- Data threshold (e.g., 1GB transmitted)
- Time threshold (e.g., 1 hour elapsed)
- Message threshold (e.g., 100,000 messages)

## Frames: The Data Units

### What is a Frame?

A **frame** is the basic unit of data transmission in STT. Think of frames as envelopes containing your messages.

**Frame structure:**

```
[Header] [Encrypted Payload] [Crypto Metadata]
```

**Header**: Contains frame type, session ID, stream ID, sequence number  
**Encrypted Payload**: Your actual data, encrypted with STC  
**Crypto Metadata**: Information needed to decrypt (nonce, etc.)

### Frame Types

STT defines several frame types:

- **HANDSHAKE (0x01)**: Used during connection setup
- **DATA (0x02)**: Regular data transmission
- **CONTROL (0x03)**: Control messages (close, error, etc.)
- **STREAM_CONTROL (0x04)**: Stream-specific control
- **AUTH (0x05)**: Authentication messages

### Frame Limits

Frames have a maximum size (typically 2MB). If you send larger data:

```
Large File (10MB)
    ↓
[Split into chunks]
    ↓
Frame 1 (2MB) → Frame 2 (2MB) → Frame 3 (2MB) → Frame 4 (2MB) → Frame 5 (2MB)
```

Each frame is independently encrypted and can be transmitted over the network.

## How It All Fits Together

Let's trace a complete example: Alice sends a file to Bob.

### 1. Setup

```
Alice's Node: Created with node_seed_alice, shared_seed_ab
Bob's Node: Created with node_seed_bob, shared_seed_ab
```

Note: `shared_seed_ab` is the same on both sides.

### 2. Connection

```
Alice: "I want to connect to Bob at 192.168.1.100:9000"
Alice → [HELLO] → Bob
Bob → [RESPONSE] → Alice
Alice → [AUTH_PROOF] → Bob
Bob → [FINAL] → Alice

Session established: session_id = abc12345
```

### 3. Stream Creation

```
Alice: "Create stream 1 for file transfer"
Stream 1 created in session abc12345
```

### 4. Data Transmission

```
File: example.pdf (5MB)

Alice:
  Split file into chunks
  
  Chunk 1 → [Encrypt] → Frame 1 → [Send on Stream 1]
  Chunk 2 → [Encrypt] → Frame 2 → [Send on Stream 1]
  Chunk 3 → [Encrypt] → Frame 3 → [Send on Stream 1]
  ...

Bob:
  [Receive Frame 1] → [Decrypt] → Chunk 1
  [Receive Frame 2] → [Decrypt] → Chunk 2
  [Receive Frame 3] → [Decrypt] → Chunk 3
  ...
  
  Reassemble chunks → example.pdf (verified)
```

### 5. Cleanup

```
Alice: "Stream 1 complete, close it"
Alice: "Session complete, close it"

Session abc12345 closed
Nodes remain running for future connections
```

## Visual Summary

```
                    STT Architecture
                    
+--------------------------------------------------+
|                    Application                   |
|  (Your code using STT)                          |
+--------------------------------------------------+
                       ↓
+--------------------------------------------------+
|                 Stream Layer                     |
|  Stream 1    Stream 2    Stream 3               |
|  [Ordered]   [Ordered]   [Ordered]              |
+--------------------------------------------------+
                       ↓
+--------------------------------------------------+
|                Session Layer                     |
|  Session ID: abc12345                           |
|  [Encrypted with STC]                           |
|  [Key rotation support]                         |
+--------------------------------------------------+
                       ↓
+--------------------------------------------------+
|                  Frame Layer                     |
|  [Binary frames]                                |
|  [Header + Encrypted Payload + Metadata]        |
+--------------------------------------------------+
                       ↓
+--------------------------------------------------+
|               Transport Layer                    |
|  UDP or WebSocket                               |
|  [Network transmission]                         |
+--------------------------------------------------+
```

## Key Takeaways

1. **Nodes** are participants running STT
2. **Sessions** are encrypted connections between two nodes
3. **Streams** are multiplexed channels within a session
4. **Frames** are the basic units of data transmission
5. **Seeds** are pre-shared secrets that enable encryption
6. **Session IDs** uniquely identify connections
7. **Stream IDs** separate different data flows

## Common Misconceptions

### "STT is like HTTP"

**Wrong**: HTTP is client-server, request-response. STT is peer-to-peer, streaming.

### "I can connect without pre-shared seeds"

**Wrong**: STT requires pre-shared seeds for authentication. No seeds = no connection.

### "One session = one data transfer"

**Wrong**: Sessions can have multiple streams for different data types simultaneously.

### "Frames are like packets"

**Wrong**: Frames are STT's protocol units. Packets are lower-level network units. One frame might span multiple packets or vice versa.

## Practical Example: Code Walkthrough

Here's simplified Python code showing the concepts:

```python
# 1. Create nodes
alice_node = STTNode(
    node_seed=b"alice_unique_seed_32bytes!!!",
    shared_seed=b"shared_secret_with_bob_32bytes"
)

bob_node = STTNode(
    node_seed=b"bob_unique_seed_32bytes!!!!!",
    shared_seed=b"shared_secret_with_bob_32bytes"
)

# 2. Start nodes
await alice_node.start()
await bob_node.start()

# 3. Establish session
session = await alice_node.connect_udp("192.168.1.100", 9000)
# At this point, handshake completed, session active

# 4. Create stream
stream = await session.stream_manager.create_stream()

# 5. Send data
await stream.send(b"Hello Bob!")

# 6. Receive data (on Bob's side)
async for packet in bob_node.receive():
    print(f"Received: {packet.data}")

# 7. Cleanup
await stream.close()
await session.close()
await alice_node.stop()
await bob_node.stop()
```

## Next Chapter

Now that you understand the core concepts, we'll dive deeper into how binary protocols work and why STT uses binary instead of text-based formats.

Continue to [Chapter 3: Binary Protocols and Data](03_binary_protocols.md)

---

**Review Questions:**

1. What's the difference between a node and a peer?
2. Why can one session have multiple streams?
3. What are the two types of seeds, and what is each used for?
4. What information does a frame header contain?
5. When is a session key rotated?

**Hands-on Exercise:**
Try drawing a diagram showing two nodes establishing a session with three streams. Label the session ID and stream IDs.
