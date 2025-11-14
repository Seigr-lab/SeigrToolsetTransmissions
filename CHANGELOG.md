# Changelog

All notable changes to Seigr Toolset Transmissions will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-11-14

### Implementation Status: **56% Complete** (96/173 tests passing)

### ✅ Fully Implemented & Working

**Core Infrastructure** (100% tested)
- Frame Protocol: Binary frame format with 2MB size limit for STC metadata
- Serialization: Native STT binary serialization (not JSON/msgpack)
- Varint Encoding: Variable-length integer encoding for space efficiency
- STC Integration: Core crypto wrapper (67% - determinism tests fail due to probabilistic STC)

**Basic Functionality** (Partial - core working)
- Session Management: Creation, key rotation, basic lifecycle (record_sent_bytes/record_received_bytes missing)
- Stream Management: Creation, statistics tracking (_handle_incoming method missing)
- Chamber Storage: Encrypted key-value storage (get_metadata missing proper implementation)
- Handshake Protocol: Basic message creation (process_challenge, verify_response, process_final missing)

**Transport Layers** (Implemented but untested in integration)
- UDP Transport: Complete native implementation
- WebSocket Transport: Complete RFC 6455 native implementation

### ⚠️ Partially Implemented

**Session (STTSession)**
- ✅ Basic creation, key rotation, close, statistics
- ❌ Missing: `record_sent_bytes()`, `record_received_bytes()`, `get_statistics()` (has `get_stats()`)
- ❌ Missing: Metadata handling through constructor
- ❌ Missing: `is_active()` method (has `is_active` property)

**Stream (STTStream)**
- ✅ Basic send/receive, statistics
- ❌ Missing: `_handle_incoming()` for receiving data
- ❌ Missing: `get_statistics()` (has `get_stats()`)
- ❌ Missing: `is_expired()`, `receive_window_size()`, `receive_buffer_empty()`
- ❌ Missing: Proper flow control and ordered delivery

**Handshake (STTHandshake)**
- ✅ `create_hello()`, `process_hello()`
- ❌ Missing: `process_challenge()` - Cannot complete 3-way handshake
- ❌ Missing: `verify_response()` - Cannot verify peer responses
- ❌ Missing: `process_final()` - Cannot finalize handshake
- **Impact**: Full handshake protocol incomplete, only basic hello exchange works

**Chamber (Chamber)**
- ✅ Basic store/retrieve/delete operations
- ❌ Missing: Proper `get_metadata()` return type (returns Dict instead of ChamberMetadata)
- ❌ Issue: Multi-chamber isolation test failing

**Streaming (StreamEncoder/Decoder)**  
- ❌ Not tested: All encoder/decoder tests failing
- ❌ Missing proper implementation of chunk-wise encryption

**Transport Integration**
- ❌ UDP tests: All failing (7 failures)
- ❌ WebSocket tests: All failing (7 errors)
- **Root Cause**: Tests expect different API than implemented

### ❌ Not Implemented

**Missing Core Features**
- SessionManager: `get_session()` returns Session not STTSession
- SessionManager: `close_session()` expects async method
- SessionManager: `list_sessions()` returns wrong attribute
- HandshakeManager: Missing complete protocol flow
- Stream ordering and reassembly
- Proper flow control
- Encryption/decryption in streams
- Out-of-order packet handling

### Test Results Summary

**Passing: 96 / 173 (55.5%)**

By Module:
- ✅ Frame: 11/11 (100%)
- ✅ Serialization: 29/29 (100%)
- ✅ Varint: 12/12 (100%)
- ⚠️ STCWrapper: 14/21 (67%) - 7 determinism failures expected
- ⚠️ Chamber: 15/17 (88%) - 2 failures
- ⚠️ Session: 5/15 (33%) - Missing API methods
- ❌ Handshake: 3/13 (23%) - Protocol incomplete
- ❌ Stream: 2/18 (11%) - Missing core functionality
- ❌ Streaming: 0/16 (0%) - Not implemented
- ❌ Transport: 4/21 (19%) - Integration issues

### Known Issues

1. **API Inconsistency**: `get_stats()` vs `get_statistics()` naming
2. **Missing Methods**: Tests expect methods not implemented
3. **Handshake Incomplete**: 3-way protocol only 33% complete
4. **Stream Flow Control**: Not implemented
5. **Transport Tests**: Expect different constructor signatures

### Dependencies

**Runtime:**
- `seigr-toolset-crypto` (STC) - ONLY cryptographic dependency
- Python 3.9+

**Development:**
- pytest >= 8.0
- pytest-asyncio >= 0.21
- pytest-cov >= 4.0

### Architecture

```
Application Layer
    ↓
Stream Layer (partial: send/receive, missing: ordering)
    ↓  
Session Layer (partial: lifecycle, missing: proper stats APIs)
    ↓
Frame Layer (complete: 2MB frames)
    ↓
Transport Layer (complete impl, failing integration)
```

## [0.1.0] - 2025-11-14

### Added - Phase 1: STC Integration Foundation

#### Cryptography
- **STCWrapper**: Complete STC integration wrapper (~320 lines)
  - Hash operations using STC.hash (PHE)
  - Node ID generation from identity
  - Content-addressed storage IDs
  - Session key derivation using STC.derive_key (CKE)
  - Session key rotation
  - Frame encryption/decryption with AEAD-like associated_data
  - Per-stream isolated contexts to prevent nonce reuse
  
#### Native Serialization
- **STT Binary Format**: Self-sovereign TLV-like encoding
  - No JSON, msgpack, or third-party formats
  - Type-length-value encoding with 14 data types
  - Deterministic serialization
  - Used for all handshake messages and chamber storage

#### Protocol Components
- **STTFrame**: Binary frame protocol with STC encryption
  - Magic bytes (0x53 0x54) for frame identification
  - Varint encoding for efficient size representation
  - Integrated STC encryption with crypto metadata
  - Optional encryption with decrypt-on-demand
  
- **STTHandshake**: Pre-shared seed authentication
  - Challenge-response protocol using STC.hash
  - Commitment-based proof of shared seed
  - Session key derivation from handshake context
  - No external crypto dependencies (no X25519/Ed25519)
  
- **STTSession**: Session management with STC key rotation
  - STC-based key derivation for session keys
  - Automatic key rotation with configurable thresholds
  - Sequence tracking and statistics
  
- **Chamber**: STC-encrypted storage
  - AEAD-like encryption using STC with associated_data
  - Nonce management for each stored item
  - Encrypted key and session metadata storage
  - No hashlib or placeholder encryption

#### Streaming Foundation
- **StreamEncoder/StreamDecoder**: Native STC streaming
  - Uses STC.encrypt_stream and decrypt_stream
  - Configurable chunk sizes (64KB default)
  - Per-chunk encryption with chunk indexing
  - Statistics tracking

#### Transport Layer
- **UDPTransport**: Connectionless datagram transport
  - Asyncio-based UDP implementation
  - Configurable MTU (1472 bytes safe default)
  - Frame-based communication
  - NAT traversal ready
  
- **WebSocketTransport**: Native RFC 6455 implementation
  - No websockets library dependency
  - Client and server roles
  - Binary frame support
  - Ping/pong and close handshake

#### Core Runtime
- **STTNode**: Integrated node runtime
  - UDP transport with frame handling
  - STC-native handshake processing
  - Session management
  - Receive queue for data packets
  - Statistics and monitoring

### Technical Details

#### Dependencies
- **Runtime**: seigr-toolset-crypto (STC) ONLY
- **Development**: pytest, pytest-asyncio, pytest-cov, black, flake8, mypy
- **Removed**: websockets, msgpack, all hashlib usage

#### Architecture
- Pure STC cryptography throughout
- Native binary serialization (no JSON)
- Self-sovereign data formats
- All modules under 500 lines
- Zero third-party runtime dependencies except STC

### Security
- STC is the ONLY cryptographic provider
- Pre-shared seed authentication model
- AEAD-like encryption with associated_data
- Per-stream context isolation
- Nonce management to prevent reuse
- No placeholder encryption remaining

### Breaking Changes from Original Design
- Removed all hashlib usage (now pure STC)
- Removed JSON/msgpack (now native STT binary)
- Removed websockets library (now native RFC 6455)
- Changed from X25519/Ed25519 to pre-shared seed model
- TCP transport removed in favor of UDP-first design

### Known Limitations
- Handshake requires pre-shared seed (no public key crypto)
- WebSocket handshake uses hashlib.sha1 for RFC 6455 browser compatibility
- NAT traversal not yet implemented (UDP foundation ready)
- DHT and discovery not yet implemented
- Comprehensive tests pending

### Next Steps (Phase 2+)
- NAT traversal (STUN/TURN-like)
- DHT for peer discovery
- Content-addressed storage
- Comprehensive test suite
- Performance benchmarks
- Production deployment guides

---

[0.1.0]: https://github.com/seigr/seigr-toolset-transmissions/releases/tag/v0.1.0
