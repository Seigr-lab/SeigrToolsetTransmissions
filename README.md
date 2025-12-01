# Seigr Toolset Transmissions (STT)

[![Sponsor Seigr-lab](https://img.shields.io/badge/Sponsor-Seigr--lab-forestgreen?style=flat&logo=github)](https://github.com/sponsors/Seigr-lab)
[![License](https://img.shields.io/badge/license-ANTI--CAPITALIST-red)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-green)](https://python.org)
[![Version](https://img.shields.io/badge/version-0.2.0a0-blue)]()
[![Coverage](https://img.shields.io/badge/coverage-93.01%25-brightgreen)]()

> **Secure binary transport that doesn't care what you're sending.**

STT creates **opaque encrypted packets** that tunnel through any network (UDP, WebSocket, HTTPS) and can only be decrypted by authorized participants. No assumptions about your data - you could be streaming video, sending sensor readings, transferring files, or running your own custom protocol.

---

## 📖 Quick Links

- **New to STT?** → [What is STT?](docs/user_manual/01_what_is_stt.md) - Start here
- **Want to use it?** → [Getting Started](docs/user_manual/09_getting_started.md) - Installation & first program  
- **Need API docs?** → [API Reference](docs/api/API.md) - Complete Python API
- **Curious how it works?** → [Architecture](docs/design/ARCHITECTURE.md) - Design & protocol details

---

## Why STT?

**Problem**: Most protocols assume what you're sending (HTTP = web pages, MQTT = IoT messages, WebRTC = video calls). But what if you need secure binary transport without those assumptions?

**Solution**: STT provides **encrypted binary packets** that:

✅ **Tunnel through any transport** (UDP if available, WebSocket/HTTPS if firewalled)  
✅ **Only decrypt for authorized peers** (pre-shared seed authentication)  
✅ **Work for any application** (you define what the bytes mean)  
✅ **Are opaque to intermediaries** (network sees encrypted binary blobs)  

**Use STT for**: Video streaming, sensor networks, file transfer, messaging, custom protocols - anything that moves bytes securely.

---

## Status

**Version**: 0.2.0a0 (unreleased)  
**Test Coverage**: 93.01% (2803 statements)  
**Status**: Alpha - core functionality implemented and tested

**What works**: Handshake, sessions, streams, frames, UDP/WebSocket transport, encryption, storage  
**Known stubs/incomplete**:
- `ProbabilisticStream._try_send_segment()` - simulates network delivery (stub for integration)
- `RelayServer._handle_forward()` - counts forwarded frames but doesn't implement actual forwarding
- `core/transport.py UDPTransport` - placeholder class (working implementation is in `transport/udp.py`)

**What's next**: Complete stub implementations, production hardening, additional transports

---

## Quick Example

```python
import asyncio
from seigr_toolset_transmissions import STTNode

async def main():
    # Create node with pre-shared seeds
    node = STTNode(
        node_seed=b"my_node_secret_32bytes_minimum!",
        shared_seed=b"shared_secret_32bytes_minimum!",
        host="127.0.0.1",  # Default; use "0.0.0.0" to accept external connections
        port=8080
    )
    
    # Start listening
    await node.start(server_mode=True)
    
    # Receive packets from any authorized peer
    async for packet in node.receive():
        print(f"Received {len(packet.data)} bytes")
        # packet.data contains decrypted bytes
        # Only peers with matching shared_seed can send to us

asyncio.run(main())
```

**That's it.** Encrypted packets tunnel through your network automatically.

👉 **Learn more**: [Getting Started Guide](docs/user_manual/09_getting_started.md)

---

## How It Works

**1. Pre-Shared Seeds**: Both peers must have matching secrets (QR code, secure channel, etc.)  
**2. Handshake**: 4-message mutual authentication using STC encryption  
**3. Encrypted Packets**: All data encrypted before sending - opaque to network  
**4. Transport Agnostic**: Packets travel over UDP, WebSocket, or any byte transport  

```
┌─────────────┐                    ┌─────────────┐
│   Node A    │ ──[encrypted]────→ │   Node B    │
│ (shared_seed│    UDP/WebSocket   │ shared_seed)│
└─────────────┘ ←─[encrypted]───── └─────────────┘
                Only A & B can decrypt
                Network sees random bytes
```

👉 **Deep dive**: [Architecture](docs/design/ARCHITECTURE.md) | [Handshake Process](docs/user_manual/05_handshake_process.md) | [Security Model](docs/user_manual/13_security_model.md)

---

## Installation

**Requirements**: Python 3.9+

```bash
# From source (not yet on PyPI)
git clone https://github.com/Seigr-lab/SeigrToolsetTransmissions.git
cd SeigrToolsetTransmissions
pip install -e .
```

**Dependencies**:

- `seigr-toolset-crypto` >= 0.4.0 (STC encryption)

👉 **Full guide**: [Installation & Setup](docs/user_manual/09_getting_started.md)

---

## 📚 Documentation

### **User Manual** (Learn STT from scratch)

**Getting Started**:

- [Chapter 1: What is STT?](docs/user_manual/01_what_is_stt.md) - Overview and use cases
- [Chapter 2: Core Concepts](docs/user_manual/02_core_concepts.md) - Nodes, sessions, streams
- [Chapter 9: Getting Started](docs/user_manual/09_getting_started.md) - Installation and first program

**Understanding How It Works**:

- [Chapter 3: Binary Protocols](docs/user_manual/03_binary_protocols.md) - Why binary?
- [Chapter 4: Encryption](docs/user_manual/04_understanding_encryption.md) - STC and pre-shared seeds
- [Chapter 5: Handshake](docs/user_manual/05_handshake_process.md) - 4-message authentication
- [Chapter 6: Sessions](docs/user_manual/06_sessions_and_connections.md) - Session lifecycle
- [Chapter 7: Streams](docs/user_manual/07_streams_and_multiplexing.md) - Multiplexing explained
- [Chapter 8: Transport](docs/user_manual/08_transport_layer.md) - UDP vs WebSocket

**Using STT**:

- [Chapter 10: Common Patterns](docs/user_manual/10_common_usage_patterns.md) - Real-world examples
- [Chapter 11: Error Handling](docs/user_manual/11_error_handling.md) - Troubleshooting
- [Chapter 12: Performance](docs/user_manual/12_performance_and_optimization.md) - Optimization

**Security & Design**:

- [Chapter 13: Security Model](docs/user_manual/13_security_model.md) - Threat model
- [Chapter 14: Comparisons](docs/user_manual/14_comparisons.md) - STT vs HTTP/gRPC/WebRTC/QUIC
- [Chapter 15: Design Decisions](docs/user_manual/15_design_decisions.md) - Why STT works this way

**Reference**:

- [Glossary](docs/user_manual/appendix_a_glossary.md) - All terms defined
- [Frame Format](docs/user_manual/appendix_b_frame_format.md) - Binary format spec
- [Configuration](docs/user_manual/appendix_c_configuration.md) - All settings
- [Error Codes](docs/user_manual/appendix_d_error_codes.md) - Complete error reference

### **API & Technical Docs**

- **[API Reference](docs/api/API.md)** - Complete Python API for all components
- **[Architecture](docs/design/ARCHITECTURE.md)** - Design philosophy and protocol stack
- **[STC Dependency](docs/api/STC_DEPENDENCY_REFERENCE.md)** - External crypto library docs

### **Development**

- [Environment Setup](docs/development/ENVIRONMENT_SETUP.md) - Dev environment
- [CHANGELOG](docs/releases/CHANGELOG.md) - Version history

---

## Components

STT is built from these core components (all with dedicated documentation):

- **[STTNode](docs/user_manual/02_core_concepts.md#sttnode)** - Main runtime (85.56% tested)
- **[Handshake](docs/user_manual/05_handshake_process.md)** - Mutual authentication (87.93% tested)
- **[Sessions](docs/user_manual/06_sessions_and_connections.md)** - Connection management (100% tested)
- **[Streams](docs/user_manual/07_streams_and_multiplexing.md)** - Multiplexed channels (99.24% tested)
- **[Frames](docs/user_manual/appendix_b_frame_format.md)** - Binary protocol (98.26% tested)
- **[Transport](docs/user_manual/08_transport_layer.md)** - UDP/WebSocket (84-90% tested)
- **[Chamber](docs/api/API.md#storage)** - Encrypted storage (96.97% tested)
- **[STCWrapper](docs/api/STC_DEPENDENCY_REFERENCE.md)** - Cryptography (98.78% tested)

👉 **Full component docs**: [API Reference](docs/api/API.md)

---

## Testing

```bash
pytest tests/ -v --cov
```

**Coverage**: 93.01% (2803 statements)  
**Test suite**: 200+ tests covering all core components

---

## Security

STT has undergone comprehensive security auditing:

- ✅ **Bandit** static analysis: 0 issues (6679 lines of code scanned)
- ✅ **Safety** dependency check: 0 vulnerabilities
- ✅ **pip-audit** OSV database: 0 vulnerabilities in STT code

All identified security issues have been fixed, including:

- SHA1 usage properly marked as non-cryptographic (WebSocket handshake only)
- Default bind addresses set to localhost (127.0.0.1) for security
- Pickle replaced with JSON for storage serialization
- Secrets module used for cryptographic randomness
- Comprehensive error logging for debugging

👉 **Full security audit**: [Security Audit Summary](docs/security/SECURITY_AUDIT_SUMMARY.md)

---

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality  
4. Ensure all tests pass
5. Submit a pull request

**Development**: See [Environment Setup](docs/development/ENVIRONMENT_SETUP.md)

---

## License

**ANTI-CAPITALIST SOFTWARE LICENSE (v 1.4)**

See [LICENSE](LICENSE) for full details.

---

## Support & Community

- **Issues**: [GitHub Issues](https://github.com/Seigr-lab/SeigrToolsetTransmissions/issues)
- **Sponsor**: [GitHub Sponsors](https://github.com/sponsors/Seigr-lab)
