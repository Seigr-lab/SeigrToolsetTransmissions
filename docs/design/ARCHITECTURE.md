# STT Architecture & Design

**Version**: 0.2.0a0 (unreleased)  
**Status**: Pre-release Alpha - Functional core with 93%+ test coverage

---

## Table of Contents

1. [Design Philosophy](#design-philosophy)
2. [Protocol Stack](#protocol-stack)
3. [Agnostic Primitives](#agnostic-primitives)
4. [Frame Format](#frame-format)
5. [Security Model](#security-model)
6. [Transport Layer](#transport-layer)

---

## Design Philosophy

### Core Principle: Binary Agnosticism

**STT is a binary transport protocol that makes ZERO assumptions about data semantics.**

STT provides secure, ordered, multiplexed byte transmission. The application layer defines what those bytes mean.

#### What STT Provides

- **Binary Transport**: Secure delivery of arbitrary byte streams
- **Encryption**: STC-based post-classical cryptography
- **Multiplexing**: Multiple independent streams per session
- **Ordering**: Sequence-numbered segments guarantee ordering
- **Addressing**: SHA3-256 content addressing for routing
- **Framing**: Binary protocol for efficient encoding

#### What STT Does NOT Provide

- **Content Interpretation**: No file system, no message types, no media codecs
- **Application Semantics**: You define what bytes represent
- **Data Structure**: No assumptions about JSON, Protobuf, or any format
- **Business Logic**: Purely transport-layer functionality

### Use Cases (All Supported Equally)

- Video streaming (H.264, VP9, AV1 - your choice)
- Sensor networks (IoT telemetry)
- File transfer (any file type)
- P2P messaging (any message format)
- Custom binary protocols
- Blockchain data synchronization
- Any application requiring secure binary transport

---

## Protocol Stack

```
┌─────────────────────────────────────┐
│  Application Layer                  │  ← YOUR data format
│  (Semantic interpretation)          │
├─────────────────────────────────────┤
│  Endpoint Layer                     │  ← Named routing
│  (SHA3-256 content addressing)      │
├─────────────────────────────────────┤
│  Stream Layer                       │  ← Multiplexing
│  (Independent byte streams)         │
├─────────────────────────────────────┤
│  Session Layer                      │  ← Key management
│  (STC key derivation & rotation)    │
├─────────────────────────────────────┤
│  Frame Layer                        │  ← Binary encoding
│  (Encrypted STT frames)             │
├─────────────────────────────────────┤
│  Transport Layer                    │  ← Network delivery
│  (UDP / WebSocket)                  │
└─────────────────────────────────────┘
```

### Layer Responsibilities

1. **Application**: Defines data meaning, structure, business logic
2. **Endpoint**: Routes frames to named destinations (content-addressed)
3. **Stream**: Manages multiple independent data flows per session
4. **Session**: Handles authentication, key derivation, session lifecycle
5. **Frame**: Encodes/decodes binary frames with encryption
6. **Transport**: Sends/receives bytes over network (UDP or WebSocket)

---

## Agnostic Primitives

STT provides eight core primitives that work with ANY binary data:

### 1. BinaryStreamEncoder

Async generator yielding encrypted byte segments for transmission.

```python
from seigr_toolset_transmissions.streaming import BinaryStreamEncoder

encoder = BinaryStreamEncoder(
    stc_wrapper,
    session_id=b'12345678',
    stream_id=1,
    segment_size=65536  # 64KB segments
)

async for segment in encoder.send(binary_data):
    # segment = {'data': bytes, 'sequence': int}
    await transport.transmit(segment['data'])
```

**Key Features**:
- No assumptions about data content
- Automatic segmentation for network MTU
- STC encryption per segment
- Flow control via credit system

### 2. BinaryStreamDecoder

Reconstructs original bytes from encrypted segments.

```python
from seigr_toolset_transmissions.streaming import BinaryStreamDecoder

decoder = BinaryStreamDecoder(stc_wrapper, session_id, stream_id)

async for decrypted_chunk in decoder.receive():
    # decrypted_chunk = original bytes
    process_data(decrypted_chunk)
```

### 3. STTFrame

Binary frame protocol with fixed overhead and encryption.

```python
from seigr_toolset_transmissions.frame import STTFrame

frame = STTFrame(
    frame_type=0x02,        # DATA frame
    session_id=session_id,  # 8 bytes
    sequence=seq_num,       # Ordering
    stream_id=stream_id,    # Multiplexing
    payload=encrypted_data  # Arbitrary bytes
)

frame_bytes = frame.to_bytes()
```

### 4. STTSession

Session management with STC key derivation.

```python
from seigr_toolset_transmissions.session import STTSession

session = STTSession(
    session_id=b'12345678',
    peer_node_id=peer_id,
    stc_wrapper=stc_wrapper
)

# Session provides:
# - Encryption/decryption via STC
# - Key rotation
# - Sequence tracking
# - Metadata storage
```

### 5. STTNode

Full node runtime with handshake, sessions, streams.

```python
from seigr_toolset_transmissions.core import STTNode

node = STTNode(
    node_seed=b'node_secret_32bytes_minimum!',
    shared_seed=b'shared_secret_32bytes_min!!',
    host='0.0.0.0',
    port=8080
)

await node.start()
```

### 6. EndpointManager

Content-addressed routing to named handlers.

```python
from seigr_toolset_transmissions.endpoints import EndpointManager

endpoints = EndpointManager()

# Register handler for specific endpoint name
endpoints.register('sensor.telemetry', telemetry_handler)

# Frames route based on SHA3-256(endpoint_name)
```

### 7. StreamManager

Per-session multiplexing of independent byte streams.

```python
from seigr_toolset_transmissions.stream import StreamManager

manager = StreamManager(session_id, stc_wrapper)

# Create independent streams
video_stream = await manager.create_stream(stream_id=1)
audio_stream = await manager.create_stream(stream_id=2)

# Each stream has isolated encryption context
```

### 8. Handshake Protocol

Pre-shared seed authentication (4-message flow).

**Design Rationale**: STT requires pre-shared seeds for immediate mutual authentication without online key agreement. Seeds must be distributed out-of-band (QR codes, secure channels, etc).

**Flow**:
1. Initiator → `INIT` (session_id, node_id_A)
2. Responder → `CHALLENGE` (node_id_B, challenge)
3. Initiator → `RESPONSE` (response = STC_derive(challenge))
4. Responder → `CONFIRM` (session established)

---

## Frame Format

### Header (20 bytes fixed)

```
Offset | Size | Field           | Description
-------|------|-----------------|---------------------------
0      | 2    | magic           | 0x5354 ("ST")
2      | 1    | frame_type      | 0x01-0x7F (STT), 0x80-0xFF (custom)
3      | 8    | session_id      | 8-byte session identifier
11     | 4    | stream_id       | Stream number (0 = control)
15     | 4    | sequence        | Sequence number
19     | 1    | flags           | Control flags (unused currently)
```

### Payload (variable)

```
Offset | Size     | Field              | Description
-------|----------|--------------------|---------------------------
20     | 4        | payload_length     | Byte count of encrypted payload
24     | variable | encrypted_payload  | STC-encrypted application data
24+N   | 4        | metadata_length    | STC metadata size
28+N   | variable | crypto_metadata    | STC encryption context
```

### Frame Types (0x01-0x7F reserved for STT)

```
0x01 = HANDSHAKE_INIT
0x02 = HANDSHAKE_CHALLENGE
0x03 = HANDSHAKE_RESPONSE
0x04 = HANDSHAKE_CONFIRM
0x10 = DATA (arbitrary binary payload)
0x11 = STREAM_OPEN
0x12 = STREAM_CLOSE
0x13 = ACK
0x14 = KEEPALIVE
0x15 = DISCONNECT
0x20 = ENDPOINT_REGISTER
0x21 = ENDPOINT_RESOLVE
0x22 = ENDPOINT_ROUTE
```

**Custom Types (0x80-0xFF)**: Reserved for application-specific frame types.

---

## Security Model

### Cryptography: STC (External Dependency)

STT uses **Seigr Toolset Crypto** for all cryptographic operations:

- **Package**: `seigr-toolset-crypto>=0.4.0`
- **Algorithm**: Post-classical lattice-based encryption
- **Key Derivation**: STC CKE (Contextual Key Emergence)
- **Hashing**: STC PHE (Probabilistic Hashing Engine)
- **Streaming**: STC StreamingContext (132.9 FPS, 7.52ms latency)

See `docs/api/STC_DEPENDENCY_REFERENCE.md` for STC API details.

### Pre-Shared Seed Model

**Design Decision**: STT requires pre-shared seeds rather than online key agreement.

**Rationale**:
1. Immediate mutual authentication (no certificate authorities)
2. Zero online trust establishment
3. Perfect forward secrecy via session-specific derivation
4. Quantum-resistant (no public key exchange vulnerable to Shor's algorithm)

**Seed Distribution** (out-of-band):
- QR codes for physical device pairing
- Secure messaging channels
- Configuration files (encrypted storage)
- Hardware security modules (HSMs)

### Per-Session Key Derivation

Each session derives unique keys from:
- Node seed (32+ bytes, node-specific)
- Shared seed (32+ bytes, pre-distributed)
- Session ID (8 bytes, ephemeral)
- Peer node ID (32 bytes)

**Formula**:
```
session_key = STC_derive(
    node_seed,
    shared_seed,
    session_id,
    peer_node_id
)
```

### Per-Stream Encryption Isolation

Each stream within a session gets isolated encryption context:

```
stream_context = STC_StreamingContext(
    STC_derive(session_key, stream_id)
)
```

**Benefit**: Compromising one stream does NOT compromise other streams in the same session.

---

## Transport Layer

### UDP Transport (Primary)

- **Coverage**: 90%+
- **MTU**: 1472 bytes (Ethernet 1500 - 20 IP - 8 UDP)
- **Ordering**: Application-level via sequence numbers
- **Reliability**: Application-level retransmission (if needed)

**Use Case**: Low-latency streaming, IoT sensors, real-time data

### WebSocket Transport (Secondary)

- **Coverage**: 84%+
- **Implementation**: Native RFC 6455 (no external dependencies)
- **Benefits**: Browser compatibility, firewall-friendly
- **Drawback**: TCP overhead (head-of-line blocking)

**Use Case**: Web applications, restrictive networks, browser clients

### Transport Abstraction

```python
class TransportProtocol:
    async def send(self, data: bytes, address: tuple) -> None: ...
    async def receive(self) -> tuple[bytes, tuple]: ...
```

All higher layers are transport-agnostic. Adding new transports (QUIC, SCTP, etc) requires only implementing this interface.

---

## Component Coverage Status

**Overall**: 93.01% test coverage (2803 statements, 196 untested)

**By Layer**:
- Session Management: 100%
- Serialization: 100%
- Events: 100%
- Endpoints: 100%
- Crypto Wrappers: 100%
- Streaming Encoder: 100%
- Streaming Decoder: 96%+
- Stream Manager: 98.61%
- Frame Protocol: 90%
- UDP Transport: 90%
- Handshake: 87.36%
- WebSocket: 84.63%
- Node Runtime: 85.56%

**Untested Lines**: Primarily defensive exception handlers, race condition handlers, and complex integration paths requiring multi-node test environments.

---

## Design Trade-offs

### Pre-Shared Seeds vs Key Agreement

**Choice**: Pre-shared seeds  
**Trade-off**: Requires out-of-band distribution BUT provides immediate mutual authentication and quantum resistance  
**Justification**: Target use cases (IoT, P2P) can handle physical pairing; web PKI model not suitable

### Binary Agnosticism vs Type Safety

**Choice**: Pure binary transport  
**Trade-off**: No type checking or schema validation BUT maximum flexibility  
**Justification**: STT is transport layer; application layer defines structure

### UDP vs TCP Default

**Choice**: UDP primary, WebSocket secondary  
**Trade-off**: No built-in reliability BUT lower latency and no head-of-line blocking  
**Justification**: Streaming use cases prioritize freshness over completeness; applications can add selective retransmission

### Fixed Frame Header vs Variable

**Choice**: 20-byte fixed header  
**Trade-off**: 20 bytes overhead per frame BUT constant-time parsing  
**Justification**: Streaming traffic amortizes overhead; predictable performance critical

---

## Encapsulation Model

**Transport Agnosticism**:

STT chooses **full binary encapsulation** over network-native integration. This means:

- **Transport Agnostic**: STT packets are opaque encrypted blobs that tunnel through UDP, WebSocket, HTTPS, or any byte-transport mechanism
- **No NAT Traversal Needed**: Since STT rides on top of working transports (if UDP works, use it; if only HTTPS, tunnel through that)
- **Cryptographic Sessions**: Sessions bound to pre-shared seeds, not IP addresses (enables theoretical migration)
- **Configurable MTU**: Sensible defaults (1472 bytes UDP) with application control via `segment_size`, `max_packet_size`, etc.
- **Multi-Transport Capable**: Nodes can maintain UDP + multiple WebSocket connections simultaneously

**Application-Level Adaptation**:

- **Flow Control**: Credit-based backpressure in streaming layer
- **Bandwidth Adaptation**: Application tunes segment sizes based on network conditions
- **Acknowledgements**: Implemented via stream-level sequence tracking
- **Congestion**: Application-aware (STT provides tools, application decides policy)

---

## Related Documentation

- [API Reference](../api/API.md) - STT Python API
- [STC Dependency](../api/STC_DEPENDENCY_REFERENCE.md) - External crypto library
- [User Manual](../user_manual/00_INDEX.md) - Complete guide for developers
- [Examples](../examples/) - Code samples and patterns

---

**Document Version**: 0.2.0a0 (unreleased)  
**Last Updated**: November 25, 2025
