# Chapter 6: Sessions and Connections

## Introduction

This chapter explores **sessions** and **connections** in STT - how peers establish communication channels, maintain them, and handle errors. You'll learn the full lifecycle from connection establishment to graceful shutdown.

**Key concepts:**

- **Connection**: Network-level link (UDP socket or WebSocket)
- **Session**: Encrypted, authenticated communication channel on top of connection
- **Lifecycle**: Setup → Active → Teardown

## Connections vs Sessions

### The Layered Model

STT separates network connectivity from logical sessions:

```
+--------------------------------------------------+
|              Session (Logical)                   |
|  - Encrypted communication                       |
|  - Stream multiplexing                           |
|  - Application-level channel                     |
+--------------------------------------------------+
                       ↓
+--------------------------------------------------+
|            Connection (Network)                  |
|  - UDP socket or WebSocket                       |
|  - IP addresses and ports                        |
|  - Physical network link                         |
+--------------------------------------------------+
```

**Analogy:**

- **Connection** = Phone line (physical infrastructure)
- **Session** = Conversation (what you're actually saying)

You can have the phone line connected but no conversation happening.

### Why Separate Them?

**Flexibility:**

- Sessions can resume across transports (UDP → WebSocket)
- Sessions can be pooled by content hash similarity
- Sessions can survive temporary connection loss via resumption tokens

**v0.2.0-alpha:** Includes session continuity and content-affinity pooling features

## Connection Types

### UDP Connections

**UDP (User Datagram Protocol)** is the default transport:

```python
from seigr_toolset_transmissions.node import STTNode

node = STTNode(
    node_id=b"Alice",
    port=8080,
    transport='udp'  # Default
)
node.start()
```

**Properties:**

- **Connectionless**: No TCP handshake overhead
- **Low latency**: Minimal protocol overhead
- **No congestion control**: Application must handle (STT does this)
- **Packet loss possible**: STT detects and retransmits

**Use UDP when:**

- Low latency critical (real-time streaming)
- Direct connectivity available (no restrictive firewalls)
- You control both endpoints

### WebSocket Connections

**WebSocket** provides connection over HTTP:

```python
node = STTNode(
    node_id=b"Alice",
    port=8080,
    transport='websocket'
)
node.start()
```

**Properties:**

- **Connection-oriented**: TCP underneath
- **Firewall-friendly**: Uses HTTP port 80/443
- **Proxy traversal**: Works through HTTP proxies
- **Slightly higher latency**: TCP + HTTP overhead

**Use WebSocket when:**

- Connecting through corporate firewalls
- NAT traversal needed (with TURN server)
- Browser compatibility (future JavaScript client)

**Trade-off:** ~10-20ms extra latency vs UDP, but better connectivity success rate.

### Connection Parameters

```python
node = STTNode(
    node_id=b"Alice",
    port=8080,
    transport='udp',
    bind_address='0.0.0.0',  # Listen on all interfaces
    reuse_port=True,          # Allow multiple processes on same port
    recv_buffer_size=2097152  # 2MB socket buffer
)
```

**bind_address:** Which network interface to listen on

- `'0.0.0.0'`: All interfaces (default)
- `'127.0.0.1'`: Localhost only (testing)
- `'192.168.1.10'`: Specific interface

**recv_buffer_size:** OS-level socket buffer (handles bursts)

## Session Lifecycle

### Phase 1: Initialization

**Before connecting**, initialize node:

```python
# Alice's side
alice_node = STTNode(
    node_id=b"Alice-12345",
    port=8080,
    shared_seed=b"correct-horse-battery-staple"
)
alice_node.start()  # Starts listening
```

**Node is now listening** for incoming connections on port 8080.

### Phase 2: Handshake

**Initiate connection** to peer:

```python
# Alice connects to Bob at 10.0.1.5:8080
session = await alice_node.connect(
    peer_address=('10.0.1.5', 8080),
    peer_node_id=b"Bob-67890"
)
```

**Handshake process** (see Chapter 5 for details):

1. Alice sends HELLO (her nonce + node_id)
2. Bob sends CHALLENGE (his nonce + encrypted challenge)
3. Alice sends AUTH_PROOF (proves she has correct seed)
4. Bob sends FINAL (confirms authentication)

**Duration:** Typically 20-50ms (4 round-trips)

**Result:** `session` object ready for use.

### Phase 3: Active Session

**Session is established** - can now send/receive data:

```python
# Open a stream for file transfer
stream = session.open_stream(purpose='file_transfer')

# Send data
await stream.send(b"Hello Bob!")

# Receive data
data = await stream.receive()
```

**During active phase:**

- Streams can be opened/closed dynamically
- Data flows bidirectionally
- Keep-alives maintain session (automatic)
- Encryption/decryption handled transparently

### Phase 4: Teardown

**Graceful shutdown:**

```python
# Close specific stream
await stream.close()

# Close entire session
await session.close()

# Shutdown node (closes all sessions)
await alice_node.stop()
```

**Orderly teardown:**

1. Application calls `session.close()`
2. STT sends `SESSION_CLOSE` frame to peer
3. Peer acknowledges
4. Both sides clean up resources
5. Connection closed

**Ungraceful shutdown** (power loss, network failure):

- Peer detects missing keep-alives (timeout after ~30 seconds)
- Session marked as dead
- Resources cleaned up
- No data loss for confirmed sends (STT tracks acknowledgments)

## Session Management

### Multiple Sessions (Current v0.2.0-alpha)

**One node can handle multiple sessions** (though typically one-to-one):

```python
# Alice's node
alice_node = STTNode(node_id=b"Alice", port=8080, shared_seed=b"seed_default")
alice_node.start()

# Connect to Bob
session_bob = await alice_node.connect(('10.0.1.5', 8080), b"Bob")

# Simultaneously connect to Carol (if needed)
session_carol = await alice_node.connect(('10.0.1.8', 8081), b"Carol")

# Both sessions active concurrently
```

**Each session:**

- Independent encryption (separate derived keys)
- Independent streams
- Independent lifecycle

**Practical use cases:**

- Client downloading from multiple servers (content distribution with DHT)
- Server handling multiple clients simultaneously (server mode)

**DHT-based discovery:** Use Kademlia DHT to find peers without knowing IPs.

### Session Identification

**Session ID** uniquely identifies each session:

```python
print(session.session_id.hex())
# Output: '0123456789abcdef'  (8 bytes, hex-encoded)
```

**Derivation** (from handshake):

```python
session_id = (nonce_xor + node_xor)[:8]
```

**Properties:**

- Unique per handshake (random nonces)
- Same for both peers (deterministic calculation)
- Used internally for logging, debugging

**You rarely need to access session_id directly** - STT handles it.

### Session State

**Internal states** (FSM - Finite State Machine):

```
INIT → HANDSHAKING → ESTABLISHED → CLOSING → CLOSED
```

**State transitions:**

- `INIT`: Session object created, not yet connected
- `HANDSHAKING`: Handshake in progress (4 messages)
- `ESTABLISHED`: Authenticated, ready for data
- `CLOSING`: Graceful shutdown initiated
- `CLOSED`: Session terminated, resources freed

**Check state:**

```python
from seigr_toolset_transmissions.session import SessionState

if session.state == SessionState.ESTABLISHED:
    # Safe to send data
    await stream.send(data)
else:
    # Not ready yet
    print(f"Session not ready: {session.state}")
```

**State changes are automatic** - STT manages transitions.

## Connection Management

### Content-Affinity Session Pooling

**STT v0.2.0+ includes hash-neighborhood clustering:**

```python
from seigr_toolset_transmissions.session import ContentAffinityPool

# Create affinity pool
pool = ContentAffinityPool(dht=node.dht, max_pool_size=100)

# Add session to pool
content_hash = stc.hash_data(initial_content)
pool.add_session(session, content_hash)

# Get session for related content
related_hash = stc.hash_data(related_content)
try:
    session = pool.get_session_for_content(related_hash)
    # Likely to have related content cached!
except PoolMissError:
    # No suitable session, create new one
    session = await node.connect(peer_addr, peer_id)
    pool.add_session(session, related_hash)
```

**How it works:**

- Sessions cluster by STC.hash prefix (first 4 bytes)
- XOR distance (Kademlia metric) determines affinity
- Related content requests use same session
- Rebalancing occurs when traffic patterns change

Sessions are pooled by content hash similarity rather than transport endpoint.

### Keep-Alive Mechanism

**STT sends periodic keep-alives** to detect dead connections:

```python
# Configured at node level (defaults)
node = STTNode(
    node_id=b"Alice",
    keep_alive_interval=10.0,  # Send keep-alive every 10 seconds
    keep_alive_timeout=30.0     # Declare dead after 30 seconds silence
)
```

**How it works:**

1. Every 10 seconds, STT sends `KEEP_ALIVE` frame
2. Peer responds with `KEEP_ALIVE_ACK`
3. If no response after 30 seconds, session declared dead
4. Application notified via callback/event

**Why needed?**

- Detect crashed peers (no graceful shutdown)
- Detect network failures (cable unplugged)
- Refresh NAT mappings (keeps firewall holes open)

**Overhead:** ~10 bytes every 10 seconds per session (negligible)

### Timeout Handling

**Timeouts at different levels:**

**Handshake timeout:**

```python
session = await alice_node.connect(
    peer_address=('10.0.1.5', 8080),
    peer_node_id=b"Bob",
    timeout=5.0  # Give up after 5 seconds
)
# Raises TimeoutError if handshake not complete
```

**Stream send timeout:**

```python
await stream.send(data, timeout=10.0)
# Raises TimeoutError if not acknowledged in 10 seconds
```

**Keep-alive timeout** (configured above)

**Best practices:**

- Handshake: 5-10 seconds (allows for slow networks)
- Stream send: Depends on data size (1 second per MB reasonable)
- Keep-alive: 30 seconds (balance between detection speed and false positives)

## Error Handling

### Connection Errors

**Common failures:**

```python
try:
    session = await node.connect(('10.0.1.5', 8080), b"Bob")
except ConnectionRefusedError:
    print("Peer not listening (wrong IP or port)")
except ConnectionTimeoutError:
    print("Handshake timeout (peer slow/dead/wrong seed)")
except AuthenticationError:
    print("Wrong shared_seed (authentication failed)")
except Exception as e:
    print(f"Unexpected error: {e}")
```

**Retry logic:**

```python
import asyncio

max_retries = 3
for attempt in range(max_retries):
    try:
        session = await node.connect(('10.0.1.5', 8080), b"Bob", timeout=5.0)
        break  # Success
    except ConnectionTimeoutError:
        if attempt < max_retries - 1:
            await asyncio.sleep(2)  # Wait 2 seconds
        else:
            raise  # Give up
```

### Session Errors

**During active session:**

```python
try:
    await stream.send(large_data)
except SessionClosedError:
    print("Session closed while sending (peer disconnected)")
except StreamClosedError:
    print("Stream closed (application-level close)")
except TimeoutError:
    print("Send timeout (no acknowledgment)")
```

**Handle gracefully:**

```python
if session.state == SessionState.ESTABLISHED:
    try:
        await stream.send(data)
    except SessionClosedError:
        # Session died unexpectedly
        logger.error("Session lost, reconnecting...")
        session = await node.connect(peer_address, peer_node_id)
        # Retry send on new session
```

### Automatic Recovery

**STT provides some automatic recovery:**

**Retransmissions:**

- Lost UDP packets automatically retransmitted (transparent to application)
- Configurable retry limits

**Reordering:**

- Out-of-order frames automatically reordered (streams guarantee order)

**Corruption detection:**

- Checksums detect corrupted frames (discarded, retransmitted)

**What STT does NOT auto-recover:**

- Session-level failures (peer crash) - application must reconnect
- Authentication failures (wrong seed) - application must fix configuration
- Programming errors (invalid data) - application bug

## Reconnection Strategies

### Detecting Disconnection

```python
# Register callback for session events
def on_session_closed(session_id, reason):
    print(f"Session {session_id.hex()} closed: {reason}")
    # Trigger reconnection logic

node.on_session_closed(on_session_closed)
```

**Reasons:**

- `'graceful'`: Application called `session.close()`
- `'timeout'`: Keep-alive timeout (peer dead/unreachable)
- `'error'`: Protocol error (invalid frames)
- `'auth_failure'`: Authentication failed (wrong seed)

### Exponential Backoff

**Good practice** for reconnections:

```python
import asyncio

async def connect_with_retry(node, peer_address, peer_node_id):
    """Connect with exponential backoff retry."""
    delay = 1.0  # Start with 1 second
    max_delay = 60.0
    
    while True:
        try:
            session = await node.connect(peer_address, peer_node_id, timeout=10.0)
            return session  # Success
        except (ConnectionTimeoutError, ConnectionRefusedError):
            print(f"Connection failed, retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)  # Double delay, cap at 60s
```

**Why exponential backoff?**

- Avoids overwhelming network/server (if peer down)
- Reduces resource usage during extended outages
- Standard practice in distributed systems

### Cryptographic Session Continuity

**STT v0.2.0+ includes seed-based resumption:**

```python
from seigr_toolset_transmissions.session import CryptoSessionContinuity

# Create continuity manager
continuity = CryptoSessionContinuity(stc_wrapper, resumption_timeout=86400)

# Create resumable session
session_id, resume_token = continuity.create_resumable_session(
    peer_node_id=b"peer",
    node_seed=node.seed,
    shared_seed=shared_secret
)

# Initial session on WiFi/UDP
session = await node.connect(('192.168.1.100', 8000), peer_id)

# ... network change (WiFi → LTE) ...

# Resume on different transport/IP
resumed = continuity.resume_session(
    resume_token,
    new_transport_type='websocket',
    new_peer_addr=('10.0.0.50', 9000),
    stc_wrapper=stc
)
```

**How it works:**

- Session identity derived from cryptographic seeds
- Resume across IP changes (WiFi → LTE)
- Resume across transports (UDP ↔ WebSocket)
- Resume across devices (same seeds = same session)
- Zero-knowledge proofs verify identity without revealing seeds

Session identity is based on cryptographic seeds rather than network connection IDs.

## Performance Tuning

### Buffer Sizes

**OS-level socket buffers:**

```python
node = STTNode(
    node_id=b"Alice",
    recv_buffer_size=4194304,  # 4MB receive buffer
    send_buffer_size=4194304   # 4MB send buffer
)
```

**Larger buffers:**

- Handle bursts better (sudden influx of packets)
- Reduce packet loss on high-latency networks
- Cost: More memory per connection

**Smaller buffers:**

- Lower memory usage
- Risk: Dropped packets under load

**Rule of thumb:** `buffer_size = bandwidth * latency * 2`

- Example: 100 Mbps *100ms* 2 = 2.5 MB

### Concurrent Sessions

**STT uses asyncio** - efficient for many concurrent sessions:

```python
# Server handling 1000+ concurrent sessions
node = STTNode(node_id=b"Server", port=8080)
node.start()

# Sessions handled concurrently (event loop)
# No thread-per-session overhead
```

**Scalability:**

- 100 sessions: No problem (modern hardware)
- 1,000 sessions: Achievable (server-grade)
- 10,000+ sessions: Requires tuning (OS limits, large buffers)

**Current v0.2.0-alpha** tested up to ~500 concurrent sessions.

### Frame Size Optimization

**Larger frames = higher throughput, lower overhead:**

```python
stream = session.open_stream(
    max_frame_size=65536  # 64 KB frames (vs default 16 KB)
)
```

**Trade-off:**

- Larger frames: Better throughput, higher latency per frame
- Smaller frames: Lower latency, more overhead

**Recommendation:**

- File transfer: 64 KB frames
- Real-time chat: 4 KB frames
- Video streaming: 16-32 KB frames (balance)

## Many-to-Many Sessions

### Server Mode

**Server streaming to multiple clients:**

```python
# Server accepts multiple connections
server = STTNode(node_seed=server_seed, shared_seed=shared_seed, port=8080)
await server.start(server_mode=True)  # Enable server mode

# Server automatically accepts incoming connections
# Clients can now connect

# Broadcast to all active sessions
await server.send_to_all(b"Broadcast message", stream_id=1)

# Or send to specific sessions
session_ids = [session.session_id for session in server.get_active_sessions()]
await server.send_to_sessions(session_ids[:2], b"Targeted message")
```

**Use case:** Video streaming server to many viewers

### DHT-Based Discovery

**Find peers without knowing IP addresses:**

```python
from seigr_toolset_transmissions.dht import KademliaDHT, ContentDistribution

# Initialize DHT
dht = KademliaDHT(node_id=my_node_id, port=9337)
await dht.start()

# Publish content
content_dist = ContentDistribution(dht=dht, node_id=my_node_id)
content_id = await content_dist.publish_content(my_file_data)

# Find peers serving content
peers = await dht.find_providers(content_id)
# Returns: [DHTNode(node_id=..., host='10.0.1.5', port=9337), ...]

# Connect to first available peer
for peer in peers:
    try:
        session = await node.connect((peer.host, peer.port), peer.node_id)
        break
    except ConnectionError:
        continue  # Try next peer
```

**This enables Seigr ecosystem content distribution.**

## Common Patterns

### Request-Response

```python
# Client sends request, waits for response
stream = session.open_stream()
await stream.send(b"GET /resource")
response = await stream.receive()
await stream.close()
```

### Bidirectional Streaming

```python
# Both peers send/receive concurrently
async def send_loop(stream):
    while True:
        data = get_data_to_send()
        await stream.send(data)
        await asyncio.sleep(0.1)

async def receive_loop(stream):
    while True:
        data = await stream.receive()
        process_data(data)

# Run concurrently
await asyncio.gather(
    send_loop(stream),
    receive_loop(stream)
)
```

### Multiplexed Streams

```python
# Use separate streams for different purposes
stream_video = session.open_stream(stream_id=1, purpose='video')
stream_audio = session.open_stream(stream_id=2, purpose='audio')
stream_chat = session.open_stream(stream_id=3, purpose='chat')

# Send on each independently
await stream_video.send(video_frame)
await stream_audio.send(audio_sample)
await stream_chat.send(chat_message)
```

## Visual Summary

```
          Session Lifecycle in STT

+--------------------------------------------------+
|  1. INIT                                         |
|     STTNode created, listening on port           |
+--------------------------------------------------+
                       ↓
+--------------------------------------------------+
|  2. HANDSHAKING                                  |
|     4-message handshake (HELLO, CHALLENGE,       |
|     AUTH_PROOF, FINAL)                           |
|     Duration: ~20-50ms                           |
+--------------------------------------------------+
                       ↓
+--------------------------------------------------+
|  3. ESTABLISHED                                  |
|     Streams can be opened/closed                 |
|     Data flows bidirectionally                   |
|     Keep-alives maintain session                 |
|     Duration: Seconds to hours                   |
+--------------------------------------------------+
                       ↓
+--------------------------------------------------+
|  4. CLOSING                                      |
|     Graceful shutdown (SESSION_CLOSE frame)      |
|     Resources freed                              |
+--------------------------------------------------+
                       ↓
+--------------------------------------------------+
|  5. CLOSED                                       |
|     Session terminated                           |
|     Can create new session if needed             |
+--------------------------------------------------+
```

## Testing Your Understanding

1. **What's the difference between a connection and a session?**
   - Connection is network-level (UDP/WebSocket); session is logical encrypted channel

2. **Can one STT node handle multiple sessions simultaneously?**
   - Yes - SessionManager tracks multiple concurrent sessions

3. **How does STT detect dead peers?**
   - Keep-alive frames every 10 seconds; timeout after 30 seconds silence

4. **Is XOR used for session encryption?**
   - No - XOR only for session ID mixing; STC handles encryption

5. **Can a session survive connection loss?**
   - Not in v0.2.0-alpha; connection migration planned for v0.6.0+

6. **What happens if handshake fails due to wrong seed?**
   - AuthenticationError raised; session not established

## Common Issues and Solutions

**Problem:** Connection refused  
**Solution:** Check peer is listening, verify IP/port correct, check firewall

**Problem:** Handshake timeout  
**Solution:** Check seeds match, verify network reachability, check NAT/firewall

**Problem:** Session randomly disconnecting  
**Solution:** Check keep-alive settings, verify stable network, check peer logs

**Problem:** High latency  
**Solution:** Use UDP instead of WebSocket, check network conditions, tune buffer sizes

**Problem:** Authentication failed  
**Solution:** Verify both peers using identical shared_seed

## Next Steps

- **Chapter 7**: Streams and Multiplexing (using established sessions efficiently)
- **Chapter 8**: Transport Layer (deep dive into UDP vs WebSocket)
- **Chapter 11**: Error Handling (comprehensive error recovery patterns)

**Key Takeaways:**

- Connection (network) ≠ Session (logical encrypted channel)
- Handshake establishes authenticated session (~20-50ms)
- Keep-alives detect dead connections (30-second timeout)
- Multiple concurrent sessions supported (current and future)
- STT provides automatic retransmission, reordering, corruption detection
- Future: DHT discovery, server-to-many sessions, connection migration
