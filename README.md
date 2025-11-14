# Seigr Toolset Transmissions (STT)

[![Sponsor Seigr-lab](https://img.shields.io/badge/Sponsor-Seigr--lab-forestgreen?style=flat&logo=github)](https://github.com/sponsors/Seigr-lab)
[![License](https://img.shields.io/badge/license-ANTI--CAPITALIST-red)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-green)](https://python.org)

**Binary encrypted P2P streaming protocol using STC probabilistic cryptography.**

---

## What This Is

A P2P streaming protocol that uses Seigr Toolset Crypto (STC) for all cryptographic operations. Because STC is probabilistic (not deterministic like SHA-256), traditional handshake protocols don't work. This implements a handshake using STC encrypt/decrypt for mutual authentication.

**Status**: Work in progress (60% complete). Core protocol works, integration cleanup pending.

## Components

- **Handshake** - Mutual authentication using STC encrypt/decrypt
- **Session** - Connection lifecycle and key rotation  
- **Stream** - Multiplexed data channels with ordering
- **Frame** - Binary framing with STC encryption
- **Serialization** - Binary format (not JSON/msgpack)

---

## Architecture

Application → Stream → Session → Frame → Transport

**Handshake Flow:**

Initiator generates nonce, sends HELLO.  
Responder generates nonce, encrypts both nonces with STC, sends RESPONSE.  
Initiator decrypts to verify, creates session_id via XOR, encrypts session_id, sends AUTH_PROOF.  
Responder decrypts to verify, sends FINAL.  
Both have matching session_id.

---

## Test Results

105/173 tests passing (60.7%)

- Frame Protocol: 11/11 (100%)
- Serialization: 29/29 (100%)
- Varint Encoding: 12/12 (100%)
- Handshake: 7/13 (54%)
- Session: 8/15 (53%)
- Stream: 6/18 (33%)

Core protocol functional. Manager classes and transport integration need cleanup.

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
- [Protocol Spec](docs/protocol_spec.md)
- [API Reference](docs/api_reference.md)

---
