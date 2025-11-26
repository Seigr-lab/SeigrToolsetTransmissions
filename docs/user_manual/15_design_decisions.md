# Chapter 15: Design Decisions and Trade-offs

## Introduction

This chapter explains **why** STT is designed the way it is - the reasoning behind key decisions and trade-offs made.

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

### 2. Privacy and Encryption First

**Decision:** Build STT with mandatory encryption and decentralized capability

**Rationale:**

- Privacy-focused (encryption mandatory, not optional)
- Decentralized (no central authorities required)
- Multi-peer encrypted transport foundation for building distributed applications
- Peer-to-peer capable (not limited to client-server)

**Trade-off:** Less general-purpose than HTTP/WebRTC, but optimal for privacy-focused binary transmission

**Alternative rejected:** Use existing protocols (HTTP, BitTorrent) - don't integrate STC natively

### 3. Pre-Shared Seeds (Not PKI)

**Decision:** Require pre-shared seeds for authentication (no public key cryptography)

**Rationale:**

- Simpler trust model (no certificate authorities, no PKI complexity)
- Deterministic keys from seeds enable consistent peer authentication
- Lower computational cost (no RSA/ECDH handshake)
- Aligns with Seigr's privacy model (pre-authorized peers)

**Trade-off:** Cannot connect to arbitrary peers (like HTTPS can) - requires out-of-band seed distribution

**Alternative rejected:** TLS-style PKI - adds complexity, CAs centralized

### 4. STC Instead of Standard Crypto

**Decision:** Use STC (Seigr Toolset Crypto) exclusively

**Rationale:**

- STC.hash provides cryptographic hashing for content addressing
- Unified cryptography from Seigr Labs toolset
- Probabilistic hashing (collisions tolerated - design choice)

**Trade-off:** Not standardized (IETF), not audited like TLS, unfamiliar to developers

**Alternative rejected:** TLS/AES - doesn't provide STC.hash for content addressing

### 5. Incremental Development

**Decision:** Build incrementally with continuous feature delivery

**Rationale:**

- Ship working software early (validate architecture quickly)
- Adapt design based on real usage and feedback
- Avoid over-engineering features not yet needed

**Result:** STT now includes core features: encrypted sessions, streams, binary protocol, server mode

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

- Same seed must produce same keys (consistent peer authentication)
- Pre-shared seed authentication model requires deterministic derivation
- Forward secrecy needs ephemeral keys (random each session)

**Consequence:** Compromised seed exposes all past sessions (if attacker recorded traffic)

**Mitigation:** Seed rotation, secure storage (HSM)

**Alternative:** Hybrid (deterministic authentication + ephemeral session keys) - under research

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

- **Multi-peer streaming**: send_to_all() and send_to_sessions() for broadcast/multicast
- **Session management**: Multiple simultaneous encrypted connections
- **Stream multiplexing**: Independent data streams within sessions
- **Transport agnostic**: Works over UDP or WebSocket

### Peer-to-Peer Design

**Chosen:** Peer-to-peer architecture with server mode

**Why:**

- Symmetric peer design (any node can serve or request)
- Distributed architecture eliminates single points of failure
- Multi-peer connections enable network layer applications to build on top

**Result:** STT provides multi-peer encrypted transport: server mode accepts incoming connections, manual peer connections via connect_udp(), broadcast/multicast primitives

**Alternative:** Client-server only - simpler but limits use cases for decentralized applications

**Note:** STT is a transport layer. Network formation, peer discovery, and routing logic must be implemented by applications built on top of STT.

## Why Not Existing Protocols?

### Why Not HTTP/3 (QUIC)?

**HTTP/3:**

- Designed for web (client-server, request-response)
- QUIC provides transport (reliability, encryption)
- Not peer-to-peer native

**STT advantages:**

- Native P2P (symmetric peers)
- STC integration for ecosystem cryptography
- Seigr-specific (encrypted sessions, binary protocol)
- Multi-peer primitives (send_to_all, send_to_sessions)

### Why Not WebRTC?

**WebRTC:**

- Designed for browsers (peer-to-peer video calls)
- Complex signaling (requires server for NAT traversal)
- Heavy (media codecs, STUN/TURN infrastructure)

**STT advantages:**

- Simpler (no media codecs - general binary protocol)
- Standalone (no browser required)
- Seigr-specific (STC, content addressing)
- Encrypted by default using Seigr Toolset Crypto v0.4.1

**Similarities:** Both P2P, both require network configuration for NAT scenarios

**Note:** NAT traversal features are not currently implemented (manual port forwarding required)

### Why Not BitTorrent Protocol?

**BitTorrent:**

- Designed for file sharing (many-to-many)
- Proven at scale (millions of users)

**STT advantages:**

- General streaming (not just files)
- STC encryption (BitTorrent encryption optional)
- Real-time capable (not just bulk transfer)
- Application-agnostic binary transport

**Similarities:** Both P2P protocols designed for decentralized content

**Note:** STT uses manual peer connections (connect_udp with IP:port). Applications built on STT can implement their own peer discovery mechanisms.

### Why Not TLS/DTLS?

**TLS (Transport Layer Security):**

- Standard (IETF RFCs, widely deployed)
- PKI-based (certificates, CAs)
- Forward secret (ephemeral keys)

**STT (STC) differences:**

- Pre-shared seeds (no PKI)
- Deterministic keys (no forward secrecy)
- STC.hash for cryptographic hashing

**Could combine?** Yes - future consideration (TLS for transport, STC for content) - but redundant

**Result:** STC sufficient for binary transmission needs, simpler trust model

## STT Vision and Purpose

### The Big Picture

**STT purpose:**

1. **Encrypted binary transmission** (mandatory encryption)
2. **Privacy-preserving** (pre-shared seed model)
3. **Multi-peer capable** (peer-to-peer communication)
4. **Application-agnostic** (zero assumptions about data)

**STT's role:**

- **Transport layer** for binary applications
- Connects peers securely (STC encryption)
- Enables peer-to-peer communication
- Provides multi-peer primitives (broadcast/multicast)
- Foundation for applications to build on

**Analogy:** STT is like "encrypted UDP for P2P" - the protocol that provides secure multi-peer transport for binary applications.

### Current Capabilities

**Core Features:**

- ✅ One-to-one and one-to-many sessions (multiple simultaneous peers)
- ✅ STC encryption (Seigr Toolset Crypto v0.4.1)
- ✅ UDP/WebSocket transports
- ✅ Stream multiplexing
- ✅ Server mode (accepts incoming connections)
- ✅ Binary protocol with efficient encoding
- ✅ Multi-peer primitives (send_to_all, send_to_sessions)
- ✅ Manual peer connection (connect_udp with IP:port)

**Application Layer Responsibilities:**

Applications built on STT must implement:

- Peer discovery mechanisms
- Network topology management
- Routing decisions
- Content distribution logic

**Designed as transport foundation:** STT provides secure multi-peer encrypted transport. Applications implement network formation and routing logic on top.

## Lessons from Other Systems

### From BitTorrent

**Learned:**

- Many-to-many reduces single points of failure
- P2P architecture provides resilience

**Applied to STT:**

- Architecture supports many peers (session manager handles multiple)
- P2P design avoids centralization
- Multi-peer primitives (send_to_all, send_to_sessions)

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
- JavaScript client support possible (browsers)

### From Seigr Requirements

**Learned:**

- STC.hash provides cryptographic hashing for ecosystem
- Privacy critical (encryption mandatory, not optional)
- Deterministic keys useful for peer authentication

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
- **Trade-off:** Deterministic keys needed for peer authentication
- **Research:** Key ratcheting could add forward secrecy (not scheduled)

### "Pre-shared seeds don't scale"

**Criticism:** Can't connect to millions of unknown peers (like HTTP can)

**Response:**

- **True** - STT not designed for public internet (like HTTP)
- **Use case:** Private networks, known peers, pre-authorized connections
- **Alternative:** If need public access, use HTTP/TLS (different use case)

### "Custom crypto is dangerous"

**Criticism:** STC not standardized or audited like TLS

**Response:**

- **Valid concern** - custom crypto risky
- **Mitigation:** STC developed by cryptographers at Seigr Labs
- **Rationale:** STC.hash required for content-addressed cryptographic hashing

### "Why not just use HTTP/gRPC/QUIC?"

**Criticism:** Reinventing the wheel

**Response:**

- **Existing protocols** don't integrate STC encryption and content addressing
- **STT specific** needs (STC + P2P + multi-peer primitives)
- **Novel features** provide multi-peer encrypted transport foundation
- **Trade-off:** Custom protocol more work, but optimal for binary transmission with STC

## Current Status

### Implemented Features

**Core Protocol:**

- One-to-one and one-to-many sessions (multiple simultaneous peers)
- STC encryption (Seigr Toolset Crypto v0.4.1)
- UDP and WebSocket transports
- Stream multiplexing

**P2P Capabilities:**

- Server mode (accepts incoming connections)
- Manual peer connections with pre-shared seeds (connect_udp)
- Session manager for multiple concurrent peers
- Multi-peer primitives (send_to_all, send_to_sessions)

**Transport Foundation:**

STT provides encrypted multi-peer transport. Applications built on STT implement their own:

- Peer discovery mechanisms
- Network topology management
- Routing algorithms
- Content distribution strategies

### Research Areas

**Potential enhancements under investigation:**

### Long-Term Vision

**STT's purpose:**

- Binary transmission protocol with mandatory encryption
- Reference implementation of STC-based networking
- Multi-peer encrypted transport layer

**Development goals:**

- Privacy-preserving binary transmission
- End-to-end encryption for all communications
- Distributed peer-to-peer capable architecture

**STT's role:** Encrypted multi-peer transport layer for binary applications.

## Key Takeaways

- **Privacy and encryption first:** STT designed for encrypted binary transmission (STC, content addressing, P2P)
- **Pre-shared seeds:** Simpler trust model than PKI, aligns with privacy goals, enables deterministic keys
- **STC-only:** Unified cryptography from Seigr Labs toolset, content addressing native, trade-off vs standard crypto
- **Incremental development:** Continuous feature delivery based on real needs
- **Binary protocol:** Efficiency over convenience (debugging harder but performance better)
- **Trade-offs explicit:** No forward secrecy (determinism needed), no PKI (simpler trust), custom protocol (STC-specific)
- **Learned from others:** P2P resilience concepts from BitTorrent, stream multiplexing ideas from QUIC, NAT challenges from WebRTC
- **Implementation details:** Multi-peer primitives (send_to_all, send_to_sessions), session management, stream multiplexing
- **Criticisms valid:** Custom crypto risky, pre-shared seeds don't scale to public internet, custom protocol learning curve
- **Current features:** STC encryption, server mode, multi-peer capabilities, manual peer connections
- **Transport foundation:** STT provides encrypted multi-peer transport; applications implement network formation logic
- **Goals:** Binary transmission protocol - decentralized, encrypted, P2P-capable
