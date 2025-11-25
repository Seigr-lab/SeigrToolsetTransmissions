# STT User Manual - Complete Guide

**Version**: 0.2.0a0 (unreleased)  
**Last Updated**: November 25, 2025

## About This Manual

This manual explains Seigr Toolset Transmissions (STT) in plain language. Each chapter builds on the previous one, starting from basic concepts and progressing to advanced topics.

## Quick Start

**New to STT?** → Start with [Chapter 1: What is STT?](01_what_is_stt.md)  
**Want to code?** → Jump to [Chapter 9: Getting Started](09_getting_started.md)  
**Need component details?** → See [Part V: Component Reference](#part-v-component-reference) (Chapters 16-25)

## Manual Structure

### Part I: Foundations

- [Chapter 1: What is STT?](01_what_is_stt.md)
  - **NEW**: Agnostic design philosophy
  - **NEW**: Eight core primitives explained
  - What problem does STT solve?
  - Who uses STT and why?
  - Real-world examples (video, sensors, storage, messaging)

- [Chapter 2: Core Concepts Explained](02_core_concepts.md)
  - **NEW**: Agnostic primitives (BinaryStreamEncoder/Decoder, BinaryStorage, EndpointManager, EventEmitter, FrameDispatcher)
  - **NEW**: Composition patterns (live streaming, hash-addressed storage, multi-endpoint routing, custom protocols)
  - Nodes, peers, and networks
  - Sessions and connections
  - Streams and multiplexing
  - Encryption and keys

- [Chapter 3: Binary Protocols and Data](03_binary_protocols.md)
  - What is binary data?
  - Why use binary instead of text?
  - How computers understand binary protocols
  - STT's binary format explained

- [Chapter 4: Understanding Encryption](04_understanding_encryption.md)
  - What is encryption? (explained simply)
  - Symmetric vs asymmetric encryption
  - What is STC and how is it different?
  - Pre-shared seeds explained

### Part II: How STT Works

- [Chapter 5: The Handshake Process](05_handshake_process.md)
  - What is a handshake?
  - STT's 4-message handshake step-by-step
  - Why four messages?
  - What happens if handshake fails?

- [Chapter 6: Sessions and Connections](06_sessions_connections.md)
  - What is a session?
  - Session lifecycle (creation, use, closing)
  - Session keys and rotation
  - Multiple sessions

- [Chapter 7: Streams and Multiplexing](07_streams_multiplexing.md)
  - What is a stream?
  - Why multiplex streams?
  - Stream ordering and reliability
  - Flow control explained

- [Chapter 8: Transport Layer](08_transport_layer.md)
  - UDP vs WebSocket: What's the difference?
  - When to use which transport
  - Network addressing and ports
  - Firewalls and NAT

### Part III: Using STT

- [Chapter 9: Getting Started](09_getting_started.md)
  - Installation
  - System requirements
  - First program: Running a node
  - Configuration basics

- [Chapter 10: Common Usage Patterns](10_usage_patterns.md)
  - Two-peer communication
  - File transfer
  - Streaming data
  - Multi-stream applications

- [Chapter 11: Error Handling](11_error_handling.md)
  - Common errors and solutions
  - Network troubleshooting
  - Debugging techniques
  - Logging and diagnostics

- [Chapter 12: Performance and Optimization](12_performance.md)
  - Bandwidth considerations
  - Latency optimization
  - Memory usage
  - Tuning parameters

### Part IV: Security and Context

- [Chapter 13: Security Model](13_security_model.md)
  - Threat model: What STT protects against
  - What STT does NOT protect against
  - Pre-shared seed distribution
  - Key rotation and forward secrecy

- [Chapter 14: Comparison with Other Protocols](14_comparisons.md)
  - STT vs HTTP/HTTPS
  - STT vs gRPC
  - STT vs WebRTC
  - STT vs QUIC
  - When to use STT vs alternatives

- [Chapter 15: Design Decisions and Trade-offs](15_design_decisions.md)
  - Why pre-shared seeds?
  - Why binary serialization?
  - Why STC instead of standard crypto?
  - Limitations and when NOT to use STT

### Part V: Component Reference

**Each component has its own dedicated chapter with detailed examples, patterns, and troubleshooting:**

- **[Chapter 16: STTNode](16_sttnode.md)** - Main runtime and coordination
- **[Chapter 17: Sessions & SessionManager](17_sessions.md)** - Connection lifecycle and management
- **[Chapter 18: Handshake & HandshakeManager](18_handshake.md)** - Authentication protocol
- **[Chapter 19: Frames & FrameDispatcher](19_frames.md)** - Binary protocol and routing
- **[Chapter 20: Streams & StreamManager](20_streams.md)** - Multiplexing and flow control
- **[Chapter 21: Chamber Storage](21_chamber.md)** - Encrypted persistent storage
- **[Chapter 22: Transport Layer](22_transport.md)** - UDP and WebSocket transports
- **[Chapter 23: Cryptography (STCWrapper)](23_cryptography.md)** - STC encryption integration
- **[Chapter 24: Binary Streaming](24_binary_streaming.md)** - Large data fragmentation
- **[Chapter 25: Endpoints & Events](25_endpoints_events.md)** - Endpoint management and event system

### Part VI: Reference

- [Design: Agnostic Design Philosophy](../design/agnostic_design_philosophy.md)
  - **NEW**: Complete agnostic design documentation
  - Zero assumptions principle
  - Eight primitives in depth
  - Design patterns (live streaming, storage, routing, custom protocols)
  - Anti-patterns (what NOT to do)
  - Terminology guide (agnostic language)


- [Appendix A: Glossary](appendix_a_glossary.md)
  - All technical terms defined

- [Appendix B: Frame Format Reference](appendix_b_frame_format.md)
  - Detailed binary format specification

- [Appendix C: Configuration Reference](appendix_c_configuration.md)
  - All configuration options

- [Appendix D: Error Code Reference](appendix_d_error_codes.md)
  - Complete error code listing

---

## Getting Help

- **[Part V: Component Reference](#part-v-component-reference)** - Chapters 16-25 with detailed component guides
- **[Glossary](appendix_a_glossary.md)** - Term definitions
- **[API Reference](../api/API.md)** - Complete Python API
- **[Architecture](../design/ARCHITECTURE.md)** - Design documentation

---

**Document Version**: 0.2.0a0 (unreleased)  
**Last Updated**: November 25, 2025
