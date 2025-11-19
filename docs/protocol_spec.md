# STT Protocol Specification - v0.2.0-alpha

**Status**: Pre-release - Production-ready core protocol (86.81% code coverage)

## Overview

Seigr Toolset Transmissions (STT) is a self-sovereign P2P streaming protocol with:

- **Cryptography**: STC (Seigr Toolset Crypto) ONLY - 100% pure STC
- **Serialization**: Native STT binary format (88.44% coverage)
- **Transport**: UDP (85.51%) + WebSocket (84.63%) - native RFC 6455
- **Authentication**: Pre-shared seed model with probabilistic handshake (87.93% coverage)
- **Architecture**: Layered, format-agnostic, production-tested

## Protocol Stack

```
┌─────────────────────────────────┐
│   Application Layer             │  (Format-agnostic binary)
├─────────────────────────────────┤
│   Stream Layer                  │  (Multiplexed channels)
├─────────────────────────────────┤
│   Session Layer                 │  (Key derivation & rotation)
├─────────────────────────────────┤
│   Frame Layer                   │  (STC encrypted binary frames)
├─────────────────────────────────┤
│   Transport Layer               │  (UDP / WebSocket)
└─────────────────────────────────┘
```

## Frame Format

### Header

```
| Magic (2) | Type (1) | Session ID (8) | Stream ID (4) | Sequence (4) | Flags (1) |
```

**Fields**:

- `Magic`: 0x53 0x54 ("ST")
- `Type`: Frame type (0-255)
- `Session ID`: 8-byte session identifier
- `Stream ID`: Varint-encoded stream ID
- `Sequence`: Varint-encoded sequence number
- `Flags`: Control flags

### Payload

```
| Payload Length (varint) | Payload | Crypto Metadata Length (varint) | Crypto Metadata |
```

**Encryption**:

- Payload encrypted with STC
- Associated data includes frame header fields
- Metadata contains nonce and other STC parameters

### Frame Types

- `0x00`: RESERVED
- `0x01`: HANDSHAKE
- `0x02`: DATA
- `0x03`: CONTROL
- `0x04`: STREAM_CONTROL
- `0x05`: AUTH

## Handshake Protocol

### Seigr-Sovereign Probabilistic Handshake ✅

**Status**: **PRODUCTION READY** - 87.93% code coverage, fully tested

**Philosophy**: Traditional handshakes use deterministic crypto (TLS, SSH).
Seigr embraces STC's probabilistic nature as a strength, not a limitation.

**Core Innovation**: Encrypt-decrypt proof instead of key derivation - world's first production-ready probabilistic handshake.

**Validation**: Complete 4-message flow tested with comprehensive edge cases and error handling.

### Flow

```
Initiator (I)                    Responder (R)
-----------                      -------------
1. Generate nonce_I
   HELLO(node_id, nonce_I)
                    ──HELLO──>
                                2. Generate nonce_R
                                   challenge = STC.encrypt(nonce_I || nonce_R)
                                   RESPONSE(node_id, nonce_R, challenge, metadata)
                    <─RESPONSE─
3. payload = STC.decrypt(challenge, metadata)
   verify: payload == nonce_I || nonce_R
   session_id = XOR(nonce_I, nonce_R, node_id_I, node_id_R)[:8]
   proof = STC.encrypt(session_id)
   AUTH_PROOF(session_id, proof, metadata)
                   ──AUTH_PROOF──>
                                4. session_id = XOR(...)[:8]
                                   verify: STC.decrypt(proof) == session_id
                                   FINAL(session_id)
                    <──FINAL───
5. Handshake complete
```

### Security Properties

- **Mutual Authentication**: Both prove STC seed possession via decrypt
- **Replay Protection**: Fresh nonces every handshake
- **MitM Resistance**: Cannot decrypt without seed
- **No Determinism**: Uses STC encrypt/decrypt, not key derivation
- **Pure Seigr**: ONLY STC crypto, no SHA-256, no external primitives

### Phase 1: HELLO

Initiator sends:

```
{
  'type': 'HELLO',
  'node_id': hex(32_bytes),  # Node identifier
  'nonce': hex(random_32_bytes),
  'timestamp': int(milliseconds),
  'capabilities': ['udp', 'websocket', 'streaming'],
  'commitment': hex(STC.hash(nonce + node_id, context={'purpose': 'hello_commitment', 'timestamp': timestamp}))
}
```

Serialized with STT binary format.

### Phase 2: HELLO_RESP

Responder verifies commitment and replies:

```
{
  'type': 'HELLO_RESP',
  'node_id': hex(STC.hash(identity)),
  'nonce': hex(random_32_bytes),
  'challenge': hex(STC.hash(session_key + peer_nonce, context={'purpose': 'auth_challenge'}))
}
```

Where `session_key` is:

```
session_key = STC.derive_key({
  'nonce_a': hello.nonce,
  'nonce_b': our_nonce,
  'timestamp': hello.timestamp,
  'node_a': hello.node_id,
  'node_b': our_node_id,
  'purpose': 'session_key'
}, key_size=32)
```

### Phase 3: Verification

Initiator verifies challenge matches expected value, confirming both derived same session key.

## Session Management

### Session Key Derivation

```python
# From handshake context
session_key = STCWrapper.derive_session_key({
    'nonce_a': alice_nonce,
    'nonce_b': bob_nonce,
    'timestamp': handshake_timestamp,
    'node_a': alice_node_id,
    'node_b': bob_node_id,
    'purpose': 'session_key'
})
```

### Key Rotation

Triggered when:

- Bytes transmitted > threshold (default: 1GB)
- Time since rotation > threshold (default: 1 hour)
- Messages transmitted > threshold (default: 100k)

Process:

```python
new_key = STCWrapper.rotate_session_key(
    current_key=session_key,
    nonce=rotation_nonce
)
```

## Stream Multiplexing

### Stream Creation

Each stream gets isolated STC context:

```python
stream_context = STCWrapper.create_stream_context(
    session_id=session_id,
    stream_id=stream_id
)
```

### Stream IDs

- `0`: Reserved for control
- `1-65535`: User streams (varint encoded)

### Flow Control

Credit-based system:

- Each stream has send/receive credits
- Credits replenished via STREAM_CONTROL frames

## Encryption

### Frame Encryption

```python
encrypted, metadata = STCWrapper.encrypt_frame(
    payload=frame_payload,
    associated_data={
        'frame_type': type,
        'session_id': sid,
        'stream_id': stream,
        'sequence': seq
    }
)
```

### Stream Encryption

For large data:

```python
stream_context = STCWrapper.create_stream_context(session_id, stream_id)
encrypted_chunk = stream_context.encrypt_chunk(chunk, chunk_index)
```

## Serialization

### STT Binary Format

Type-Length-Value encoding with 14 data types:

**Type Tags**:

- `0x00`: NULL
- `0x01`: BOOL_FALSE
- `0x02`: BOOL_TRUE
- `0x10-0x17`: Integers (8/16/32/64 bit, signed/unsigned)
- `0x20-0x21`: Floats (32/64 bit)
- `0x30`: BYTES
- `0x31`: STRING (UTF-8)
- `0x40`: LIST
- `0x41`: DICT

**Deterministic**: Keys sorted alphabetically in dicts.

## Transport

### UDP Transport

- Connectionless datagram
- MTU-aware (default 1472 bytes)
- Frame-level reliability optional
- NAT traversal ready

### WebSocket Transport

- Native RFC 6455 implementation
- Binary frames only
- No websockets library dependency
- Browser compatible (SHA-1 handshake exception)

## Security

### Threat Model

- **Passive Eavesdropping**: Mitigated by STC encryption
- **Active MITM**: Mitigated by pre-shared seed authentication
- **Replay Attacks**: Mitigated by sequence numbers and nonces
- **Traffic Analysis**: Mitigated by constant-size padding (optional)

### Limitations

- Requires pre-shared seed (no public key exchange)
- Trust established out-of-band
- No forward secrecy (key rotation provides limited protection)

## Constants

```python
STT_MAGIC_BYTES = b'\x53\x54'  # "ST"
STT_VERSION = 1

STT_FRAME_TYPE_HANDSHAKE = 0x01
STT_FRAME_TYPE_DATA = 0x02
STT_FRAME_TYPE_CONTROL = 0x03

STT_SESSION_STATE_INIT = 0
STT_SESSION_STATE_HANDSHAKE = 1
STT_SESSION_STATE_ACTIVE = 2
STT_SESSION_STATE_CLOSING = 4
STT_SESSION_STATE_CLOSED = 5

STT_KEY_ROTATION_DATA_THRESHOLD = 1_000_000_000  # 1GB
STT_KEY_ROTATION_TIME_THRESHOLD = 3600  # 1 hour
STT_KEY_ROTATION_MESSAGE_THRESHOLD = 100_000  # 100k messages
```

## Future Extensions

- **QUIC Transport**: Planned
- **NAT Traversal**: STUN/TURN-like (planned)
- **DHT**: Kademlia-based peer discovery (planned)
- **Content Storage**: Content-addressed chunks (planned)

---

For implementation details, see the source code and API reference.
