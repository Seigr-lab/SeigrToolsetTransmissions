# STT API Reference - v0.2.0-alpha

**Status**: Pre-release - Functional APIs with 90.03% test coverage

**Coverage by Component**:

- Session Management: **100%**
- Session Manager: **100%**
- Serialization: **100%**
- Stream Operations: **99.24%**
- Stream Manager: **98.61%**
- STC Wrapper: **98.78%**
- Frame Protocol: **98.26%**
- UDP Transport: **89.86%**
- Handshake Protocol: **87.36%**
- WebSocket Transport: **84.17%**
- Node Runtime: **82.95%**

---

## Agnostic Primitives (Phase 0 - NEW)

**Philosophy**: Zero semantic assumptions. STT transports/stores/routes bytes. YOU define meaning.

### BinaryStreamEncoder

**Async generator yielding encrypted byte segments.**

```python
from seigr_toolset_transmissions.streaming import BinaryStreamEncoder

encoder = BinaryStreamEncoder(
    data_source: Union[bytes, AsyncIterable[bytes]],
    stc_context: StreamingContext,
    mode: Literal["live", "bounded"] = "bounded",
    segment_size: int = 1400
)

async for encrypted_segment in encoder:
    # Yields tuple: (sequence_num, encrypted_bytes)
    # STT doesn't know what the bytes represent
    await your_transport(encrypted_segment)
```

**Parameters:**

- `data_source`: Bytes or async generator (YOUR data: video, sensors, files, anything)
- `stc_context`: STC encryption context from `STCWrapper.create_stream_context()`
- `mode`: `"live"` (unknown size, real-time) or `"bounded"` (known size, batch)
- `segment_size`: MTU optimization (NOT semantic chunking)

**What it does:**

- Splits bytes into segments (MTU-optimized)
- Encrypts with STC
- Yields (sequence_num, encrypted_bytes) tuples

**What it does NOT:**

- Parse your data format
- Assume data type (video? sensors? doesn't care)
- Know about H.264, JSON, protobuf, etc.

---

### BinaryStreamDecoder

**Async iterator handling out-of-order encrypted segments.**

```python
from seigr_toolset_transmissions.streaming import BinaryStreamDecoder

decoder = BinaryStreamDecoder(stc_context: StreamingContext)

# Receive segments (possibly out-of-order from network)
decoder.receive_segment(encrypted_bytes, sequence_num)

# Get complete decrypted bytes (handles reordering)
decrypted = await decoder.receive_all()

# YOU interpret the bytes
your_data = your_deserializer(decrypted)
```

**Methods:**

**`receive_segment(encrypted_bytes: bytes, sequence: int)`**  
Buffer encrypted segment (handles out-of-order)

**`async receive_all() -> bytes`**  
Wait for all segments, decrypt, return complete bytes

**What it does:**

- Buffer out-of-order segments
- Reorder by sequence number
- Decrypt with STC
- Return complete byte stream

**What it does NOT:**

- Know what bytes represent
- Deserialize application data
- Validate schemas

---

### BinaryStorage

**Hash-addressed encrypted byte buckets (content-addressable storage).**

```python
from seigr_toolset_transmissions.storage import BinaryStorage

storage = BinaryStorage(stc_wrapper: STCWrapper, storage_dir: Path = Path(".storage"))

# Store arbitrary bytes (images, documents, sensor logs, anything)
hash_address = await storage.store(arbitrary_bytes)
# Returns SHA3-256 hash (deterministic, same bytes = same hash)

# Retrieve by hash
retrieved = await storage.retrieve(hash_address)

# Deduplication: same content = same hash = same storage
```

**Methods:**

**`async store(data: bytes) -> str`**  
Store encrypted bytes, return SHA3-256 hash address

**`async retrieve(hash_address: str) -> bytes`**  
Retrieve decrypted bytes by hash

**`async exists(hash_address: str) -> bool`**  
Check if hash exists

**What it does:**

- Hash with SHA3-256 (deterministic addressing)
- Encrypt with STC before storing
- Deduplicate automatically
- Store in filesystem (configurable directory)

**What it does NOT:**

- Know what's stored (image? document? doesn't care)
- Validate file types
- Maintain metadata (YOU add if needed)
- Organize into folders

---

### EndpointManager

**Multi-endpoint routing with per-endpoint queues.**

```python
from seigr_toolset_transmissions.routing import EndpointManager

endpoint_mgr = EndpointManager()

# Route bytes to endpoints (peers, services, destinations)
await endpoint_mgr.route_to_endpoint("video_sink", frame_bytes)
await endpoint_mgr.route_to_endpoint("telemetry", sensor_bytes)

# Each endpoint has independent queue
data = await endpoint_mgr.receive_from_endpoint("video_sink")
```

**Methods:**

**`async route_to_endpoint(endpoint_id: str, data: bytes)`**  
Send bytes to specific endpoint queue

**`async receive_from_endpoint(endpoint_id: str) -> bytes`**  
Receive bytes from endpoint queue

**`list_endpoints() -> List[str]`**  
Get all endpoint IDs

**What it does:**

- Maintain per-endpoint queues
- Route bytes to destinations
- Handle concurrent endpoints

**What it does NOT:**

- Know why routing (load balancing? replication? doesn't matter)
- Interpret endpoint names (YOU choose scheme)
- Validate data

---

### EventEmitter

**User-defined event system (YOU define event types).**

```python
from seigr_toolset_transmissions.events import EventEmitter

emitter = EventEmitter()

# Define YOUR event types (STT has no built-in events)
emitter.on("temperature_alert", handle_temp)
emitter.on("frame_received", handle_frame)
emitter.on("peer_connected", handle_peer)

# Emit YOUR events
await emitter.emit("temperature_alert", {"temp": 95.3, "sensor": "cpu"})
```

**Methods:**

**`on(event_type: str, handler: Callable)`**  
Register handler for event type (YOU define types)

**`off(event_type: str, handler: Callable)`**  
Unregister handler

**`async emit(event_type: str, data: Any)`**  
Emit event to all handlers

**What it does:**

- Dispatch to registered handlers
- Support async handlers
- Allow multiple handlers per type

**What it does NOT:**

- Define event types (YOU define)
- Validate payloads
- Enforce schemas

---

### FrameDispatcher

**Custom frame types 0x80-0xFF (YOUR binary protocol).**

```python
from seigr_toolset_transmissions.frames import FrameDispatcher

dispatcher = FrameDispatcher()

# Register YOUR custom frame handlers
dispatcher.register_handler(0x80, handle_custom_handshake)
dispatcher.register_handler(0x81, handle_custom_data)
dispatcher.register_handler(0xFF, handle_custom_control)

# STT calls handlers when those frame types arrive
await dispatcher.dispatch(frame_type, frame_payload)
```

**Methods:**

**`register_handler(frame_type: int, handler: Callable)`**  
Register handler for custom frame type (0x80-0xFF only)

**`async dispatch(frame_type: int, payload: bytes)`**  
Dispatch frame to registered handler

**What it does:**

- Route frames to type-specific handlers
- Support custom types 0x80-0xFF (STT reserves 0x01-0x7F)
- Call your handlers with payloads

**What it does NOT:**

- Define frame semantics (YOU define what 0x80 means)
- Parse payloads (YOU parse format)
- Validate protocols

---

## Core Session/Stream Components

## STTNode

Main runtime for STT protocol - **82.95% coverage** - Functional Implementation

```python
from seigr_toolset_transmissions import STTNode

node = STTNode(
    node_seed: bytes,      # STC initialization seed (32+ bytes recommended)
    shared_seed: bytes,    # Pre-shared secret for peers (32+ bytes recommended)
    host: str = "0.0.0.0",
    port: int = 0,         # UDP port (0 = random available port)
    chamber_path: Optional[Path] = None
)
```

### Methods

**`async start() -> Tuple[str, int]`**  
Start node, returns (local_ip, local_port)

**`async stop() -> None`**  
Stop node and close all sessions

**`async connect_udp(peer_host: str, peer_port: int) -> STTSession`**  
Connect to peer via UDP

**`get_stats() -> dict`**  
Get node statistics

---

## STCWrapper

Centralizes all STC cryptographic operations.

```python
from seigr_toolset_transmissions.crypto import STCWrapper

stc = STCWrapper(seed: bytes)
```

### Methods

**`hash_data(data: bytes, context: Optional[Dict] = None) -> bytes`**  
Hash using STC.hash (PHE)

**`generate_node_id(identity: bytes) -> bytes`**  
Generate 32-byte node ID

**`derive_session_key(context_data: Dict) -> bytes`**  
Derive session key using STC.derive_key (CKE)

**`rotate_session_key(current_key: bytes, nonce: bytes) -> bytes`**  
Rotate session key

**`encrypt_frame(payload: bytes, associated_data: Dict) -> Tuple[bytes, Dict]`**  
Encrypt frame with AEAD-like protection

**`decrypt_frame(encrypted: bytes, metadata: Dict, associated_data: Dict) -> bytes`**  
Decrypt and verify frame

**`create_stream_context(session_id: bytes, stream_id: int) -> StreamContext`**  
Create isolated context for stream

---

## STTFrame

Binary frame protocol with STC encryption.

```python
from seigr_toolset_transmissions.frame import STTFrame

frame = STTFrame(
    frame_type: int,
    session_id: bytes,     # 8 bytes
    stream_id: int,
    sequence: int,
    flags: int = 0,
    payload: bytes = b''
)
```

### Methods

**`encrypt_payload(stc_wrapper: STCWrapper) -> None`**  
Encrypt frame payload

**`decrypt_payload(stc_wrapper: STCWrapper) -> bytes`**  
Decrypt frame payload

**`to_bytes() -> bytes`**  
Serialize to binary

**`from_bytes(data: bytes, decrypt: bool = False, stc_wrapper: Optional[STCWrapper] = None) -> STTFrame`**  
Deserialize from binary

---

## STTHandshake

Pre-shared seed authentication protocol.

```python
from seigr_toolset_transmissions.handshake import STTHandshake

handshake = STTHandshake(
    stc_wrapper: STCWrapper,
    shared_seed: bytes,
    node_id: bytes
)
```

### Methods

**`initiate_handshake() -> bytes`**  
Create HELLO message

**`handle_hello(hello_bytes: bytes) -> bytes`**  
Handle HELLO, create HELLO_RESP

**`handle_response(response_bytes: bytes) -> Tuple[bytes, bytes]`**  
Handle HELLO_RESP, returns (session_key, peer_node_id)

**`get_session_key() -> Optional[bytes]`**  
Get derived session key

---

## STTSession

Session management with STC key rotation.

### Properties

- `session_id`: bytes (8 bytes)
- `peer_node_id`: bytes (32 bytes)
- `session_key`: Optional[bytes]
- `state`: int
- `stream_manager`: StreamManager

### Methods

**`should_rotate_keys() -> bool`**  
Check if rotation needed

**`async rotate_keys(stc_wrapper: STCWrapper) -> None`**  
Rotate session keys

**`async close() -> None`**  
Close session

**`get_stats() -> dict`**  
Get statistics

---

## Chamber

STC-encrypted storage.

```python
from seigr_toolset_transmissions.chamber import Chamber

chamber = Chamber(
    chamber_path: Path,
    node_id: bytes,
    stc_wrapper: STCWrapper
)
```

### Methods

**`store_key(key_id: str, key_data: bytes) -> None`**  
Store encrypted key

**`retrieve_key(key_id: str) -> Optional[bytes]`**  
Retrieve key

**`store_session(session_id: str, session_data: Dict) -> None`**  
Store session metadata

**`retrieve_session(session_id: str) -> Optional[Dict]`**  
Retrieve session metadata

---

## Serialization

Native STT binary format.

```python
from seigr_toolset_transmissions.utils.serialization import serialize_stt, deserialize_stt

# Serialize
binary = serialize_stt({'key': 'value', 'num': 42})

# Deserialize
data = deserialize_stt(binary)
```

---

## Transport

### UDPTransport

```python
from seigr_toolset_transmissions.transport import UDPTransport

udp = UDPTransport(on_frame_received=callback)
await udp.start()
await udp.send_frame(frame, (peer_ip, peer_port))
```

### WebSocketTransport

```python
from seigr_toolset_transmissions.transport import WebSocketTransport

# Connect
ws = await WebSocketTransport.connect(host, port, on_frame_received=callback)
await ws.send_frame(frame)
await ws.close()
```

---

## Streaming

```python
from seigr_toolset_transmissions.streaming import StreamEncoder, StreamDecoder
from seigr_toolset_transmissions.crypto import STCWrapper

stc = STCWrapper(seed)
stream_ctx = stc.create_stream_context(session_id, stream_id)

# Encode
encoder = StreamEncoder(stream_ctx, chunk_size=65536)
for encrypted_chunk in encoder.encode_bytes(data):
    send_chunk(encrypted_chunk)

# Decode
decoder = StreamDecoder(stream_ctx)
decrypted = decoder.decode_to_bytes(encrypted_chunks)
```

---

For more details, see the source code - all modules have comprehensive docstrings.
