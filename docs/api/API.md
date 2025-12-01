# STT API Reference

**Version**: 0.2.0a0 (unreleased)  
**Test Coverage**: 93.01% (2803 statements)  
**Status**: Pre-release Alpha - Core functionality implemented and tested

> **Note**: This document covers STT (Seigr Toolset Transmissions) APIs only.  
> For STC cryptography APIs, see [STC_DEPENDENCY_REFERENCE.md](STC_DEPENDENCY_REFERENCE.md).

---

## Table of Contents

1. [Installation](#installation)
2. [Core Runtime](#core-runtime)
3. [Session Management](#session-management)
4. [Stream Management](#stream-management)
5. [Binary Streaming](#binary-streaming)
6. [Frame Protocol](#frame-protocol)
7. [Handshake](#handshake)
8. [Storage](#storage)
9. [Endpoints](#endpoints)
10. [Events](#events)
11. [Transport](#transport)
12. [Utilities](#utilities)
13. [Exceptions](#exceptions)

---

## Installation

```bash
pip install seigr-toolset-transmissions  # When released
```

**Dependencies**:

- Python >= 3.9
- `seigr-toolset-crypto >= 0.4.0` (STC cryptography)

**Optional**:

- `websockets >= 11.0.0` (for WebSocket transport)

---

## Core Runtime

### STTNode

Full node runtime with handshake, sessions, streams, and transport management.

**Coverage**: 85.56%

```python
from seigr_toolset_transmissions import STTNode, StorageProvider

node = STTNode(
    node_seed: bytes,        # 32+ bytes, node-specific secret
    shared_seed: bytes,      # 32+ bytes, pre-shared with peers
    host: str = '0.0.0.0',  # Listen address
    port: int = 0,          # Listen port (0 = random)
    storage: Optional[StorageProvider] = None  # Pluggable storage (optional)
)

# Start node
await node.start()

# Connect to peer via UDP
await node.connect_udp(peer_host, peer_port)

# Receive packets
async for packet in node.receive():
    # packet.data: bytes
    # packet.session_id: bytes
    # packet.stream_id: int
    process(packet.data)

# Send to all sessions
await node.send_to_all(frame_bytes)

# Send to specific sessions
await node.send_to_sessions([session_id1, session_id2], frame_bytes)

# Statistics
stats = node.get_stats()
# {'sessions': int, 'transport': dict, ...}

# Enable/disable incoming connections
node.enable_accept_connections()
node.disable_accept_connections()

# Stop node
await node.stop()
```

**Key Features**:

- Automatic handshake on connect
- Multi-session management
- UDP and WebSocket transports
- Binary storage (Chamber) integration
- Event-driven architecture

---

## Session Management

### STTSession

Single session with a peer. Handles encryption, key derivation, metadata.

**Coverage**: 100%

```python
from seigr_toolset_transmissions import STTSession

session = STTSession(
    session_id: bytes,      # 8-byte session identifier
    peer_node_id: bytes,    # 32-byte peer identifier
    stc_wrapper: STCWrapper # Crypto wrapper
)

# Session state
session.session_id  # bytes (8)
session.peer_node_id  # bytes (32)
session.is_active  # bool
session.transport_type  # 'udp' or 'websocket'
session.metadata  # dict (custom key-value data)

# Update activity
session.update_activity()

# Mark session active/inactive
session.mark_active(peer_address=('ip', port))
await session.mark_inactive()

# Statistics
stats = session.get_stats()
# {'active': bool, 'created_at': float, 'last_activity': float, ...}
```

### SessionManager

Manages multiple sessions.

**Coverage**: 100%

```python
from seigr_toolset_transmissions import SessionManager

manager = SessionManager(stc_wrapper)

# Create session
session_id, session = manager.create_session(peer_node_id)

# Get session
session = manager.get_session(session_id)

# Get all active sessions
sessions = manager.get_active_sessions()

# Remove session
manager.remove_session(session_id)

# Cleanup inactive sessions
count = await manager.cleanup_inactive_sessions(timeout=300)

# Statistics
stats = manager.get_stats()
# {'total': int, 'active': int, ...}
```

---

## Stream Management

### STTStream

Single multiplexed stream within a session.

**Coverage**: 99.24%

```python
from seigr_toolset_transmissions import STTStream

stream = STTStream(
    stream_id: int,
    session_id: bytes,
    stc_wrapper: STCWrapper
)

# Stream state
stream.stream_id  # int
stream.session_id  # bytes
stream.is_active  # bool
stream.sequence  # int (next sequence number)

# Send data (returns encrypted segment)
segment = await stream.send(data: bytes)
# segment = {'data': bytes, 'sequence': int}

# Receive data (returns decrypted bytes)
data = await stream.receive(encrypted_bytes)

# Close stream
await stream.close()

# Statistics
stats = stream.get_stats()
# {'bytes_sent': int, 'bytes_received': int, 'sequence': int, ...}
```

### StreamManager

Manages streams within a session.

**Coverage**: 98.61%

```python
from seigr_toolset_transmissions import StreamManager

manager = StreamManager(
    session_id: bytes,
    stc_wrapper: STCWrapper
)

# Create stream
stream = await manager.create_stream(stream_id: Optional[int] = None)

# Get stream
stream = manager.get_stream(stream_id)

# List active streams
streams = manager.list_streams()

# Close stream
await manager.close_stream(stream_id)

# Close all streams
await manager.close_all_streams()

# Statistics
stats = manager.get_stats()
# {'total_streams': int, 'active_streams': int, ...}
```

---

## Binary Streaming

Agnostic binary streaming with automatic segmentation and encryption.

### StreamEncoder (BinaryStreamEncoder)

Async generator yielding encrypted segments for transmission.

**Coverage**: 100%

```python
from seigr_toolset_transmissions import StreamEncoder

encoder = StreamEncoder(
    stc_wrapper: STCWrapper,
    session_id: bytes,
    stream_id: int,
    segment_size: int = 65536,  # 64KB default
    mode: str = 'live'  # 'live' or 'bounded'
)

# Send data (yields encrypted segments)
async for segment in encoder.send(data: bytes):
    # segment = {'data': bytes, 'sequence': int}
    await transport.transmit(segment['data'])

# End bounded stream (live streams cannot call this)
end_marker = await encoder.end()
# Returns: {'data': bytes, 'sequence': int, 'is_end': True}

# Flow control
encoder.add_credits(credits: int)

# Statistics
stats = encoder.get_stats()
# {'sequence': int, 'bytes_sent': int, 'mode': str, 'credits': int}

# Reset encoder
encoder.reset()
```

**Modes**:

- `'live'`: Infinite streaming (no end marker)
- `'bounded'`: Known-size streaming (must call `end()`)

### StreamDecoder (BinaryStreamDecoder)

Reconstructs original bytes from encrypted segments.

**Coverage**: 96%+

```python
from seigr_toolset_transmissions import StreamDecoder

decoder = StreamDecoder(
    stc_wrapper: STCWrapper,
    session_id: bytes,
    stream_id: int
)

# Process incoming segment
await decoder.process_segment(
    sequence: int,
    encrypted_data: bytes
)

# Receive decrypted data (async iterator)
async for decrypted_chunk in decoder.receive():
    # decrypted_chunk = bytes (in order)
    process(decrypted_chunk)

# Signal end of bounded stream
decoder.signal_end()

# Statistics
stats = decoder.get_stats()
# {'next_expected': int, 'bytes_received': int, 'buffered_segments': int}

# Reset decoder
decoder.reset()
```

---

## Frame Protocol

### STTFrame

Binary frame with encryption and metadata.

**Coverage**: 90%

```python
from seigr_toolset_transmissions import STTFrame

# Create frame
frame = STTFrame(
    frame_type: int,        # 0x01-0xFF
    session_id: bytes,      # 8 bytes
    sequence: int,          # Sequence number
    stream_id: int,         # Stream identifier
    payload: bytes = b'',   # Application data
    flags: int = 0          # Control flags
)

# Serialize to bytes
frame_bytes = frame.to_bytes()

# Parse from bytes
frame = STTFrame.from_bytes(frame_bytes)

# Encrypt payload (modifies frame in-place)
frame.encrypt_payload(stc_wrapper)

# Decrypt payload (modifies frame in-place)
frame.decrypt_payload(stc_wrapper)

# Frame attributes
frame.frame_type  # int
frame.session_id  # bytes (8)
frame.sequence  # int
frame.stream_id  # int
frame.payload  # bytes
frame.flags  # int
frame._is_encrypted  # bool (internal)
```

**Frame Types** (STT reserved 0x01-0x7F):

- `0x01` = HANDSHAKE_INIT
- `0x02` = HANDSHAKE_CHALLENGE
- `0x03` = HANDSHAKE_RESPONSE
- `0x04` = HANDSHAKE_CONFIRM
- `0x10` = DATA
- `0x11` = STREAM_OPEN
- `0x12` = STREAM_CLOSE
- `0x13` = ACK
- `0x14` = KEEPALIVE
- `0x15` = DISCONNECT
- `0x20` = ENDPOINT_REGISTER
- `0x21` = ENDPOINT_RESOLVE
- `0x22` = ENDPOINT_ROUTE

**Custom Types**: 0x80-0xFF available for application use

### FrameDispatcher

Routes frames to handlers based on frame type.

```python
from seigr_toolset_transmissions import FrameDispatcher

dispatcher = FrameDispatcher()

# Register handler for frame type
async def handle_data(frame: STTFrame) -> None:
    print(f"Received data: {frame.payload}")

dispatcher.register(0x10, handle_data)  # DATA frames

# Dispatch frame
await dispatcher.dispatch(frame)

# Unregister handler
dispatcher.unregister(0x10)
```

---

## Handshake

Pre-shared seed 4-message handshake protocol.

**Coverage**: 87.36%

### STTHandshake

State machine for single handshake.

```python
from seigr_toolset_transmissions import STTHandshake

handshake = STTHandshake(
    session_id: bytes,
    node_seed: bytes,
    shared_seed: bytes,
    peer_node_id: bytes,
    is_initiator: bool,
    stc_wrapper: STCWrapper
)

# Process incoming frame
result = await handshake.process_frame(frame: STTFrame)
# Returns: Optional[STTFrame] (response to send, or None)

# Check if complete
if handshake.is_complete():
    session = handshake.get_session()

# State
handshake.state  # HandshakeState enum
```

### HandshakeManager

Manages multiple concurrent handshakes.

```python
from seigr_toolset_transmissions import HandshakeManager

manager = HandshakeManager(
    node_seed: bytes,
    shared_seed: bytes,
    stc_wrapper: STCWrapper
)

# Initiate handshake
session_id, init_frame = manager.initiate_handshake(peer_node_id)

# Process incoming frame
response = await manager.process_frame(frame: STTFrame)
# Returns: Optional[STTFrame] (response to send)

# Check if handshake complete
if manager.is_handshake_complete(session_id):
    session = manager.get_session(session_id)

# Cleanup
manager.cleanup_handshake(session_id)
```

---

## Storage

STT is a **transmission protocol** - storage is optional and pluggable.
Applications define their own storage implementations using the `StorageProvider` protocol.

### StorageProvider Protocol

Interface for pluggable storage implementations.

```python
from seigr_toolset_transmissions import StorageProvider
from typing import Protocol, Optional

class StorageProvider(Protocol):
    """Protocol for pluggable storage implementations."""
    
    async def store(self, key: bytes, data: bytes) -> None:
        """Store data under a key."""
        ...
    
    async def retrieve(self, key: bytes) -> Optional[bytes]:
        """Retrieve data by key. Returns None if not found."""
        ...
    
    async def exists(self, key: bytes) -> bool:
        """Check if key exists in storage."""
        ...
    
    async def delete(self, key: bytes) -> bool:
        """Delete data by key. Returns True if deleted."""
        ...
```

### InMemoryStorage

Simple in-memory storage implementation (included for testing/demos).

```python
from seigr_toolset_transmissions import InMemoryStorage

storage = InMemoryStorage()

# Use with STTNode
node = STTNode(
    node_seed=seed,
    shared_seed=shared,
    storage=storage  # Optional - STT works without storage
)

# Store data
await storage.store(b"key", b"data")

# Retrieve data
data = await storage.retrieve(b"key")

# Check existence
exists = await storage.exists(b"key")

# Delete
deleted = await storage.delete(b"key")
```

### Custom Storage Implementation

Implement your own storage for your application:

```python
from seigr_toolset_transmissions import StorageProvider

class MyDatabaseStorage:
    """Example: Redis-backed storage."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def store(self, key: bytes, data: bytes) -> None:
        await self.redis.set(key, data)
    
    async def retrieve(self, key: bytes) -> Optional[bytes]:
        return await self.redis.get(key)
    
    async def exists(self, key: bytes) -> bool:
        return await self.redis.exists(key)
    
    async def delete(self, key: bytes) -> bool:
        return await self.redis.delete(key) > 0

# Use with STTNode
node = STTNode(seed, shared, storage=MyDatabaseStorage(redis))
```

### Chamber (DEPRECATED)

> ⚠️ **DEPRECATED**: Use `StorageProvider` protocol instead.
> Chamber will be removed in v0.3.0.

Legacy hash-addressed binary storage.

```python
# DEPRECATED - do not use in new code
from seigr_toolset_transmissions import Chamber
```

### BinaryStorage (DEPRECATED)

> ⚠️ **DEPRECATED**: Use `StorageProvider` protocol instead.
> BinaryStorage will be removed in v0.3.0.

Legacy simple key-value storage.

```python
# DEPRECATED - do not use in new code
from seigr_toolset_transmissions import BinaryStorage
```

---

## Endpoints

Content-addressed routing to named handlers.

**Coverage**: 100%

### EndpointManager

```python
from seigr_toolset_transmissions import EndpointManager

manager = EndpointManager()

# Register endpoint handler
async def telemetry_handler(data: bytes) -> bytes:
    # Process incoming telemetry data
    return response_bytes

manager.register('sensor.telemetry', telemetry_handler)

# Route data to endpoint (by name)
response = await manager.route('sensor.telemetry', data_bytes)

# Route data to endpoint (by hash)
endpoint_hash = manager.get_endpoint_hash('sensor.telemetry')
response = await manager.route_by_hash(endpoint_hash, data_bytes)

# Unregister endpoint
manager.unregister('sensor.telemetry')

# List registered endpoints
endpoints = manager.list_endpoints()
# Returns: List[str] of endpoint names
```

**Endpoint Naming**:

- Names are arbitrary strings
- Hashed with SHA3-256 for routing
- Allows content-addressed discovery

---

## Events

User-defined event system.

**Coverage**: 100%

### EventEmitter

```python
from seigr_toolset_transmissions import EventEmitter

emitter = EventEmitter()

# Register event listener
async def on_connection(peer_id: bytes) -> None:
    print(f"Connected to {peer_id.hex()}")

emitter.on('connection.established', on_connection)

# Emit event
await emitter.emit('connection.established', peer_id=peer_id_bytes)

# One-time listener
emitter.once('connection.closed', handler)

# Remove listener
emitter.off('connection.established', on_connection)

# Remove all listeners for event
emitter.remove_all_listeners('connection.established')

# Check if listeners exist
has_listeners = emitter.has_listeners('connection.established')

# Get listener count
count = emitter.listener_count('connection.established')
```

### STTEvents

Registry of standard events.

```python
from seigr_toolset_transmissions import STTEvents

# Standard events (constants)
STTEvents.SESSION_CREATED
STTEvents.SESSION_CLOSED
STTEvents.STREAM_OPENED
STTEvents.STREAM_CLOSED
STTEvents.DATA_RECEIVED
STTEvents.ERROR
# ... etc
```

---

## Transport

### UDP Transport

Low-latency datagram transport.

**Coverage**: 90%

```python
from seigr_toolset_transmissions.transport import UDPTransport, UDPConfig

config = UDPConfig(
    host='0.0.0.0',
    port=8080,
    max_packet_size=1472,  # MTU - headers
    recv_buffer_size=65536
)

transport = UDPTransport(config)

# Start listening
await transport.start()

# Send data
await transport.send(data: bytes, address: tuple[str, int])

# Receive data
data, address = await transport.receive()

# Stop transport
await transport.stop()
```

### WebSocket Transport

Browser-compatible transport with RFC 6455 implementation.

**Coverage**: 84.63%

```python
from seigr_toolset_transmissions.transport import WebSocketTransport, WebSocketConfig

config = WebSocketConfig(
    host='0.0.0.0',
    port=8080,
    max_frame_size=1048576,  # 1MB
    ping_interval=30.0,
    ping_timeout=10.0
)

transport = WebSocketTransport(config)

# Start server
await transport.start()

# Send data
await transport.send(data: bytes, connection_id: str)

# Receive data
data, connection_id = await transport.receive()

# Close connection
await transport.close(connection_id)

# Stop server
await transport.stop()
```

---

## Utilities

### Serialization

STT custom binary serialization.

**Coverage**: 100%

```python
from seigr_toolset_transmissions.utils import serialize_stt, deserialize_stt

# Serialize Python objects to bytes
data = serialize_stt({'key': 'value', 'count': 42})

# Deserialize bytes to Python objects
obj = deserialize_stt(data)
```

**Supported Types**:

- None, bool, int, float, str, bytes
- list, tuple, dict, set
- Nested structures

### Varint Encoding

Variable-length integer encoding.

```python
from seigr_toolset_transmissions.utils import encode_varint, decode_varint, varint_size

# Encode integer
encoded = encode_varint(12345)

# Decode integer
value, bytes_read = decode_varint(encoded)

# Calculate encoded size
size = varint_size(12345)
```

### Logging

Structured logging for STT.

```python
from seigr_toolset_transmissions.utils import get_logger

logger = get_logger('my_module')

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

---

## Exceptions

All STT exceptions inherit from `STTException`.

```python
from seigr_toolset_transmissions.utils import (
    STTException,          # Base exception
    STTProtocolError,      # Protocol violation
    STTCryptoError,        # Cryptography error
    STTSessionError,       # Session management
    STTStreamError,        # Stream management
    STTFrameError,         # Frame parsing/validation
    STTHandshakeError,     # Handshake failure
    STTTransportError,     # Transport error
    STTFlowControlError,   # Flow control violation
    STTChamberError,       # Storage error
    STTTimeoutError,       # Operation timeout
    STTConfigError,        # Configuration error
    STTVersionError,       # Version mismatch
    STTInvalidStateError,  # Invalid state transition
    STTSerializationError, # Serialization failure
    STTStreamingError,     # Streaming error
    STTStorageError,       # Storage error
    STTEndpointError,      # Endpoint routing error
    STTEventError,         # Event system error
)
```

---

## Complete Example

```python
import asyncio
from seigr_toolset_transmissions import (
    STTNode,
    EndpointManager,
    EventEmitter,
    InMemoryStorage  # Optional - STT works without storage
)

async def main():
    # Initialize node (storage is optional)
    node = STTNode(
        node_seed=b'my_node_secret_32bytes_minimum!',
        shared_seed=b'shared_secret_32bytes_minimum!',
        host='0.0.0.0',
        port=8080,
        storage=None  # Pure transmission mode - no storage needed
    )
    
    # Setup endpoints
    endpoints = EndpointManager()
    
    async def handle_data(data: bytes) -> bytes:
        print(f"Received: {data}")
        return b"ACK"
    
    endpoints.register('data.receiver', handle_data)
    
    # Setup events
    events = EventEmitter()
    
    async def on_session_created(session_id: bytes):
        print(f"New session: {session_id.hex()}")
    
    events.on('session.created', on_session_created)
    
    # Start node
    await node.start()
    
    # Connect to peer
    await node.connect_udp('peer.example.com', 8080)
    
    # Receive packets
    async for packet in node.receive():
        # Route to endpoint
        await endpoints.route('data.receiver', packet.data)
    
    # Cleanup
    await node.stop()

if __name__ == '__main__':
    asyncio.run(main())
```

---

## Related Documentation

- [Architecture](../design/ARCHITECTURE.md) - Design philosophy and protocol details
- [STC Dependency](STC_DEPENDENCY_REFERENCE.md) - External cryptography library
- [User Manual](../user_manual/00_INDEX.md) - Complete developer guide
- [Examples](https://github.com/seigr/seigr-toolset-transmissions/tree/main/examples) - Code samples

---

**Version**: 0.2.0a0 (unreleased)  
**Last Updated**: November 25, 2025  
**Test Coverage**: 93.01%
