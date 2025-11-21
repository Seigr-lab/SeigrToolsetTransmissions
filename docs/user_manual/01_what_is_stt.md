# Chapter 1: What is STT?

## Introduction

STT (Seigr Toolset Transmissions) is a protocol for secure peer-to-peer communication. Before we dive into technical details, let's understand what that means in everyday terms.

## What Problem Does STT Solve?

### The Communication Challenge

When two computers want to communicate securely, they face several challenges:

1. **Direct Connection**: How do they find and connect to each other?
2. **Security**: How do they ensure no one else can read their messages?
3. **Efficiency**: How do they send large amounts of data quickly?
4. **Reliability**: How do they handle network problems gracefully?
5. **Multiple Conversations**: How can they have several conversations simultaneously?

STT provides solutions to all these challenges.

### Real-World Analogy

Think of STT like a secure phone system:

- **Nodes** are like phones - each device that can make calls
- **Sessions** are like phone calls - active connections between two phones
- **Streams** are like having multiple conversations during one call (imagine talking AND sending pictures simultaneously)
- **Encryption** is like speaking in a secret language only you and your friend understand
- **Handshake** is like confirming "Can you hear me?" before starting the real conversation

## What Makes STT Different?

### Peer-to-Peer Architecture

Most internet communication works like this:

```
You → Server → Friend
```

Your message goes to a central server, which forwards it to your friend.

STT works like this:

```
You ←→ Friend
```

Your computer talks directly to your friend's computer. No middleman needed.

**Benefits of peer-to-peer:**

- Faster (no extra hops for direct communication)
- More private (no mandatory central server)
- More resilient (no central point of failure)
- Distributed (content can be replicated across many peers)

**Current limitations (v0.2.0-alpha):**

- Manual peer discovery (automatic DHT-based discovery planned for v0.4.0)
- Direct connections require known IP addresses (NAT traversal planned for v0.3.0)
- Pre-shared seeds for authentication (current design choice)

### Binary Protocol

STT uses binary data, not text. Think of it like this:

**Text-based protocol** (like HTTP):

```
"Please send me file number 42"
```

**Binary protocol** (like STT):

```
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

### Use Cases

STT is designed for the **Seigr ecosystem** and similar applications:

1. **Distributed Content Networks**
   - Content-addressed storage across many peers
   - DHT-based content discovery (planned v0.4.0)
   - Decentralized file distribution
   - No central server required

2. **Secure File Sharing**
   - Send files directly between devices
   - Multiple peers can serve the same content
   - End-to-end encryption with STC

3. **Real-Time Communication**
   - Video/audio calls
   - Live data streaming
   - Sensor networks

4. **Peer-to-Peer Applications**
   - Decentralized systems
   - Collaborative tools
   - Private messaging
   - Distributed databases

### When NOT to Use STT

STT may not be suitable for:

1. **Web Browsing**
   - HTTP/HTTPS is standard and universally supported in browsers
   - STT is not a web protocol

2. **Email-Style Store-and-Forward**
   - Email works when recipient is offline
   - STT requires active peer connectivity (though DHT allows finding content later)

3. **Simple Request-Response APIs**
   - If you just need basic client-server RESTful API, HTTP is simpler
   - STT's peer-to-peer architecture is unnecessary overhead

4. **Systems Requiring Standard TLS Cryptography**
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
- DHT-based content distribution (planned v0.4.0)
- STC encryption built-in
- Real-time streaming AND file distribution
- Uses STC hashes (probabilistic)

## Technical Overview (Simplified)

### The Basic Flow

When two devices communicate using STT:

1. **Setup Phase**
   - Both devices share a secret seed beforehand (like exchanging keys)
   - Each device starts an STT node

2. **Connection Phase**
   - Device A initiates connection to Device B
   - They perform a 4-step handshake to verify identities
   - A secure session is established

3. **Communication Phase**
   - Devices create streams for different data types
   - Data is encrypted, transmitted, and decrypted
   - Multiple streams can run simultaneously

4. **Shutdown Phase**
   - Streams are closed
   - Session is terminated
   - Connection is cleaned up

### What Happens Under the Hood

When you send data through STT:

```
Your Data
   ↓
[Encrypt with STC]
   ↓
[Package into frames]
   ↓
[Add sequence numbers]
   ↓
[Send over network (UDP or WebSocket)]
   ↓
[Receive on other side]
   ↓
[Verify and reorder]
   ↓
[Decrypt with STC]
   ↓
Original Data
```

## Key Concepts to Remember

1. **Node**: A device/program running STT
2. **Peer**: Another node you're communicating with
3. **Session**: An active encrypted connection between two peers
4. **Stream**: A channel for data within a session
5. **Frame**: A unit of data with headers and encrypted payload
6. **Seed**: A pre-shared secret that enables encryption

## Testing Status

STT is currently in pre-release (v0.2.0-alpha) with 90.03% test coverage:

- Core session management: 100% tested
- Stream operations: 99.24% tested
- Handshake protocol: 87.36% tested
- Transport layers: 84-90% tested

This means the core functionality is well-tested and reliable, though some edge cases and error paths are still being refined.

## Summary

STT is a peer-to-peer binary streaming protocol that:

- Enables direct, encrypted communication between devices
- Uses STC for probabilistic cryptography
- Supports multiple simultaneous data streams
- Works over UDP or WebSocket transports
- Requires pre-shared seeds for authentication

In the next chapter, we'll explore the core concepts in more detail, explaining nodes, sessions, streams, and encryption without assuming any technical background.

## Next Steps

Continue to [Chapter 2: Core Concepts Explained](02_core_concepts.md) to learn about the building blocks of STT.

---

**Questions to think about:**

- Do you understand the difference between peer-to-peer and client-server?
- Can you explain why binary protocols are more efficient than text?
- What use cases might benefit from STT in your context?
