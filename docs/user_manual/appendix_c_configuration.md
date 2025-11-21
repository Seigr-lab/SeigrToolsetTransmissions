# Appendix C: Configuration Reference

## Introduction

Complete reference for all STTNode configuration parameters and their effects.

## STTNode Parameters

### Basic Configuration

```python
node = STTNode(
    node_id: bytes,                    # Required
    port: int = 0,                     # Default: random port
    shared_seed: bytes = None,         # Required for sessions
    transport: str = 'udp'             # 'udp' or 'websocket'
)
```

**node_id** (bytes, required):
- Unique identifier for this node
- Length: 32 bytes recommended (can be shorter)
- Used in handshake, session derivation
- Example: `b"Alice-Node-12345"`

**port** (int, default: 0):
- Listen port for incoming connections
- `0`: OS assigns random port (client mode)
- `1-65535`: Specific port (server mode)
- Ports < 1024 require root/admin (not recommended)

**shared_seed** (bytes, required for connecting):
- Pre-shared seed for STC encryption
- Length: 32 bytes (256 bits) minimum
- Must be cryptographically random
- Generate: `secrets.token_bytes(32)`

**transport** (str, default: 'udp'):
- `'udp'`: UDP sockets (default, fastest)
- `'websocket'`: WebSocket over TCP (firewall-friendly)

### Transport Configuration

```python
# UDP-specific
node = STTNode(
    transport='udp',
    bind_address: str = '0.0.0.0',     # Default: all interfaces
    reuse_port: bool = False,          # Default: False
    recv_buffer_size: int = 2097152,   # Default: 2 MB
    send_buffer_size: int = 2097152    # Default: 2 MB
)
```

**bind_address** (str, default: '0.0.0.0'):
- Network interface to listen on
- `'0.0.0.0'`: All IPv4 interfaces
- `'::'`: All IPv6 interfaces
- `'127.0.0.1'`: Localhost only (testing)
- Specific IP: `'192.168.1.10'` (one interface)

**reuse_port** (bool, default: False):
- Allow multiple processes on same port
- Linux/BSD: Load balance across processes
- Windows: Not supported
- Use case: Multi-process servers

**recv_buffer_size** (int, default: 2 MB):
- OS-level socket receive buffer
- Larger = handle bursts better, less packet loss
- Smaller = less memory, risk drops under load
- Formula: `bandwidth * RTT * 2`

**send_buffer_size** (int, default: 2 MB):
- OS-level socket send buffer
- Similar trade-offs as recv_buffer_size

```python
# WebSocket-specific
node = STTNode(
    transport='websocket',
    tls: bool = False,                 # Default: False (WS), True = WSS
    tls_cert: str = None,              # Path to TLS certificate
    tls_key: str = None,               # Path to TLS private key
    proxy: str = None,                 # HTTP proxy URL
    proxy_auth: tuple = None           # (username, password)
)
```

**tls** (bool, default: False):
- Use WebSocket Secure (WSS) instead of WS
- Requires `tls_cert` and `tls_key`
- Double encryption: TLS + STC (overhead but compliance)

**tls_cert** (str, default: None):
- Path to TLS certificate file (.pem or .crt)
- Required if `tls=True`
- Self-signed or CA-signed

**tls_key** (str, default: None):
- Path to TLS private key file (.pem or .key)
- Required if `tls=True`

**proxy** (str, default: None):
- HTTP proxy URL: `'http://proxy.company.com:8080'`
- For WebSocket through corporate proxies
- CONNECT method used

**proxy_auth** (tuple, default: None):
- Proxy authentication: `('username', 'password')`
- Required if proxy needs auth

### Session Configuration

```python
node = STTNode(
    keep_alive_interval: float = 10.0,    # Default: 10 seconds
    keep_alive_timeout: float = 30.0,     # Default: 30 seconds
    handshake_timeout: float = 10.0,      # Default: 10 seconds
    max_concurrent_sessions: int = 100    # Default: 100
)
```

**keep_alive_interval** (float, default: 10.0):
- Send keep-alive frame every N seconds
- Lower = faster failure detection, higher overhead
- Higher = less overhead, slower detection
- Recommended: 5-30 seconds

**keep_alive_timeout** (float, default: 30.0):
- Declare session dead after N seconds without response
- Should be > 2 * keep_alive_interval
- Lower = faster detection, risk false positives (transient network issues)
- Higher = tolerate longer outages, slower recovery

**handshake_timeout** (float, default: 10.0):
- Maximum time for handshake completion
- Includes all 4 messages (HELLO, CHALLENGE, AUTH_PROOF, FINAL)
- Slow networks may need higher (20-30s)
- Fast LANs can use lower (5s)

**max_concurrent_sessions** (int, default: 100):
- Maximum number of simultaneous sessions
- Limits memory usage (each session has buffers)
- Per-session memory: ~100 KB
- Exceeding raises `TooManySessionsError`

### Stream Configuration

```python
node = STTNode(
    max_concurrent_streams: int = 256,    # Default: 256
    default_max_frame_size: int = 16384,  # Default: 16 KB
    stream_recv_buffer: int = 1048576,    # Default: 1 MB
    stream_send_buffer: int = 1048576     # Default: 1 MB
)
```

**max_concurrent_streams** (int, default: 256):
- Maximum streams per session
- Each stream: ~10 KB overhead
- 256 streams = ~2.5 MB per session

**default_max_frame_size** (int, default: 16384):
- Default frame size for new streams
- Can override per-stream in `open_stream()`
- Trade-off: Latency vs throughput

**stream_recv_buffer** (int, default: 1 MB):
- Per-stream receive buffer
- Out-of-order frames buffered here

**stream_send_buffer** (int, default: 1 MB):
- Per-stream send buffer
- Unsent data buffered here (Nagle-like)

### Reliability Configuration

```python
node = STTNode(
    retransmit_timeout: float = 0.1,      # Default: 100 ms
    max_retransmits: int = 5,             # Default: 5
    ack_delay: float = 0.05,              # Default: 50 ms
    enable_nack: bool = True              # Default: True
)
```

**retransmit_timeout** (float, default: 0.1):
- Retransmit if no ACK after N seconds
- Adjust based on RTT (should be ~2 * RTT)
- Too low: Spurious retransmissions (waste bandwidth)
- Too high: Slow recovery from loss

**max_retransmits** (int, default: 5):
- Maximum retransmission attempts
- After max, frame considered undeliverable (error)
- Higher = more resilient to transient loss
- Lower = faster failure detection

**ack_delay** (float, default: 0.05):
- Delay ACKs to batch multiple (efficiency)
- Lower = faster acknowledgment, more ACK frames
- Higher = fewer ACK frames, higher latency

**enable_nack** (bool, default: True):
- Use NACKs (negative acknowledgments) for faster recovery
- True: Request missing frames immediately
- False: Wait for timeout (slower but simpler)

### Performance Tuning

```python
node = STTNode(
    no_delay: bool = False,               # Default: False (Nagle-like)
    compression: bool = False,            # Default: False (not implemented)
    priority_enabled: bool = False        # Default: False (future)
)
```

**no_delay** (bool, default: False):
- Disable send buffering (Nagle-like algorithm)
- False: Buffer small sends, send full frames (higher throughput)
- True: Send immediately (lower latency, more overhead)
- Use True for real-time applications (chat, gaming)

**compression** (bool, default: False):
- Enable payload compression (future feature)
- Not implemented in v0.2.0-alpha

**priority_enabled** (bool, default: False):
- Enable stream priority (future feature)
- Not implemented in v0.2.0-alpha

### Logging Configuration

```python
import logging

# Set log level
logging.getLogger('seigr_toolset_transmissions').setLevel(logging.DEBUG)

# Or at node creation
node = STTNode(
    log_level: str = 'INFO'               # 'DEBUG', 'INFO', 'WARNING', 'ERROR'
)
```

**log_level** (str, default: 'INFO'):
- `'DEBUG'`: All messages (verbose)
- `'INFO'`: Normal operation events
- `'WARNING'`: Potential issues
- `'ERROR'`: Errors only

## Stream Parameters

### Opening a Stream

```python
stream = session.open_stream(
    stream_id: int = None,                # Default: auto-assign
    max_frame_size: int = None,           # Default: from node config
    purpose: str = None,                  # Default: None (optional label)
    no_delay: bool = None                 # Default: from node config
)
```

**stream_id** (int, default: auto-assign):
- Specific stream ID (0-65535)
- None: Auto-assign next available
- Both peers must agree on ID

**max_frame_size** (int, default: node default):
- Override node's default_max_frame_size
- Range: 1-65536 bytes
- Tune per stream: video=32KB, chat=4KB

**purpose** (str, default: None):
- Human-readable label (for logging)
- Example: `'video_stream'`, `'audio'`, `'chat'`

**no_delay** (bool, default: node default):
- Override node's no_delay setting
- True: Low latency, False: High throughput

## Connection Parameters

### Connecting to Peer

```python
session = await node.connect(
    peer_address: tuple,                  # ('ip', port) required
    peer_node_id: bytes,                  # Required
    timeout: float = 10.0,                # Default: 10 seconds
    transport: str = None                 # Default: node's transport
)
```

**peer_address** (tuple, required):
- Remote peer address: `('192.168.1.5', 8080)`
- IPv4 or IPv6
- Must be reachable (firewall, NAT)

**peer_node_id** (bytes, required):
- Expected node_id of peer
- Verified during handshake
- Prevents connecting to wrong peer

**timeout** (float, default: 10.0):
- Handshake timeout (override node's handshake_timeout)
- Seconds to wait for handshake completion

**transport** (str, default: node's transport):
- Override node's default transport
- `'udp'` or `'websocket'`
- Future: Auto-fallback

## Environment Variables

**Override configuration via environment:**

```bash
export STT_PORT=8080
export STT_TRANSPORT=udp
export STT_LOG_LEVEL=DEBUG
export STT_RECV_BUFFER_SIZE=4194304  # 4 MB
export STT_KEEP_ALIVE_INTERVAL=5.0
```

**Load in code:**
```python
import os

node = STTNode(
    port=int(os.getenv('STT_PORT', 8080)),
    transport=os.getenv('STT_TRANSPORT', 'udp'),
    log_level=os.getenv('STT_LOG_LEVEL', 'INFO'),
    recv_buffer_size=int(os.getenv('STT_RECV_BUFFER_SIZE', 2097152)),
    keep_alive_interval=float(os.getenv('STT_KEEP_ALIVE_INTERVAL', 10.0))
)
```

## Configuration Presets

### Low-Latency Preset

```python
LOW_LATENCY_CONFIG = {
    'transport': 'udp',
    'max_frame_size': 4096,
    'no_delay': True,
    'recv_buffer_size': 524288,        # 512 KB
    'send_buffer_size': 524288,
    'ack_delay': 0.01,                 # 10 ms
    'retransmit_timeout': 0.05         # 50 ms
}

node = STTNode(node_id=b"Node", **LOW_LATENCY_CONFIG)
```

### High-Throughput Preset

```python
HIGH_THROUGHPUT_CONFIG = {
    'transport': 'udp',
    'max_frame_size': 65536,
    'no_delay': False,
    'recv_buffer_size': 8388608,       # 8 MB
    'send_buffer_size': 8388608,
    'ack_delay': 0.1,                  # 100 ms
    'max_concurrent_streams': 64       # Focus bandwidth
}

node = STTNode(node_id=b"Node", **HIGH_THROUGHPUT_CONFIG)
```

### Balanced Preset

```python
BALANCED_CONFIG = {
    'transport': 'udp',
    'max_frame_size': 16384,           # Default
    'recv_buffer_size': 2097152,       # 2 MB
    'send_buffer_size': 2097152,
    'max_concurrent_streams': 256,
    'keep_alive_interval': 10.0,
    'keep_alive_timeout': 30.0
}

node = STTNode(node_id=b"Node", **BALANCED_CONFIG)
```

## Validation Rules

**node_id:**
- Must be bytes
- Recommended: 32 bytes (can be shorter)
- Not empty

**port:**
- Integer 0-65535
- <1024 requires privileges (avoid)

**shared_seed:**
- Must be bytes
- Minimum: 16 bytes (128 bits)
- Recommended: 32 bytes (256 bits)
- Cryptographically random

**timeouts:**
- Must be positive floats
- keep_alive_timeout > 2 * keep_alive_interval

**buffer sizes:**
- Positive integers
- Practical max: 16 MB (OS limits)

## Key Takeaways

- **node_id, shared_seed:** Required for sessions
- **port=0:** Random (client), specific (server)
- **transport:** UDP (fast), WebSocket (firewall-friendly)
- **Buffers:** Larger = better burst handling, more memory
- **Keep-alive:** Balance detection speed (low interval) vs overhead
- **Frame size:** Small (latency), large (throughput)
- **Timeouts:** Tune for network conditions (RTT, loss)
- **Presets:** Low-latency, high-throughput, balanced
- **Environment:** Override via env vars for deployment
