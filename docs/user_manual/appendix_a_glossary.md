# Appendix A: Glossary

## Complete STT Terminology Reference

This glossary defines all technical terms used in STT documentation. Terms are organized alphabetically with clear, factual definitions.

---

### A

**AEAD (Authenticated Encryption with Associated Data)**  
A mode of encryption that provides both confidentiality and authenticity. STC's frame encryption provides AEAD-like properties by including frame headers in the encryption context.

**Associated Data**  
Data that is authenticated but not encrypted. In STT, frame headers (session ID, stream ID, sequence) are included in the encryption as associated data.

**Asynchronous / Async**  
A programming pattern where operations don't block - code continues executing while waiting for results. STT uses Python's `async`/`await` for non-blocking I/O.

**AUTH_PROOF**  
The third message in STT's handshake protocol, where the initiator proves they successfully decrypted the responder's challenge.

---

### B

**Binary Protocol**  
A protocol that uses raw bytes rather than text strings for communication. STT uses binary framing for efficiency.

**Bit**  
A single binary digit: 0 or 1. The smallest unit of data in computing.

**Byte**  
8 bits grouped together. Can represent values 0-255 (unsigned) or -128 to 127 (signed).

---

### C

**CEL (Continuous Entropy Lattice)**  
A component of STC that provides evolving entropy. Not directly exposed in STT but used internally by STC.

**Chamber**  
STT's encrypted storage system for keys and session metadata, secured with STC.

**Challenge**  
In the handshake, the encrypted payload sent by the responder that the initiator must decrypt to prove possession of the shared seed.

**Chunk**  
A portion of data split for transmission. Large data is divided into chunks that fit within frame size limits.

**Ciphertext**  
Encrypted data. The output of encryption operations.

**CKE (Contextual Key Emergence)**  
STC's key derivation component. Used by STT for deriving session keys.

**Client-Server**  
An architecture where clients make requests to servers. Opposite of peer-to-peer. STT supports peer-to-peer, not client-server.

**Commitment**  
A cryptographic hash sent in the HELLO message that binds the initiator to their nonce, preventing the responder from manipulating it.

**CONTROL Frame**  
A frame type (0x03) used for control messages like session termination or errors.

---

### D

**DATA Frame**  
The most common frame type (0x02) used for transmitting application data.

**Datagram**  
A self-contained packet of data. UDP sends datagrams. STT frames are transmitted as UDP datagrams or WebSocket messages.

**Decryption**  
The process of converting ciphertext back to plaintext using a key.

**Deterministic**  
Produces the same output for the same input every time. Traditional cryptography is deterministic; STC is probabilistic.

**DSF (Data State Folding)**  
STC's encryption component. Used by STT for frame encryption.

---

### E

**Encryption**  
The process of converting plaintext to ciphertext to protect confidentiality.

**Endpoint**  
A network address (IP + port) where a node can be reached.

**Ephemeral**  
Short-lived, temporary. Ephemeral keys are generated for a single session and discarded after use.

---

### F

**FINAL**  
The fourth and final message in STT's handshake protocol, confirming session establishment.

**Flags**  
A byte in the frame header indicating special conditions (e.g., final frame in stream, error).

**Flow Control**  
Mechanisms to prevent sender from overwhelming receiver. STT implements credit-based flow control.

**Frame**  
The basic unit of data transmission in STT. Contains header, encrypted payload, and crypto metadata.

**Frame Type**  
A byte indicating the purpose of a frame: HANDSHAKE (0x01), DATA (0x02), CONTROL (0x03), etc.

---

### G

**gRPC**  
A modern RPC framework using Protocol Buffers and HTTP/2. Compared with STT in Chapter 14.

---

### H

**Handshake**  
The process of establishing a session between two peers. STT uses a 4-message handshake: HELLO, RESPONSE, AUTH_PROOF, FINAL.

**HANDSHAKE Frame**  
A frame type (0x01) used during the handshake process.

**Hash**  
A one-way function that produces a fixed-size output from any input. STC uses PHE for hashing.

**Header**  
The fixed portion at the start of a frame containing metadata: magic bytes, type, session ID, stream ID, sequence, flags.

**HELLO**  
The first message in STT's handshake protocol, sent by the initiator to begin authentication.

**Hexadecimal (Hex)**  
Base-16 number system using digits 0-9 and A-F. Used to represent bytes compactly (e.g., 0xFF = 255).

**HTTP/HTTPS**  
The protocol used for web browsing. Compared with STT in Chapter 14.

---

### I

**Initiator**  
The peer that starts a handshake by sending the HELLO message.

**IP Address**  
Internet Protocol address. Identifies a device on a network (e.g., 192.168.1.100 or 2001:db8::1).

---

### K

**Key**  
Secret data used for encryption and decryption. STT uses STC-derived keys.

**Key Derivation**  
The process of generating cryptographic keys from other data. STT uses CKE for key derivation.

**Key Rotation**  
Replacing an encryption key with a new one during a long session. Triggered by data/time/message thresholds.

---

### L

**Latency**  
The time delay between sending and receiving data. Lower is better for real-time applications.

**Local**  
Referring to this computer/node. Opposite of remote/peer.

---

### M

**Magic Bytes**  
The first two bytes of every STT frame: 0x53 0x54 (ASCII "ST"). Used to identify STT frames.

**Metadata**  
Data about data. In STT: crypto metadata (nonce, parameters needed for decryption) and frame metadata (headers).

**MITM (Man-in-the-Middle)**  
An attack where an attacker intercepts communication between two peers. STT's handshake provides MITM resistance.

**Multiplexing**  
Sending multiple streams over one connection. STT supports stream multiplexing within sessions.

**Mutual Authentication**  
Both peers verify each other's identity. STT's handshake provides mutual authentication.

---

### N

**NAT (Network Address Translation)**  
A network technique that allows multiple devices to share one public IP. Can complicate peer-to-peer connections.

**Node**  
A device or program running the STT protocol. Each node has a unique node ID.

**Node ID**  
A 32-byte identifier uniquely identifying a node. Derived from the node seed using STC.

**Node Seed**  
Random bytes (32+ recommended) used to initialize STC and generate a node ID. Should be unique per node.

**Nonce**  
"Number used once" - random data used only once to ensure uniqueness. Handshake generates fresh nonces each time.

---

### O

**Out-of-Band**  
Communication happening outside the primary channel. Shared seeds must be distributed out-of-band (not via STT itself).

---

### P

**Packet**  
A unit of data transmitted over a network. Lower-level than frames.

**Payload**  
The actual data content of a frame, excluding headers and metadata.

**PCF (Polymorphic Cryptographic Flow)**  
STC's algorithmic morphing component. Used internally by STC.

**Peer**  
Another node you're communicating with. The relationship is symmetric - you're also their peer.

**Peer-to-Peer (P2P)**  
Architecture where participants communicate directly without a central server. STT is peer-to-peer.

**PHE (Probabilistic Hashing Engine)**  
STC's hashing component. Used for node IDs, commitments, and content hashing.

**Plaintext**  
Unencrypted data. The input to encryption operations.

**Port**  
A number (0-65535) identifying a specific service on a device. Like an apartment number.

**Pre-Shared Seed**  
A secret that both peers must have before connecting. Core to STT's authentication model.

**Probabilistic**  
Produces different outputs for the same input due to randomness. STC encryption is probabilistic.

**Proof**  
In the handshake, encrypted evidence that proves successful decryption and correct session ID calculation.

**Protocol**  
A set of rules for communication between computers.

---

### Q

**QUIC**  
A modern UDP-based transport protocol. Compared with STT in Chapter 14.

---

### R

**Remote**  
Referring to the other computer/peer. Opposite of local.

**Replay Attack**  
Reusing old legitimate messages to impersonate. STT's nonces prevent replay attacks.

**Responder**  
The peer that receives the HELLO and responds with RESPONSE during handshake.

**RESPONSE**  
The second message in STT's handshake, sent by the responder containing the encrypted challenge.

**Round Trip Time (RTT)**  
Time for a message to go from sender to receiver and back. STT's handshake takes 2 RTTs.

---

### S

**Seed**  
Random data used to initialize cryptography. STT uses two types: node seed and shared seed.

**Sequence Number**  
A counter in each frame header ensuring ordered delivery within a stream.

**Serialization**  
Converting data structures to bytes for transmission. STT uses a custom binary serialization format.

**Session**  
An active encrypted connection between two peers. Identified by an 8-byte session ID.

**Session ID**  
An 8-byte identifier for a session, derived during handshake via XOR of nonces and node IDs.

**Session Key**  
The encryption key used for a session, derived during the handshake.

**Shared Seed**  
Secret bytes (32+ recommended) that both peers must possess. Required for handshake authentication.

**STC (Seigr Toolset Crypto)**  
The cryptographic library used by STT. Provides probabilistic encryption, hashing, and key derivation.

**STCWrapper**  
STT's interface to STC cryptography. Centralizes all crypto operations.

**Stream**  
A logical channel within a session for ordered data transmission. Multiple streams can exist per session.

**Stream ID**  
An integer identifying a stream within a session. Encoded as varint. Stream 0 is reserved.

**STREAM_CONTROL Frame**  
A frame type (0x04) for stream-specific control messages.

**STT (Seigr Toolset Transmissions)**  
This protocol. A peer-to-peer binary streaming protocol using STC cryptography.

**STTFrame**  
The Python class representing an STT frame.

**STTHandshake**  
The Python class implementing STT's handshake protocol.

**STTNode**  
The Python class representing an STT node (the main runtime).

**STTSession**  
The Python class representing an active session between peers.

**STTStream**  
The Python class representing a stream within a session.

**Symmetric Encryption**  
Encryption where the same key is used for encryption and decryption. STT uses symmetric encryption (via STC).

---

### T

**TCP (Transmission Control Protocol)**  
A reliable, connection-oriented transport protocol. STT doesn't use TCP directly but WebSocket runs over TCP.

**Throughput**  
The rate of data transmission. Higher is better for bulk transfers.

**Timestamp**  
A point in time, usually in milliseconds. Used in handshake messages for freshness.

**TLS (Transport Layer Security)**  
Standard encryption protocol used by HTTPS. STT uses STC instead of TLS.

**Transport**  
The underlying network mechanism. STT supports UDP and WebSocket transports.

**Type Tag**  
A byte identifying data type in STT's serialization format (e.g., 0x31 = string, 0x40 = list).

---

### U

**UDP (User Datagram Protocol)**  
A connectionless transport protocol. STT can use UDP for low-latency communication.

**Unicast**  
Sending data to a single destination. STT is unicast (one-to-one), not broadcast or multicast.

---

### V

**Varint**  
Variable-length integer encoding. Small numbers use fewer bytes. Used for stream IDs and sequence numbers.

---

### W

**WebRTC (Web Real-Time Communication)**  
Browser-based peer-to-peer protocol. Compared with STT in Chapter 14.

**WebSocket**  
A protocol providing full-duplex communication over HTTP. STT can use WebSocket as a transport.

---

### X

**XOR (Exclusive OR)**  
A bitwise operation. STT uses XOR to derive session IDs from nonces and node IDs.

---

## Acronyms Quick Reference

- **AEAD**: Authenticated Encryption with Associated Data
- **CEL**: Continuous Entropy Lattice (STC component)
- **CKE**: Contextual Key Emergence (STC component)
- **DSF**: Data State Folding (STC component)
- **HTTP**: HyperText Transfer Protocol
- **IP**: Internet Protocol
- **MITM**: Man-in-the-Middle
- **NAT**: Network Address Translation
- **P2P**: Peer-to-Peer
- **PCF**: Polymorphic Cryptographic Flow (STC component)
- **PHE**: Probabilistic Hashing Engine (STC component)
- **RPC**: Remote Procedure Call
- **RTT**: Round Trip Time
- **STC**: Seigr Toolset Crypto
- **STT**: Seigr Toolset Transmissions
- **TCP**: Transmission Control Protocol
- **TLS**: Transport Layer Security
- **UDP**: User Datagram Protocol
- **XOR**: Exclusive OR

---

## Related Documentation

- For code-level details: [API Reference](../api_reference.md)
- For protocol details: [Protocol Specification](../protocol_spec.md)
- For examples: [Usage Examples](../examples.md)
- For conceptual understanding: [User Manual Chapters](00_INDEX.md)

---

**Note**: This glossary defines terms as used in STT. Some terms may have different meanings in other contexts.
