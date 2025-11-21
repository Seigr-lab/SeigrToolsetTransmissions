# STT User Manual - Complete Guide

**Version**: 0.2.0-alpha  
**Last Updated**: November 21, 2025

## About This Manual

This manual explains Seigr Toolset Transmissions (STT) in plain language. It is designed for anyone to understand - you don't need to be a developer or cryptography expert. Each chapter builds on the previous one, starting from basic concepts and progressing to advanced topics.

## What is STT?

STT (Seigr Toolset Transmissions) is a protocol - a set of rules that computers follow to communicate with each other over a network. Think of it like the rules for having a conversation: you take turns speaking, you confirm you understood each other, and you have a way to end the conversation gracefully.

STT is specifically designed for:

- **Peer-to-peer communication**: Two computers talk directly to each other without a central server
- **Binary data streaming**: Sending any type of data (files, video, audio, messages) efficiently
- **Strong encryption**: All data is encrypted using STC (Seigr Toolset Crypto)
- **Multiple streams**: Send different types of data simultaneously over one connection

## Who Should Read This

- **Non-technical users** who want to understand what STT is and how it works
- **Developers** who want to integrate STT into their applications
- **System administrators** who need to deploy STT-based systems
- **Security auditors** who need to understand STT's security model
- **Anyone curious** about peer-to-peer networking and cryptography

## How to Use This Manual

Read the chapters in order if you're new to STT:

1. Start with **Chapter 1** to understand the basics
2. Read **Chapters 2-4** to learn core concepts
3. **Chapters 5-7** explain how things work technically
4. **Chapters 8-10** cover practical usage
5. **Chapters 11-13** discuss security and comparisons
6. **Appendices** provide reference information

If you're looking for specific information, use the chapter links below.

## Manual Structure

### Part I: Foundations

- [Chapter 1: What is STT?](01_what_is_stt.md)
  - What problem does STT solve?
  - Who uses STT and why?
  - Real-world analogies

- [Chapter 2: Core Concepts Explained](02_core_concepts.md)
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

### Part V: Reference

- [Appendix A: Glossary](appendix_a_glossary.md)
  - All technical terms defined

- [Appendix B: Frame Format Reference](appendix_b_frame_format.md)
  - Detailed binary format specification

- [Appendix C: Configuration Reference](appendix_c_configuration.md)
  - All configuration options

- [Appendix D: Error Code Reference](appendix_d_error_codes.md)
  - Complete error code listing

- [Appendix E: Migration Guide](appendix_e_migration.md)
  - Migrating from other protocols

## Getting Help

If you have questions after reading this manual:

1. Check the [Glossary](appendix_a_glossary.md) for term definitions
2. Review the [FAQ](appendix_f_faq.md) for common questions
3. See the [API Reference](../api_reference.md) for code-level details
4. Check the [Examples](../examples.md) for code samples

## Contributing to This Manual

Found an error? Something unclear? This manual can be improved:

- Corrections and clarifications welcome
- Suggest additional examples
- Request new chapters or topics
- Fix typos and formatting

The manual source is in the `docs/user_manual/` directory.

## Document Conventions

Throughout this manual:

- **Bold text**: Important terms or emphasis
- `Code formatting`: Code, filenames, commands
- > Block quotes: Important notes or warnings
- 📝 Note icons: Additional information
- ⚠️ Warning icons: Important cautions
- ✅ Success icons: Confirmation or completion

Let's begin! Continue to [Chapter 1: What is STT?](01_what_is_stt.md)
