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
