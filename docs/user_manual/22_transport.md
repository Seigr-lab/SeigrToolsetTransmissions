# Chapter 22: Transport Layer

**Version**: 0.2.0a0 (unreleased)  
**Components**: `UDPTransport`, `WebSocketTransport`  
**Test Coverage**: UDP 90%, WebSocket 84.63%

---

## Overview

The **transport layer** moves encrypted frames between nodes. STT supports two transports:

**UDPTransport** - Fast, unreliable datagrams  
**WebSocketTransport** - Reliable, bidirectional streams

Both transports:
- Send/receive opaque encrypted bytes
- Don't know frame contents (encryption happens before transport)
- Are **pluggable** (you can implement custom transports)

---

## Transport Agnosticism

Key principle: **Frames are encrypted BEFORE reaching transport**

```
┌──────────────────────────────────────┐
│ Application                          │
│   ↓ creates STTFrame                 │
│ Frame Layer                          │
│   ↓ encrypts with STC                │
│ [Encrypted Frame Bytes]              │
│   ↓ transport doesn't see plaintext  │
│ Transport (UDP or WebSocket)         │
│   ↓ sends encrypted bytes            │
│ Network                              │
└──────────────────────────────────────┘
```

**Result**: Network sees only encrypted binary blobs, regardless of transport used.

---

## UDP Transport

### When to Use UDP

✓ **Use UDP for**:
- Low latency critical applications
- Streaming data (audio/video)
- Real-time gaming
- IoT sensor data
- Situations where losing occasional packets is acceptable

✗ **Don't use UDP for**:
- File transfers requiring 100% reliability
- Transaction systems
- When every packet must arrive

### Creating UDP Transport

```python
from seigr_toolset_transmissions.transport import UDPTransport

# Create transport
udp = UDPTransport(
    host="0.0.0.0",  # Listen on all interfaces
    port=8080,        # Bind port (0 = random)
    stc_wrapper=node.stc,
    on_frame_received=handle_frame  # Callback
)

# Start
local_addr = await udp.start()
print(f"UDP listening on {local_addr}")
```

### UDP Configuration

```python
from seigr_toolset_transmissions.transport import UDPConfig

config = UDPConfig(
    bind_address="0.0.0.0",
    bind_port=8080,
    max_packet_size=1472,      # MTU (default safe for IPv4)
    receive_buffer_size=65536,  # 64 KB
    send_buffer_size=65536
)

udp = UDPTransport(config=config, ...)
```

### Sending Frames (UDP)

```python
# Serialize frame to bytes
frame_bytes = frame.to_bytes()

# Send to peer
await udp.send_frame(frame_bytes, ("peer.example.com", 8080))
```

### Receiving Frames (UDP)

```python
# Set callback during creation
async def handle_received_frame(frame: STTFrame, peer_addr: tuple):
    print(f"Received frame from {peer_addr}")
    # Process frame

udp = UDPTransport(on_frame_received=handle_received_frame, ...)

# Callback invoked automatically when frames arrive
```

### UDP Statistics

```python
stats = udp.get_statistics()

# Returns:
{
    'running': True,
    'local_addr': ('0.0.0.0', 8080),
    'uptime': 120.5,
    'bytes_sent': 102400,
    'bytes_received': 204800,
    'packets_sent': 50,
    'packets_received': 100,
    'packets_dropped': 2,
    'errors_send': 0,
    'errors_receive': 0
}
```

---

## WebSocket Transport

### When to Use WebSocket

✓ **Use WebSocket for**:
- Reliable delivery required
- Traversing NAT/firewalls (uses HTTP ports)
- Browser-based applications
- Long-lived connections with guaranteed delivery

✗ **Don't use WebSocket for**:
- Ultra-low latency (<1ms)
- Connectionless packet delivery
- Simple peer-to-peer without infrastructure

### Creating WebSocket Transport

```python
from seigr_toolset_transmissions.transport import WebSocketTransport

# Server mode
ws_server = WebSocketTransport(
    host="0.0.0.0",
    port=8081,
    stc_wrapper=node.stc,
    on_frame_received=handle_frame
)

await ws_server.start_server()

# Client mode
ws_client = WebSocketTransport(
    stc_wrapper=node.stc,
    on_frame_received=handle_frame
)

await ws_client.connect("ws://peer.example.com:8081")
```

### Sending Frames (WebSocket)

```python
# Serialize frame
frame_bytes = frame.to_bytes()

# Send (no address needed - connection already established)
await ws.send_frame(frame_bytes)
```

### Receiving Frames (WebSocket)

```python
# Same callback model as UDP
async def handle_frame(frame: STTFrame, peer_addr: tuple):
    print(f"Received via WebSocket from {peer_addr}")

ws = WebSocketTransport(on_frame_received=handle_frame, ...)
```

---

## Complete Example: Dual Transport

```python
import asyncio
from seigr_toolset_transmissions import STTNode

async def dual_transport_example():
    shared_seed = b"shared_secret_32bytes_minimum!"
    
    # Server with both UDP and WebSocket
    server = STTNode(
        node_seed=b"server" * 8,
        shared_seed=shared_seed,
        port=8080  # UDP
    )
    
    await server.start(server_mode=True)
    
    # Also enable WebSocket
    await server.start_websocket_server(port=8081)
    
    print("Server listening on:")
    print(f"  UDP: {server.udp_transport.local_addr}")
    print(f"  WebSocket: ws://localhost:8081")
    
    # Client can connect via UDP
    client_udp = STTNode(
        node_seed=b"client1" * 8,
        shared_seed=shared_seed,
        port=0
    )
    await client_udp.start()
    session_udp = await client_udp.connect_udp("localhost", 8080)
    print("Connected via UDP")
    
    # Or via WebSocket
    client_ws = STTNode(
        node_seed=b"client2" * 8,
        shared_seed=shared_seed,
        port=0
    )
    await client_ws.start()
    session_ws = await client_ws.connect_websocket("ws://localhost:8081")
    print("Connected via WebSocket")
    
    # Send via UDP
    await client_udp.send_to_sessions([session_udp.session_id], b"Via UDP")
    
    # Send via WebSocket
    await client_ws.send_to_sessions([session_ws.session_id], b"Via WS")
    
    await asyncio.sleep(1)
    
    # Cleanup
    await client_udp.stop()
    await client_ws.stop()
    await server.stop()

asyncio.run(dual_transport_example())
```

---

## MTU and Packet Size

### UDP MTU Limits

```python
# Default: 1472 bytes (safe for IPv4)
# = 1500 (Ethernet MTU) - 20 (IP header) - 8 (UDP header)

UDPConfig.max_packet_size = 1472

# Frames larger than MTU must be fragmented
# (handled automatically by Stream layer)
```

### Configuring MTU

```python
# For jumbo frames (if network supports)
config = UDPConfig(max_packet_size=8972)  # 9000 - 28

# For restrictive networks
config = UDPConfig(max_packet_size=512)

udp = UDPTransport(config=config, ...)
```

### WebSocket Packet Size

WebSocket has no MTU limit (uses TCP):

```python
# Can send arbitrarily large frames
huge_frame = STTFrame(payload=b"X" * 1_000_000)  # 1 MB

# WebSocket handles fragmentation automatically
await ws.send_frame(huge_frame.to_bytes())
```

---

## Transport Comparison

| Feature              | UDP              | WebSocket        |
|----------------------|------------------|------------------|
| **Reliability**      | Unreliable       | Reliable         |
| **Ordering**         | Not guaranteed   | Guaranteed       |
| **Latency**          | Very low (~1ms)  | Low (~5-10ms)    |
| **MTU**              | 1472 bytes       | Unlimited (TCP)  |
| **Firewall**         | Often blocked    | Rarely blocked   |
| **Connection**       | Connectionless   | Connection-based |
| **Overhead**         | 8 bytes (UDP)    | ~20 bytes (TCP)  |
| **Use case**         | Streaming        | Reliable data    |

---

## Common Patterns

### Automatic Reconnection (WebSocket)

```python
class ReconnectingWebSocket:
    def __init__(self, url, stc, on_frame):
        self.url = url
        self.stc = stc
        self.on_frame = on_frame
        self.ws = None
    
    async def connect_with_retry(self, max_retries=5):
        for attempt in range(max_retries):
            try:
                self.ws = WebSocketTransport(
                    stc_wrapper=self.stc,
                    on_frame_received=self.on_frame
                )
                await self.ws.connect(self.url)
                print("Connected!")
                return
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        raise ConnectionError("Failed to connect")

# Usage
ws = ReconnectingWebSocket("ws://peer:8081", node.stc, handle_frame)
await ws.connect_with_retry()
```

### Transport Failover

```python
async def send_with_failover(node, session_id, data):
    """Try UDP first, fallback to WebSocket"""
    try:
        # Attempt UDP (fast)
        await node.send_via_udp(session_id, data)
    except Exception as e:
        print(f"UDP failed: {e}, trying WebSocket...")
        # Fallback to WebSocket (reliable)
        await node.send_via_websocket(session_id, data)
```

### Bandwidth Limiting

```python
import time

class RateLimitedTransport:
    def __init__(self, transport, bytes_per_second):
        self.transport = transport
        self.bytes_per_second = bytes_per_second
        self.tokens = bytes_per_second
        self.last_refill = time.time()
    
    async def send_frame(self, frame_bytes, addr=None):
        # Refill tokens
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.bytes_per_second,
            self.tokens + (elapsed * self.bytes_per_second)
        )
        self.last_refill = now
        
        # Wait if not enough tokens
        if len(frame_bytes) > self.tokens:
            wait_time = (len(frame_bytes) - self.tokens) / self.bytes_per_second
            await asyncio.sleep(wait_time)
            self.tokens = 0
        else:
            self.tokens -= len(frame_bytes)
        
        # Send
        if addr:
            await self.transport.send_frame(frame_bytes, addr)
        else:
            await self.transport.send_frame(frame_bytes)

# Usage: Limit to 1 MB/s
limited = RateLimitedTransport(udp, bytes_per_second=1024*1024)
```

---

## Troubleshooting

### UDP Packets Not Arriving

**Causes**:
- Firewall blocking UDP port
- Router dropping packets
- Packet loss

**Solutions**:
```python
# 1. Check firewall
# Allow UDP on port 8080

# 2. Verify binding
stats = udp.get_statistics()
print(f"Listening on: {stats['local_addr']}")

# 3. Monitor drops
print(f"Dropped packets: {stats['packets_dropped']}")
```

### WebSocket Connection Fails

**Causes**:
- Server not running
- Wrong URL
- Network issue

**Solutions**:
```python
# 1. Verify server URL
await ws.connect("ws://localhost:8081")  # Not http://

# 2. Check server is listening
# Server side:
await ws_server.start_server()

# 3. Test with timeout
try:
    await asyncio.wait_for(ws.connect(url), timeout=10)
except asyncio.TimeoutError:
    print("Connection timeout!")
```

### "Address already in use"

**Problem**: Port already bound

**Solution**: Use port 0 for auto-assignment:
```python
udp = UDPTransport(port=0)  # Random available port
await udp.start()
print(f"Assigned port: {udp.local_addr[1]}")
```

---

## Performance Considerations

**UDP Performance**:
- Throughput: ~1 Gbps on gigabit network
- Latency: ~1ms (local network)
- CPU: Minimal (~1% per 100 Mbps)

**WebSocket Performance**:
- Throughput: ~500 Mbps (TCP overhead)
- Latency: ~5-10ms (TCP handshake + framing)
- CPU: ~2-3% per 100 Mbps

**Choosing Transport**:
- **Latency critical**: UDP
- **Reliability critical**: WebSocket
- **Firewall traversal**: WebSocket
- **Maximum throughput**: UDP

---

## Security Notes

**Transport Security**:
- Frames encrypted BEFORE transport sees them
- Transport just moves opaque bytes
- Network intermediaries can't decrypt

**UDP Security**:
- No built-in encryption (STT provides this)
- Vulnerable to IP spoofing (mitigated by handshake)

**WebSocket Security**:
- Use `wss://` for TLS (recommended)
- STT encryption still applies (defense in depth)

```python
# Secure WebSocket
await ws.connect("wss://peer.example.com:8081")  # TLS encrypted

# Frames are double-encrypted:
# 1. STC encryption (STT layer)
# 2. TLS encryption (WebSocket layer)
```

---

## Related Documentation

- **[Chapter 16: STTNode](16_sttnode.md)** - Uses transports
- **[Chapter 19: Frames](19_frames.md)** - What transports carry
- **[Chapter 20: Streams](20_streams.md)** - Fragmentation over transport
- **[API Reference](../api/API.md#transport)** - Complete API

---

**Document Version**: 0.2.0a0 (unreleased)  
**Last Updated**: November 25, 2025
