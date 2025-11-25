# Chapter 15: Design Decisions and Trade-offs

## Introduction

This chapter explains **why** STT is designed the way it is - the reasoning behind key decisions, trade-offs made, and the vision for the Seigr ecosystem.

## Core Design Principles

### 1. Agnostic Binary Transport (Zero Assumptions)

**Decision:** STT makes ZERO assumptions about data semantics

**Rationale:**

- Maximum flexibility (same primitives for video, sensors, files, protocols)
- No built-in content types or file semantics (user defines ALL meaning)
- Future-proof (works for use cases not yet invented)
- Composable primitives (BinaryStreamEncoder, BinaryStorage, EndpointManager, EventEmitter, FrameDispatcher)

**Trade-off:** More work for developers (must define schemas, codecs, metadata) but infinite flexibility

**Alternative rejected:** Built-in file transfer, messaging, media streaming - limits use cases to what we anticipated

**Result:** Same STT node can simultaneously run video streaming, sensor networks, file sharing, custom protocols

### 2. Seigr Ecosystem First

**Decision:** Build STT specifically for Seigr ecosystem needs

**Rationale:**

- Seigr requires content-addressed storage (STC.hash native)
- Distributed network needs peer-to-peer (not client-server)
- Privacy-focused (encryption mandatory, not optional)
- Decentralized (no central authorities)

**Trade-off:** Less general-purpose than HTTP/WebRTC, but optimal for Seigr use case

**Alternative rejected:** Use existing protocols (HTTP, BitTorrent) - don't integrate STC natively

### 3. Pre-Shared Seeds (Not PKI)

**Decision:** Require pre-shared seeds for authentication (no public key cryptography)

**Rationale:**

- Simpler trust model (no certificate authorities, no PKI complexity)
- Deterministic keys useful (same seed → same keys, helps content addressing)
- Lower computational cost (no RSA/ECDH handshake)
- Aligns with Seigr's privacy model (pre-authorized peers)

**Trade-off:** Cannot connect to arbitrary peers (like HTTPS can) - requires out-of-band seed distribution

**Alternative rejected:** TLS-style PKI - adds complexity, CAs centralized, ephemeral keys incompatible with deterministic content addressing

### 4. STC Instead of Standard Crypto

**Decision:** Use STC (Seigr Temporal Cryptography) exclusively

**Rationale:**

- STC.hash integral to Seigr (content addressing, DHT distances)
- Unified cryptography across ecosystem (one library)
- Probabilistic hashing (collisions tolerated - design choice for Seigr)

**Trade-off:** Not standardized (IETF), not audited like TLS, unfamiliar to developers

**Alternative rejected:** TLS/AES - doesn't provide STC.hash, deterministic keys harder

### 5. Incremental Development

**Decision:** Build incrementally with continuous feature delivery

**Rationale:**

- Ship working software early (validate architecture quickly)
- Adapt design based on real usage and feedback
- Avoid over-engineering features not yet needed

**Result:** STT now includes comprehensive features: DHT peer discovery, content distribution, NAT traversal, server mode

**Alternative rejected:** Wait until all features complete - delays feedback, risks building wrong thing

### 6. Binary Protocol (Not Text)

**Decision:** Custom binary framing (not HTTP-like text)

**Rationale:**

- Efficiency (binary smaller than text)
- Precise control (varint encoding, frame structure optimized)
- Lower overhead (fewer bytes for headers)

**Trade-off:** Harder to debug (can't read with `curl`), requires custom tools (Wireshark dissectors)

**Alternative rejected:** HTTP/2-style text headers - higher overhead, less control

## Key Trade-Offs

### Forward Secrecy vs Determinism

**Chosen:** Deterministic keys (no forward secrecy)

**Why:**

- Content addressing requires deterministic hashing
- Same seed must produce same keys (Seigr ecosystem requirement)
- Forward secrecy needs ephemeral keys (random each session)

**Consequence:** Compromised seed exposes all past sessions (if attacker recorded traffic)

**Mitigation:** Seed rotation, secure storage (HSM)

**Alternative:** Hybrid (deterministic content keys + ephemeral session keys) - under research

### Reliability on UDP vs Using TCP

**Chosen:** Build reliability on top of UDP

**Why:**

- Control over retransmission policy (application-aware)
- Lower latency (no TCP head-of-line blocking)
- Works with WebSocket fallback (same reliability layer over both transports)

**Consequence:** More complex (STT implements retransmissions, ordering)

**Alternative:** Use TCP directly - simpler but slower, less flexible

**Result:** UDP default, WebSocket (TCP) fallback - best of both worlds

### Custom Protocol vs gRPC/QUIC

**Chosen:** Custom STT protocol

**Why:**

- Precise control (frame format, STC integration, Seigr-specific features)
- No unnecessary features (gRPC designed for RPCs, not general P2P)
- QUIC nascent (2019), STT started ~2021 (QUIC not mature enough)

**Consequence:** Must maintain own protocol (more work), less ecosystem tooling

**STT 0.2.0a0 features:**

- **Adaptive Priority**: Priority calculated from content properties (uniqueness, access patterns, network conditions)
- **Probabilistic Delivery**: Shannon entropy determines delivery probability
- **Crypto Session Continuity**: Resume sessions across transports/IPs/devices using seed-based identity
- **Content-Affinity Pooling**: Sessions clustered by STC.hash proximity (Kademlia XOR distance)

### Peer-to-Peer Design

**Chosen:** Peer-to-peer with DHT and content distribution

**Why:**

- Native support for Seigr ecosystem content addressing
- Distributed architecture eliminates single points of failure
- Kademlia DHT for efficient peer and content discovery

**Result:** STT includes comprehensive P2P capabilities: server mode, DHT discovery, content distribution

**Alternative:** Client-server only - simpler but defeats purpose of decentralized Seigr ecosystem

## Why Not Existing Protocols?

### Why Not HTTP/3 (QUIC)?

**HTTP/3:**

- Designed for web (client-server, request-response)
- QUIC provides transport (reliability, encryption)
- Not peer-to-peer native

**STT advantages:**

- Native P2P (symmetric peers)
- STC integration (content addressing)
- Seigr-specific (DHT, Kademlia XOR distances with STC.hash)

### Why Not WebRTC?

**WebRTC:**

- Designed for browsers (peer-to-peer video calls)
- Complex signaling (requires server for NAT traversal)
- Heavy (media codecs, STUN/TURN infrastructure)

**STT advantages:**

- Simpler (no media codecs - general binary protocol)
- Standalone (no browser required)
- Seigr-specific (STC, content addressing)
- Integrated NAT traversal (STUN-like functionality included)

**Similarities:** Both P2P, both need NAT traversal

### Why Not BitTorrent Protocol?

**BitTorrent:**

- Designed for file sharing (many-to-many)
- DHT-based (Kademlia with SHA-1)
- Proven at scale (millions of users)

**STT advantages:**

- General streaming (not just files)
- STC encryption (BitTorrent encryption optional, not content-addressed)
- Real-time capable (not just bulk transfer)
- STC.hash for content addressing (vs SHA-1)

**Similarities:** Both DHT, both P2P, both content distribution

**Result:** STT inspired by BitTorrent DHT, but extends to real-time + STC

### Why Not TLS/DTLS?

**TLS (Transport Layer Security):**

- Standard (IETF RFCs, widely deployed)
- PKI-based (certificates, CAs)
- Forward secret (ephemeral keys)

**STT (STC) differences:**

- Pre-shared seeds (no PKI)
- Deterministic keys (no forward secrecy)
- STC.hash (content addressing)

**Could combine?** Yes - future consideration (TLS for transport, STC for content) - but redundant

**Result:** STC sufficient for Seigr ecosystem, simpler trust model

## Seigr Ecosystem Vision

### The Big Picture

**Seigr ecosystem goals:**

1. **Decentralized content storage** (no central servers)
2. **Content-addressed** (data identified by STC.hash)
3. **Privacy-preserving** (encryption mandatory)
4. **Resilient** (distributed, redundant)
5. **Efficient** (peer-to-peer, no unnecessary hops)

**STT's role:**

- **Transport layer** for Seigr ecosystem
- Connects peers securely (STC encryption)
- Supports DHT (peer discovery, content routing)
- Enables content distribution (many-to-many)

**Analogy:** STT is like "HTTP for Seigr" - the protocol that makes the ecosystem work.

### Current Capabilities

**Core Features:**

- ✅ One-to-one and many-to-many sessions
- ✅ STC encryption
- ✅ UDP/WebSocket transports
- ✅ Stream multiplexing
- ✅ DHT (Kademlia + STC.hash)
- ✅ Peer and content discovery
- ✅ Content-addressed storage
- ✅ Server mode (one-to-many streaming)
- ✅ NAT traversal (STUN-like)
- ✅ Content distribution with chunking

**Designed for Seigr ecosystem:**  Distributed content network, automated peer discovery, content-addressed storage

## Lessons from Other Systems

### From BitTorrent

**Learned:**

- DHT works at scale (Kademlia proven)
- Content addressing enables distribution (hash-based)
- Many-to-many reduces single points of failure

**Applied to STT:**

- Kademlia DHT with STC.hash (implemented)
- Content-addressed from start (STC.hash native)
- Architecture supports many peers (session manager handles multiple)

### Session Continuity Approach

**STT session continuity differs from connection migration:**

- **UDP default with custom reliability** (application-level)
- **Stream multiplexing** (independent flows)
- **Session continuity**:
  - Session identity derived from cryptographic seeds
  - Can resume across transports (UDP ↔ WebSocket)
  - Can resume across devices with same seeds
- **Probabilistic reliability**:
  - Delivery probability based on Shannon entropy
  - No manual configuration of reliable/unreliable flags

### From WebRTC

**Learned:**

- NAT traversal is hard (STUN/TURN necessary)
- Signaling out-of-band (need coordination)
- Browser use cases matter (WebSocket support)

**Applied to STT:**

- WebSocket transport (firewall-friendly)
- NAT traversal implemented (STUN-like functionality)
- Future: JavaScript client for browsers

### From Seigr Requirements

**Learned:**

- STC.hash must be native (content addressing)
- Privacy critical (encryption mandatory, not optional)
- Deterministic keys useful (same seed → same hash)

**Applied to STT:**

- STC-only (no AES/TLS alternative)
- All payloads encrypted (cannot disable)
- Pre-shared seeds (deterministic derivation)

## Common Criticisms and Responses

### "No forward secrecy is insecure"

**Criticism:** Compromised seed exposes all past sessions

**Response:**

- **True** - this is a known limitation
- **Mitigation:** Secure seed storage (HSM), rotation
- **Trade-off:** Deterministic keys needed for content addressing (Seigr ecosystem requirement)
- **Research:** Key ratcheting could add forward secrecy while preserving deterministic content keys (not scheduled)

### "Pre-shared seeds don't scale"

**Criticism:** Can't connect to millions of unknown peers (like HTTP can)

**Response:**

- **True** - STT not designed for public internet (like HTTP)
- **Use case:** Private networks, known peers, Seigr ecosystem (pre-authorized)
- **Alternative:** If need public access, use HTTP/TLS (different use case)
- **Research:** Optional certificate auth for hybrid trust model (not scheduled)

### "Custom crypto is dangerous"

**Criticism:** STC not standardized or audited like TLS

**Response:**

- **Valid concern** - custom crypto risky
- **Mitigation:** STC developed by cryptographers, will undergo audit
- **Rationale:** STC.hash required for Seigr (standard crypto doesn't provide this)
- **Future:** Security audit planned (before v1.0 production release)

### "Why not just use HTTP/gRPC/QUIC?"

**Criticism:** Reinventing the wheel

**Response:**

- **Existing protocols** not designed for Seigr ecosystem (no STC, no content addressing)
- **STT specific** to Seigr needs (DHT + STC + P2P + content distribution)
- **Novel features** provide QUIC benefits without QUIC complexity
- **Trade-off:** Custom protocol more work, but optimal for Seigr

## Current Status and Research Directions

### Implemented Features

**Core Protocol:**

- One-to-one and many-to-many sessions
- STC encryption with deterministic content addressing
- UDP and WebSocket transports
- Stream multiplexing

**P2P Capabilities:**

- Kademlia DHT with STC.hash
- Automatic peer and content discovery
- Server mode (one-to-many streaming)
- Content distribution with chunking
- NAT traversal (STUN-like functionality)

**Additional Features (0.2.0a0):**

- Adaptive priority (content property-based)
- Probabilistic delivery (entropy-based)
- Session continuity (seed-based resumption)
- Content-affinity pooling (hash proximity)

### Research Areas

**Potential enhancements under investigation:**

- Key ratcheting for forward secrecy (while preserving deterministic content keys)
- Post-quantum cryptographic algorithms
- Hybrid authentication models (seeds + optional certificates)
- Connection migration for mobile scenarios (may be superseded by session continuity)

These are research directions, not committed roadmap items. Development prioritizes Seigr ecosystem needs.

### Long-Term Vision

**Long-term goals:**

- Standard transport for Seigr ecosystem
- Reference implementation of STC-based networking
- Scale to large deployments
- Security audit and hardening

**Seigr ecosystem goals:**

- Decentralized content network using STC
- End-to-end encryption
- Distributed architecture
- DHT-based discovery

**STT's role:** Protocol layer for Seigr ecosystem.

## Key Takeaways

- **Design for Seigr first:** STT optimized for Seigr ecosystem needs (STC, content addressing, DHT)
- **Pre-shared seeds:** Simpler trust model than PKI, aligns with privacy goals, enables deterministic keys
- **STC-only:** Unified cryptography, content addressing native, trade-off vs standard crypto
- **Incremental development:** Continuous feature delivery guided by ecosystem needs
- **Binary protocol:** Efficiency over convenience (debugging harder but performance better)
- **Trade-offs explicit:** No forward secrecy (determinism needed), no PKI (simpler trust), custom protocol (Seigr-specific)
- **Learned from others:** BitTorrent (DHT), QUIC concepts (streams), WebRTC (NAT)
- **Implementation details:** Content-derived priority, entropy-based reliability, seed-based continuity, hash-affinity pooling
- **Criticisms valid:** Custom crypto risky (will audit), pre-shared seeds don't scale (different use case), custom protocol (Seigr-specific needs)
- **Current features:** DHT, NAT traversal, content distribution, server mode, adaptive priority, probabilistic delivery, session continuity, affinity pooling
- **Goals:** STT as Seigr ecosystem transport - decentralized, encrypted, content-addressed
