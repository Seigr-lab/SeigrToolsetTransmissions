# Chapter 8: Transport Layer

## Introduction

STT operates on top of a **transport layer** that moves frames between peers. This chapter explains the two transport options (UDP and WebSocket), when to use each, how they work, and their trade-offs.

**Transport layer** = The "postal service" that delivers STT frames between network endpoints.

**Agnostic Design:** UDP and WebSocket transport encrypted bytes - NOTHING more. STT doesn't care if those bytes represent video streams, sensor readings, file transfers, or custom protocol messages. Transport choice depends on network constraints (firewalls, NAT), not data semantics.

## Transport Options

### Overview

STT supports two transports:

| Transport | Protocol | Characteristics | Use Case |
|-----------|----------|-----------------|----------|
| **UDP** | User Datagram Protocol | Connectionless, low overhead, fast | Direct peer-to-peer, low latency |
| **WebSocket** | TCP + HTTP upgrade | Connection-oriented, firewall-friendly | Through firewalls, browser compatibility |

**Both provide the same STT features** (encryption, multiplexing, reliability) - transport only affects how frames reach the destination.

### UDP Transport

**UDP (User Datagram Protocol)** is the default and recommended transport:

```python
node = STTNode(
    node_id=b"Alice",
    port=8080,
    transport='udp'  # Default (can omit)
)
```

**Characteristics:**

- **Connectionless**: No handshake (send packets directly)
- **Stateless**: No connection tracking in kernel
- **Unreliable**: Packets can be lost, reordered, duplicated
- **Lightweight**: Minimal protocol overhead (~8 bytes UDP header)

**STT handles reliability** on top of UDP (retransmissions, ordering).

**When to use UDP:**

- ✅ Direct connectivity (both peers have reachable IP addresses)
- ✅ Low latency critical (real-time streaming, gaming)
- ✅ No restrictive firewalls (corporate environments may block)
- ✅ You control both endpoints (can configure ports)

**When NOT to use UDP:**

- ❌ Through NAT without port forwarding
- ❌ Corporate firewalls (often block non-standard UDP)
- ❌ Public internet where only HTTP/HTTPS works

### WebSocket Transport

**WebSocket** tunnels STT over HTTP/TCP:

```python
node = STTNode(
    node_id=b"Alice",
    port=8080,
    transport='websocket'
)
```

**Characteristics:**

- **Connection-oriented**: TCP handshake + WebSocket upgrade
- **Reliable**: TCP retransmissions (redundant with STT retransmissions)
- **Firewall-friendly**: Uses HTTP ports (80/443)
- **Proxy support**: Works through HTTP proxies

**Overhead:**

- TCP header: ~20 bytes
- WebSocket frame: ~2-14 bytes (depends on payload size)
- **Total:** ~30-50ms extra latency vs UDP (connection setup + TCP overhead)

**When to use WebSocket:**

- ✅ Through corporate firewalls (HTTP allowed)
- ✅ NAT traversal with TURN server (WebSocket over HTTP)
- ✅ Browser compatibility (future JavaScript client)
- ✅ Proxied environments (HTTP proxy support)

**When NOT to use WebSocket:**

- ❌ Low latency critical (TCP + HTTP overhead significant)
- ❌ Direct connectivity available (UDP simpler and faster)

## UDP Deep Dive

### Packet Structure

**UDP packet carrying STT frame:**

```
+------------------+
| IP Header        | 20 bytes (IPv4) or 40 bytes (IPv6)
+------------------+
| UDP Header       | 8 bytes
|  - Source Port   |
|  - Dest Port     |
|  - Length        |
|  - Checksum      |
+------------------+
| STT Frame        | Variable (up to ~65KB)
|  - Frame Header  |
|  - Payload       |
+------------------+
```

**MTU (Maximum Transmission Unit):**

- Ethernet: 1500 bytes
- IPv4 overhead: 20 bytes
- UDP overhead: 8 bytes
- **Available for STT frame:** ~1472 bytes (typical)

**Path MTU Discovery:**
STT fragments frames larger than MTU (application-level fragmentation).

### Port Configuration

```python
node = STTNode(
    node_id=b"Alice",
    port=8080,               # Listen port
    bind_address='0.0.0.0'  # Listen on all interfaces
)
```

**Firewall rules** (example using `ufw` on Linux):

```bash
# Allow incoming UDP on port 8080
sudo ufw allow 8080/udp
```

**Port forwarding** (if behind NAT):

- Router config: Forward external_port → internal_ip:8080/UDP
- STT node listens on internal_ip:8080

### Performance Tuning

**Socket buffer sizes:**

```python
node = STTNode(
    node_id=b"Alice",
    transport='udp',
    recv_buffer_size=4194304,  # 4 MB receive buffer
    send_buffer_size=4194304   # 4 MB send buffer
)
```

**Why larger buffers?**

- Handle bursts (sudden influx of packets)
- Reduce packet loss (more time for application to read)
- Critical for high-bandwidth transfers

**OS-level tuning** (Linux):

```bash
# Increase max socket buffer size
sudo sysctl -w net.core.rmem_max=8388608
sudo sysctl -w net.core.wmem_max=8388608
```

**Packet loss handling:**
STT detects and retransmits lost packets (automatic).

### NAT Traversal

**Problem:** Peers behind NAT can't directly connect

**STT 0.2.0a0 (unreleased) solution:**

- **NAT traversal**: Not currently implemented (manual port forwarding required)
- Hole punching for direct peer connections
- Fallback to relay if direct connection fails

**Manual alternatives:**

- Port forwarding (manual configuration on router)
- DMZ host (expose peer directly - insecure)
- VPN (tunnel through intermediate server)

**Best practice:** Use built-in NAT traversal first, fall back to manual only if needed.

## WebSocket Deep Dive

### Connection Establishment

**WebSocket upgrade** from HTTP:

```
Client → Server:
GET /stt HTTP/1.1
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==

Server → Client:
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=

[Connection upgraded to WebSocket - now sends STT frames]
```

**Latency impact:**

- TCP handshake: ~1 RTT (round-trip time)
- HTTP upgrade: ~1 RTT
- **Total setup:** ~2 RTT (~20-100ms depending on network)

**Once established:** Similar performance to UDP (TCP overhead ~5-10% lower throughput).

### Frame Encapsulation

**WebSocket frame carrying STT frame:**

```
+------------------+
| IP Header        | 20 bytes (IPv4)
+------------------+
| TCP Header       | 20+ bytes (options)
+------------------+
| WebSocket Frame  | 2-14 bytes
|  - FIN, opcode   |
|  - Mask bit      |
|  - Payload len   |
|  - Mask key      |
+------------------+
| STT Frame        | Variable
|  - Frame Header  |
|  - Payload       |
+------------------+
```

**Masking:** WebSocket requires client-to-server frames be masked (XOR with random key - RFC 6455 requirement, not STT crypto).

### TLS Support

**WebSocket over TLS** (WSS - like HTTPS):

```python
node = STTNode(
    node_id=b"Alice",
    transport='websocket',
    tls=True,  # Use WSS instead of WS
    tls_cert='/path/to/cert.pem',
    tls_key='/path/to/key.pem'
)
```

**Double encryption:**

- TLS encrypts WebSocket frames (transport layer)
- STC encrypts STT payloads (application layer)

**Why both?**

- TLS: Satisfies network policies (enterprises often require TLS)
- STC: End-to-end encryption (even if TLS terminated at proxy)

**Performance cost:** ~20-30% higher CPU (two encryption layers).

**Alternative:** Use WebSocket without TLS (STC provides encryption anyway), only if network policies allow.

### Proxy Support

**HTTP proxies** (common in corporate networks):

```python
node = STTNode(
    node_id=b"Alice",
    transport='websocket',
    proxy='http://proxy.company.com:8080',
    proxy_auth=('username', 'password')  # If required
)
```

**CONNECT method:**

```
Client → Proxy:
CONNECT peer.example.com:8080 HTTP/1.1

Proxy → Server (on behalf of client):
[Establishes TCP connection]

Proxy → Client:
HTTP/1.1 200 Connection Established

[Client sends WebSocket upgrade through tunnel]
```

**Works transparently** - STT doesn't care about proxy once tunnel established.

## Protocol Comparison

### UDP vs WebSocket Trade-offs

| Aspect | UDP | WebSocket |
|--------|-----|-----------|
| **Setup Latency** | None (connectionless) | ~20-100ms (TCP handshake + upgrade) |
| **Throughput** | Higher (~5-10% more) | Slightly lower (TCP overhead) |
| **Firewall Traversal** | Often blocked | Usually allowed (HTTP ports) |
| **NAT Traversal** | Difficult (needs STUN/TURN) | Easier (HTTP tunneling) |
| **Reliability** | None (STT adds) | TCP (redundant with STT) |
| **Overhead** | ~8 bytes/packet | ~22-54 bytes/packet |
| **Browser Support** | No (future with WebRTC data channels) | Yes (native WebSocket API) |

**Recommendation:**

- **UDP first** if direct connectivity (faster)
- **WebSocket fallback** if firewalls/NAT (connectivity)

### TCP Redundancy

**Problem:** WebSocket uses TCP, which already provides reliability

**STT also provides reliability** (retransmissions, ordering)

**Double work?** Yes, partially:

- TCP retransmits lost packets
- STT also detects/retransmits lost frames
- **Redundant** but necessary (STT needs transport independence)

**Consequence:**

- Slightly lower performance (double tracking)
- Longer recovery from packet loss (TCP timeout + STT timeout)

**Optimization:**

- Could disable STT retransmissions when using TCP transport (trust TCP)
- "Bare TCP" mode (no redundant reliability)
- Current: Both layers do reliability (safe but redundant)

## Transport Selection Strategy

### Manual Selection

**Current 0.2.0a0 (unreleased):** Must choose one transport manually.

### Hybrid Approach

**Use different transports for different peers:**

```python
# Alice's node supports both
node_alice = STTNode(node_id=b"Alice", transport='udp')
node_alice.start()

# Bob uses UDP (direct connectivity)
session_bob = await node_alice.connect(
    ('10.0.1.5', 8080),
    b"Bob",
    transport='udp'
)

# Carol uses WebSocket (behind firewall)
session_carol = await node_alice.connect(
    ('carol.example.com', 8080),
    b"Carol",
    transport='websocket'
)
```

**Not yet implemented** - current 0.2.0a0 (unreleased): one transport per node.

## Session Continuity Across Transports

**STT 0.2.0a0 includes cryptographic session continuity:**

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

**Continuity features:**

- **Transport migration**: Resume session when switching UDP → WebSocket (or vice versa)
- **IP address change**: WiFi → LTE transition without reconnecting
- **Device migration**: Same seeds = same session across devices
- **Zero-knowledge proofs**: Verify session identity without revealing seeds

Session identity is based on cryptographic seeds rather than network connection IDs.

**Allow custom transports:**

```python
# Future API (not yet implemented)
class CustomTransport(TransportInterface):
    def send_frame(self, frame: bytes, dest: Address):
        # Your custom transport logic
        pass
    
    def receive_frame(self) -> tuple[bytes, Address]:
        # Your custom transport logic
        pass

node = STTNode(
    node_id=b"Alice",
    transport_impl=CustomTransport()
)
```

**Use cases:**

- Bluetooth transport (local wireless)
- Serial/UART (embedded systems)
- Shared memory (same-machine IPC)
- Custom overlay networks

## Diagnostics and Monitoring

### Transport Statistics

```python
# Get transport stats
stats = node.get_transport_stats()

print(f"Packets sent: {stats.packets_sent}")
print(f"Packets received: {stats.packets_received}")
print(f"Bytes sent: {stats.bytes_sent}")
print(f"Bytes received: {stats.bytes_received}")
print(f"Packet loss rate: {stats.loss_rate * 100:.2f}%")
```

**Useful for:**

- Diagnosing network issues
- Monitoring performance
- Detecting congestion

### Packet Capture

**Use Wireshark** to inspect traffic:

**UDP:**

```
Filter: udp.port == 8080
```

**WebSocket:**

```
Filter: websocket
```

**What you'll see:**

- UDP: Encrypted STT frames (binary blobs)
- WebSocket: Encrypted STT frames inside WebSocket frames

**Cannot decrypt** (STC encrypted) - but can see:

- Packet timing
- Frame sizes
- Connection patterns

**Useful for debugging connectivity issues** (not content).

## Common Issues and Solutions

### UDP Packet Loss

**Problem:** High packet loss (>5%)

**Diagnosis:**

```python
stats = node.get_transport_stats()
print(f"Loss rate: {stats.loss_rate * 100:.2f}%")
```

**Solutions:**

1. **Check network quality** (WiFi interference, cable issues)
2. **Increase socket buffers** (`recv_buffer_size`, `send_buffer_size`)
3. **Reduce send rate** (slow down application)
4. **Switch to WebSocket** (TCP handles loss better)

### Firewall Blocking

**Problem:** Connection times out (no response)

**Diagnosis:**

```bash
# Test UDP reachability
nc -u -v peer_ip 8080

# Test WebSocket reachability
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://peer_ip:8080/
```

**Solutions:**

1. **Configure firewall rules** (allow port)
2. **Port forwarding** (if behind NAT)
3. **Switch to WebSocket** (use HTTP port 80/443)
4. **Use proxy** (HTTP proxy support with WebSocket)

### MTU Issues

**Problem:** Large frames fail to send

**Symptoms:**

- Works for small data
- Fails for large data (>1400 bytes)

**Diagnosis:**

```bash
# Test path MTU
ping -M do -s 1472 peer_ip  # Linux
ping -D -s 1472 peer_ip     # macOS
```

**Solutions:**

1. **Reduce max_frame_size** (avoid fragmentation)

   ```python
   stream = session.open_stream(max_frame_size=1400)
   ```

2. **Path MTU discovery** (automatic in future versions)
3. **Switch to WebSocket** (TCP handles fragmentation)

### WebSocket Connection Failures

**Problem:** WebSocket upgrade fails

**Diagnosis:**

```python
import websockets

async def test_websocket():
    async with websockets.connect('ws://peer_ip:8080') as ws:
        await ws.send('test')
        response = await ws.recv()
        print(response)

asyncio.run(test_websocket())
```

**Solutions:**

1. **Check TLS configuration** (if using WSS)
2. **Verify proxy settings** (correct proxy URL)
3. **Test basic HTTP connectivity** (curl http://peer_ip:8080)

## Best Practices

### Transport Selection

✅ **DO:**

- Use UDP for direct peer-to-peer (lowest latency)
- Use WebSocket through firewalls (connectivity)
- Test both transports in your environment
- Configure fallback (when available)

❌ **DON'T:**

- Assume UDP always works (firewalls block)
- Use WebSocket unnecessarily (extra overhead)
- Ignore MTU limits (causes fragmentation/loss)

### Configuration

✅ **DO:**

- Increase socket buffers for high-bandwidth (GB/s)
- Use TLS for WebSocket in hostile networks (defense in depth)
- Monitor transport stats (detect issues early)
- Configure timeouts appropriately (network conditions)

❌ **DON'T:**

- Use tiny buffers (causes packet loss)
- Double-encrypt if not needed (WSS + STC - CPU cost)
- Ignore loss rate (>5% indicates problem)
- Use same timeout everywhere (tune per use case)

### Network Optimization

✅ **DO:**

- Prioritize UDP packets (QoS on router/switch)
- Use wired connections for reliability (avoid WiFi)
- Monitor bandwidth usage (avoid congestion)
- Test under realistic network conditions

❌ **DON'T:**

- Saturate link (leave headroom - congestion control)
- Assume LAN performance on WAN (latency differs)
- Ignore jitter (variability in latency - affects real-time)

## Visual Summary

```
         STT Transport Layer Stack

+--------------------------------------------------+
|           Application Layer                      |
|  Your code using STT                            |
+--------------------------------------------------+
                       ↓
+--------------------------------------------------+
|             STT Session Layer                    |
|  Encryption, Multiplexing, Reliability          |
+--------------------------------------------------+
                       ↓
+--------------------------------------------------+
|           STT Frame Layer                        |
|  Frame encoding, Sequence numbers               |
+--------------------------------------------------+
                       ↓
            ┌──────────┴──────────┐
            ↓                     ↓
+------------------------+  +------------------------+
|  UDP Transport         |  | WebSocket Transport    |
|  - Raw datagrams       |  | - TCP connection       |
|  - Low overhead        |  | - HTTP upgrade         |
|  - Fast, unreliable    |  | - Firewall-friendly    |
+------------------------+  +------------------------+
            ↓                     ↓
+--------------------------------------------------+
|              IP Network Layer                    |
|  IPv4/IPv6 routing                              |
+--------------------------------------------------+
            ↓
+--------------------------------------------------+
|           Physical Network                       |
|  Ethernet, WiFi, Fiber, etc.                    |
+--------------------------------------------------+
```

## Testing Your Understanding

1. **Is UDP reliable by itself?**
   - No - STT adds reliability (retransmissions, ordering)

2. **Which transport has lower latency: UDP or WebSocket?**
   - UDP (no connection setup, less overhead)

3. **Can STT use both UDP and WebSocket simultaneously?**
   - Not in 0.2.0a0 (unreleased) (not implemented)

4. **Does WebSocket provide encryption?**
   - No (unless using WSS - WebSocket Secure with TLS), but STC encrypts STT payloads anyway

5. **Why would you use WebSocket if it's slower?**
   - Firewall traversal, NAT traversal, browser compatibility, proxy support

6. **Is TCP redundant with STT's reliability?**
   - Yes, partially (both provide retransmissions/ordering) - future versions may optimize

## Next Steps

- **Chapter 9**: Getting Started (practical setup, first program using transports)
- **Chapter 11**: Error Handling (transport-specific errors, recovery)
- **Chapter 12**: Performance and Optimization (tuning transport parameters)

**Key Takeaways:**

- UDP = default, fastest, direct connectivity required
- WebSocket = fallback, firewall-friendly, higher latency
- Both provide same STT features (transport is interchangeable)
- Choose based on network environment (firewalls, NAT, latency requirements)
- Future: QUIC, automatic fallback, pluggable transports
- Monitor transport stats to detect issues (loss rate, throughput)
