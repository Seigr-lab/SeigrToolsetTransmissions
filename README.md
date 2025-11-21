# Seigr Toolset Transmissions (STT)

[![Sponsor Seigr-lab](https://img.shields.io/badge/Sponsor-Seigr--lab-forestgreen?style=flat&logo=github)](https://github.com/sponsors/Seigr-lab)
[![License](https://img.shields.io/badge/license-ANTI--CAPITALIST-red)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-green)](https://python.org)

**Binary P2P streaming protocol using STC (Seigr Toolset Crypto) for cryptographic operations.**

---

## What This Is

STT is a peer-to-peer streaming protocol that uses Seigr Toolset Crypto (STC) for all cryptographic operations. STC uses probabilistic cryptography rather than deterministic functions like SHA-256. The protocol implements a 4-message handshake (HELLO, RESPONSE, AUTH_PROOF, FINAL) using STC's encrypt/decrypt operations for mutual authentication between peers who share a pre-distributed seed.

**Status**: Pre-release v0.2.0-alpha - **90.03% test coverage** - Core protocol tested and functional

## Components

- **Handshake** - Complete mutual authentication using STC encrypt/decrypt (87.93% coverage)
- **Session** - Full lifecycle and key rotation (100% coverage)
- **Stream** - Multiplexed data channels with ordering (99.24% coverage)
- **Frame** - Binary framing with STC encryption (80% coverage)
- **Serialization** - Binary format (not JSON/msgpack) (88.44% coverage)
- **Transport** - UDP & WebSocket native implementations (84%+ coverage)

---

## Architecture

Application → Stream → Session → Frame → Transport

**Handshake Flow (4 messages):**

1. **HELLO**: Initiator generates nonce, creates commitment hash, sends to responder
2. **RESPONSE**: Responder generates nonce, encrypts challenge (both nonces) with STC, sends to initiator
3. **AUTH_PROOF**: Initiator decrypts challenge, creates session_id from XOR of (nonce_i, nonce_r, node_id_i, node_id_r), encrypts proof, sends to responder
4. **FINAL**: Responder verifies proof by decrypting and comparing session_id, sends confirmation

Both peers now have the same session_id and can establish streams. This protocol requires pre-shared seeds - the ability to decrypt the STC-encrypted challenge proves seed possession.

---

## Test Coverage

**Overall: 90.03% (210 missing lines from 2107 total statements)**

**Module Coverage:**

- session.py: **100%** (96 statements, 0 missing)
- serialization.py: **100%** (147 statements, 0 missing)
- session_manager.py: **100%** (78 statements, 0 missing)
- stream.py: **99.24%** (131 statements, 1 missing)
- stream_manager.py: **98.61%** (72 statements, 1 missing)
- stc_wrapper.py: **98.78%** (82 statements, 1 missing)
- frame.py: **98.26%** (115 statements, 2 missing)
- decoder.py: **97.87%** (47 statements, 1 missing)
- chamber.py: **96.97%** (66 statements, 2 missing)
- udp.py: **89.86%** (138 statements, 14 missing)
- handshake.py: **87.36%** (174 statements, 22 missing)
- websocket.py: **84.17%** (436 statements, 69 missing)
- node.py: **82.95%** (129 statements, 22 missing)

Core protocol components (session, stream, frame, serialization) have high coverage. Lower coverage in node.py and websocket.py is primarily in error handling paths and less common code branches.

---

## Installation

Not yet published to PyPI.

From source:

```bash
git clone https://github.com/Seigr-lab/SeigrToolsetTransmissions.git
cd SeigrToolsetTransmissions
pip install -e .
```

### Requirements

- Python 3.9+
- seigr-toolset-crypto>=0.3.1

---

## Quick Start

### Basic Node

```python
import asyncio
from seigr_toolset_transmissions import STTNode

async def main():
    seed = b"shared_seed_32_bytes_minimum!!"
    
    node = STTNode(node_seed=seed, shared_seed=seed)
    await node.start()
    
    print(f"Node ID: {node.node_id.hex()}")

asyncio.run(main())
```

### Handshake Example

```python
from seigr_toolset_transmissions.handshake import STTHandshake
from seigr_toolset_transmissions.crypto import STCWrapper

seed = b"shared_seed_32_bytes_minimum!!"

# Initiator
initiator = STTHandshake(
    node_id=b"\x01" * 32,
    stc_wrapper=STCWrapper(seed),
    is_initiator=True
)

# Responder
responder = STTHandshake(
    node_id=b"\x02" * 32,
    stc_wrapper=STCWrapper(seed),
    is_initiator=False
)

# Protocol
hello = initiator.create_hello()
challenge = responder.process_hello(hello)
response = initiator.process_challenge(challenge)
final = responder.verify_response(response)
initiator.process_final(final)

print(f"Session: {initiator.session_id.hex()}")
```

### Frame Encryption

```python
from seigr_toolset_transmissions.frame import STTFrame
from seigr_toolset_transmissions.crypto import STCWrapper

stc = STCWrapper(b"seed" * 8)

frame = STTFrame.create_frame(
    frame_type=1,
    session_id=b"\x01" * 8,
    sequence=0,
    stream_id=1,
    payload=b"Hello!"
)

encrypted = frame.encrypt(stc)
serialized = frame.to_bytes()

# Decrypt
received = STTFrame.from_bytes(serialized, stc)
print(received.payload)  # b"Hello!"
```

---

## Usage

### Session Management

```python
from seigr_toolset_transmissions.session import STTSession
from seigr_toolset_transmissions.crypto import STCWrapper

stc = STCWrapper(b"seed" * 8)
session = STTSession(
    session_id=b"\x01" * 8,
    peer_node_id=b"\x02" * 32,
    stc_wrapper=stc
)

session.record_sent_bytes(1024)
session.record_received_bytes(2048)

stats = session.get_statistics()
print(stats)
```

### Stream Usage

```python
from seigr_toolset_transmissions.stream import STTStream
from seigr_toolset_transmissions.crypto import STCWrapper

stc = STCWrapper(b"seed" * 8)
stream = STTStream(
    session_id=b"\x01" * 8,
    stream_id=1,
    stc_wrapper=stc
)

await stream.send(b"Data")
data = await stream.receive()
```

---

## Documentation

**User Manual**: [`docs/user_manual/`](docs/user_manual/) - Complete guide (15 chapters)

**Core References**:

- [API Reference](docs/api/api_reference.md) - Complete API documentation
- [Protocol Specification](docs/design/protocol_spec.md) - Protocol details
- [STC API Reference](docs/api/STC_API_REFERENCE.md) - seigr-toolset-crypto API
- [Environment Setup](docs/development/ENVIRONMENT_SETUP.md) - Development environment

**Development**:

- [Documentation Updates](docs/development/DOCUMENTATION_UPDATE.md) - Tracking doc changes

**Releases**:

- [CHANGELOG](docs/releases/CHANGELOG.md) - Complete changelog
- [v0.2.0-alpha](docs/releases/v0.2.0-alpha.md) - Current release
- [v0.1.0](docs/releases/v0.1.0.md) - Initial release

---

## Features

- Handshake using STC encrypt/decrypt proof
- XOR-based session IDs (pure math)  
- Session lifecycle with statistics  
- Stream multiplexing with ordering  
- Frame encryption (STC AEAD-like)  
- Binary serialization  
- Varint encoding

### Not Yet Implemented

- Manager async integration (blocks many tests)
- Transport layer integration
- Streaming encoder/decoder
- NAT traversal
- DHT discovery

---

## Testing

```bash
# All tests
pytest tests/ -v

# Specific modules
pytest tests/test_handshake.py -v
pytest tests/test_session.py -v

# With coverage
pytest tests/ --cov
```

---

## Contributing

1. Fork repository
2. Create feature branch
3. Add tests
4. Keep modules focused
5. Use ONLY STC crypto
6. Submit PR

---

## License

ANTI-CAPITALIST SOFTWARE LICENSE (v 1.4)

---

## Links

- [Seigr Toolset Crypto](https://pypi.org/project/seigr-toolset-crypto/)
- [Protocol Spec](docs/design/protocol_spec.md)
- [API Reference](docs/api/api_reference.md)

---
