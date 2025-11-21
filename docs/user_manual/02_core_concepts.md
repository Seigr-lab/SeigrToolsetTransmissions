# Chapter 2: Core Concepts Explained

## Introduction

This chapter explains the fundamental building blocks of STT in plain language. By the end, you'll understand nodes, sessions, streams, and how they work together.

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

## DHT and Content Distribution

**STT includes** DHT-based peer discovery and content distribution using Kademlia:

### DHT-Based Peer Discovery

Peers can discover each other automatically:

1. Join the DHT network (like joining a giant phonebook)
2. Publish content using STC.hash addresses
3. Find peers serving specific content automatically
4. Connect using the same session/stream architecture

**Example scenario:**

```
Alice wants file with STC.hash abc123...

Alice queries DHT: "Who has abc123...?"
DHT responds: Bob (IP 10.0.1.5) and Carol (IP 10.0.1.8) have it

Alice connects to Bob using standard STT session
Alice and Bob exchange file over streams
```

### Many-to-Many Content Distribution

Multiple peers can serve the same content:

- Alice downloads chunks from Bob, Carol, and Dave simultaneously
- Each chunk verified with STC.hash
- Resilient: if Bob disconnects, Alice continues from Carol/Dave
- Same session/stream primitives, just more of them

### Server-to-Many Streaming

A server can maintain multiple sessions simultaneously:

- Server has sessions with Alice, Bob, Carol (hundreds or thousands)
- Server streams video/data to all clients
- Each session independent (STC encrypted)
- Designed for Seigr ecosystem backbone

**The architecture you learned above doesn't change** - we just add DHT for discovery and support concurrent sessions to many peers. The node/session/stream concepts remain the same.

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
