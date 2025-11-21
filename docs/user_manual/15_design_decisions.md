# Chapter 15: Design Decisions and Trade-offs

## Introduction

This chapter explains **why** STT is designed the way it is - the reasoning behind key decisions, trade-offs made, and the vision for the Seigr ecosystem.

## Core Design Principles

### 1. Seigr Ecosystem First

**Decision:** Build STT specifically for Seigr ecosystem needs

**Rationale:**

- Seigr requires content-addressed storage (STC.hash native)
- Distributed network needs peer-to-peer (not client-server)
- Privacy-focused (encryption mandatory, not optional)
- Decentralized (no central authorities)

**Trade-off:** Less general-purpose than HTTP/WebRTC, but optimal for Seigr use case

**Alternative rejected:** Use existing protocols (HTTP, BitTorrent) - don't integrate STC natively

### 2. Pre-Shared Seeds (Not PKI)

**Decision:** Require pre-shared seeds for authentication (no public key cryptography)

**Rationale:**

- Simpler trust model (no certificate authorities, no PKI complexity)
- Deterministic keys useful (same seed → same keys, helps content addressing)
- Lower computational cost (no RSA/ECDH handshake)
- Aligns with Seigr's privacy model (pre-authorized peers)

**Trade-off:** Cannot connect to arbitrary peers (like HTTPS can) - requires out-of-band seed distribution

**Alternative rejected:** TLS-style PKI - adds complexity, CAs centralized, ephemeral keys incompatible with deterministic content addressing

### 3. STC Instead of Standard Crypto

**Decision:** Use STC (Seigr Temporal Cryptography) exclusively

**Rationale:**

- STC.hash integral to Seigr (content addressing, DHT distances)
- Unified cryptography across ecosystem (one library)
- Probabilistic hashing (collisions tolerated - design choice for Seigr)

**Trade-off:** Not standardized (IETF), not audited like TLS, unfamiliar to developers

**Alternative rejected:** TLS/AES - doesn't provide STC.hash, deterministic keys harder

### 4. Phased Development Roadmap

**Decision:** Build incrementally - v0.2.0 (one-to-one) → v0.4.0 (DHT) → v0.5.0 (content distribution)

**Rationale:**

- Ship working software early (v0.2.0 useful for direct P2P)
- Validate architecture before adding complexity (DHT, many-to-many)
- Learn from real usage (adapt design based on feedback)

**Trade-off:** Current v0.2.0-alpha appears limited (one-to-one only) - must explain "future vision"

**Alternative rejected:** Wait until DHT complete - delays getting feedback, risks building wrong thing

### 5. Binary Protocol (Not Text)

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

**Alternative:** Hybrid (deterministic content keys + ephemeral session keys) - future consideration (v0.7.0)

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

**Alternative:** Build on QUIC - considered for future (v0.3.0 may add QUIC transport)

### One-to-One Now, Many-to-Many Later

**Chosen:** v0.2.0-alpha is one-to-one; DHT/content distribution in v0.4.0+

**Why:**

- Incremental delivery (ship working software early)
- Validate design (test one-to-one before scaling to many-to-many)
- Complexity management (DHT is hard - get fundamentals right first)

**Consequence:** Current version appears limited - documentation must explain roadmap

**Alternative:** Wait for DHT - delays real-world testing, risks building wrong thing

**Result:** Clear roadmap communicated (v0.2.0 → v0.4.0 → v0.5.0)

## Why Not Existing Protocols?

### Why Not HTTP/3 (QUIC)?

**HTTP/3:**

- Designed for web (client-server, request-response)
- QUIC provides transport (reliability, encryption)
- Not peer-to-peer native

**STT advantages:**

- Native P2P (symmetric peers)
- STC integration (content addressing)
- Seigr-specific (DHT, Kademlia XOR distances)

**Could use HTTP/3 as transport?** Maybe (future consideration for v0.3.0 QUIC transport)

### Why Not WebRTC?

**WebRTC:**

- Designed for browsers (peer-to-peer video calls)
- Complex signaling (requires server for NAT traversal)
- Heavy (media codecs, STUN/TURN infrastructure)

**STT advantages:**

- Simpler (no media codecs - general binary protocol)
- Standalone (no browser required)
- Seigr-specific (STC, content addressing)

**Similarities:** Both P2P, both need NAT traversal

**Result:** STT learns from WebRTC (ICE, STUN/TURN planned for v0.3.0)

### Why Not BitTorrent Protocol?

**BitTorrent:**

- Designed for file sharing (many-to-many)
- DHT-based (Kademlia - similar to STT's planned DHT)
- Proven at scale (millions of users)

**STT advantages:**

- General streaming (not just files)
- STC encryption (BitTorrent encryption optional, not content-addressed)
- Real-time capable (not just bulk transfer)

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

### Roadmap Alignment

**Phase 1 (v0.2.0-alpha - CURRENT):**

- ✅ One-to-one sessions
- ✅ STC encryption
- ✅ UDP/WebSocket transports
- ✅ Stream multiplexing

**Use case:** Secure direct P2P (file sharing, messaging)

**Phase 2 (v0.3.0):**

- NAT traversal (STUN/TURN/ICE)
- Connection migration (WiFi → LTE)
- QUIC transport (optional)

**Use case:** Better connectivity (through firewalls, mobile)

**Phase 3 (v0.4.0):**

- **DHT (Kademlia + STC.hash)**
- Peer discovery (find content without manual IPs)
- Content addressing (request by STC.hash)

**Use case:** Discover peers automatically, request content by hash

**Phase 4 (v0.5.0):**

- **Many-to-many content distribution**
- Server-to-many streaming
- Content replication (redundancy)
- **Seigr ecosystem backbone**

**Use case:** Distributed content network, Seigr applications

**Phase 5 (v0.6.0+):**

- Priority streams (QoS)
- Connection pooling (optimization)
- Advanced features

**This roadmap is critical** - STT is designed for Phase 4+, but shipped Phase 1 first.

## Lessons from Other Systems

### From BitTorrent

**Learned:**

- DHT works at scale (Kademlia proven)
- Content addressing enables distribution (hash-based)
- Many-to-many reduces single points of failure

**Applied to STT:**

- Planned DHT (Kademlia + STC.hash)
- Content-addressed from start (STC.hash native)
- Architecture supports many peers (session manager handles multiple)

### From QUIC

**Learned:**

- UDP-based can be reliable (application-level control)
- Multiplexing avoids head-of-line blocking (streams)
- Fast connection setup (0-RTT)

**Applied to STT:**

- UDP default (application reliability layer)
- Stream multiplexing (independent flows)
- Future: Consider QUIC as transport (v0.3.0)

### From WebRTC

**Learned:**

- NAT traversal is hard (STUN/TURN necessary)
- Signaling out-of-band (need coordination)
- Browser use cases matter (WebSocket support)

**Applied to STT:**

- WebSocket transport (firewall-friendly)
- Planned NAT traversal (v0.3.0)
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
- **Future:** Key ratcheting (v0.7.0) adds forward secrecy while preserving deterministic content keys

### "Pre-shared seeds don't scale"

**Criticism:** Can't connect to millions of unknown peers (like HTTP can)

**Response:**

- **True** - STT not designed for public internet (like HTTP)
- **Use case:** Private networks, known peers, Seigr ecosystem (pre-authorized)
- **Alternative:** If need public access, use HTTP/TLS (different use case)
- **Future:** Optional certificate auth (v0.9.0) for hybrid trust model

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
- **Could use as transport** - considered (QUIC for v0.3.0)
- **Trade-off:** Custom protocol more work, but optimal for Seigr

## Future Direction

### Planned Features (v0.3.0 - v1.0)

**v0.3.0 (NAT Traversal):**

- STUN, TURN, ICE
- Connection migration
- QUIC transport

**v0.4.0 (DHT):**

- Kademlia DHT with STC.hash
- Peer discovery
- Content addressing

**v0.5.0 (Content Distribution):**

- Many-to-many
- Server-to-many streaming
- Content replication

**v0.6.0 (Optimization):**

- Priority streams, QoS
- Connection pooling
- Performance tuning

**v0.7.0 (Key Ratcheting):**

- Forward secrecy (ratcheting keys)
- While preserving deterministic content keys

**v0.8.0 (Post-Quantum):**

- Quantum-resistant algorithms
- Future-proof security

**v0.9.0 (Hybrid Auth):**

- Optional certificates
- Hybrid trust model (seeds + certs)

**v1.0.0 (Production):**

- Security audit
- Stable API
- Production-ready

### Long-Term Vision

**STT becomes:**

- Standard transport for Seigr ecosystem
- Reference implementation of STC-based networking
- Proven at scale (millions of nodes)
- Battle-tested (secure, reliable, performant)

**Seigr ecosystem becomes:**

- Decentralized content network (like BitTorrent but STC-based)
- Privacy-preserving (all encrypted)
- Resilient (distributed, no single point of failure)
- Accessible (DHT-based discovery, no manual configuration)

**STT's role:** The protocol that makes it all work.

## Key Takeaways

- **Design for Seigr first:** STT optimized for Seigr ecosystem needs (STC, content addressing, DHT)
- **Pre-shared seeds:** Simpler trust model than PKI, aligns with privacy goals, enables deterministic keys
- **STC-only:** Unified cryptography, content addressing native, trade-off vs standard crypto
- **Phased roadmap:** Ship early (v0.2.0 one-to-one), build toward vision (v0.5.0 many-to-many)
- **Binary protocol:** Efficiency over convenience (debugging harder but performance better)
- **Trade-offs explicit:** No forward secrecy (determinism needed), no PKI (simpler trust), custom protocol (Seigr-specific)
- **Learned from others:** BitTorrent (DHT), QUIC (streams), WebRTC (NAT), applied to Seigr context
- **Criticisms valid:** Custom crypto risky (will audit), pre-shared seeds don't scale (different use case), reinventing wheel (Seigr-specific needs)
- **Future clear:** NAT (v0.3.0), DHT (v0.4.0), content distribution (v0.5.0), production (v1.0)
- **Vision:** STT as Seigr ecosystem backbone - decentralized, encrypted, content-addressed, resilient
