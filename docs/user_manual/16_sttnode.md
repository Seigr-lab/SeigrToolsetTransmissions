# Chapter 16: STTNode - Main Runtime

**Version**: 0.2.0a0 (unreleased)  
**Component**: `seigr_toolset_transmissions.core.STTNode`  
**Test Coverage**: 85.56%

---

## Overview

**STTNode** is the main runtime that coordinates all STT components. It's your entry point to the entire STT system - when you create an `STTNode`, you get a fully functional secure transport system.

Think of STTNode as the conductor of an orchestra - it doesn't play music itself, but coordinates all the musicians (components) to create the final performance (secure binary transport).

---

## What STTNode Does

STTNode manages:

1. **Handshakes** - Authenticating new peers
2. **Sessions** - Tracking active connections
3. **Streams** - Multiplexed data channels
4. **Transports** - UDP and WebSocket networking
5. **Storage** - Chamber for encrypted data
6. **Routing** - Directing frames to correct handlers

**You interact with STTNode** - it coordinates everything else behind the scenes.

---

## Basic Usage

### Creating a Node

```python
from seigr_toolset_transmissions import STTNode

# Create node with pre-shared seeds
node = STTNode(
    node_seed=b"my_node_secret_32bytes_minimum!",  # Node-specific secret
    shared_seed=b"shared_secret_32bytes_minimum!", # Pre-shared with peers
    host="0.0.0.0",                                # Listen address
    port=8080                                      # UDP port (0 = random)
)
```

**Parameters**:

- `node_seed` (bytes): Your node's unique secret (32+ bytes) - used for identity and Chamber encryption
- `shared_seed` (bytes): Pre-shared secret (32+ bytes) - must match peer's shared_seed for handshake to succeed
- `host` (str): IP address to bind (default: `"0.0.0.0"` = all interfaces)
- `port` (int): UDP port to listen on (default: `0` = random available port)
- `chamber_path` (Optional[Path]): Storage location (default: `~/.seigr/chambers/{node_id}`)

---

## Starting the Node

### Server Mode (Accept Incoming Connections)

```python
# Start in server mode - automatically accepts handshakes from authorized peers
local_addr = await node.start(server_mode=True)
print(f"Node listening on {local_addr[0]}:{local_addr[1]}")

# Node will now:
# 1. Listen for incoming UDP packets
# 2. Accept handshake requests from peers with matching shared_seed
# 3. Automatically create sessions when handshakes complete
```

### Client Mode (Outgoing Only)

```python
# Start without accepting incoming connections
await node.start(server_mode=False)

# You can still initiate outgoing connections
session = await node.connect_udp("peer.example.com", 8080)
```

### Controlling Accept Mode Dynamically

```python
# Enable accepting connections after starting
node.enable_accept_connections()

# Disable accepting connections
node.disable_accept_connections()
```

---

## Connecting to Peers

### UDP Connection

```python
# Connect to peer via UDP
session = await node.connect_udp(
    peer_host="192.168.1.100",
    peer_port=8080
)

# Handshake happens automatically:
# 1. HELLO sent to peer
# 2. RESPONSE received and verified
# 3. AUTH_PROOF sent
# 4. FINAL received - session established

print(f"Session ID: {session.session_id.hex()}")
print(f"Peer Node ID: {session.peer_node_id.hex()}")
```

**What happens during `connect_udp`**:

1. Node creates `STTHandshake` instance
2. Sends HELLO message with nonce and commitment
3. Receives RESPONSE with encrypted challenge
4. Decrypts challenge (proves we have matching `shared_seed`)
5. Sends AUTH_PROOF with session_id
6. Receives FINAL confirmation
7. Creates `STTSession` and returns it to you

**If handshake fails**:

- Different `shared_seed` → Decryption fails → `STTException` raised
- Network timeout → `STTException` raised
- Invalid response → `STTException` raised

---

## Sending Data

### Send to All Sessions (Broadcast)

```python
# Broadcast message to all connected peers
await node.send_to_all(
    data=b"Hello everyone!",
    stream_id=0  # Default stream
)
```

**Use case**: Server broadcasting state updates to all clients.

### Send to Specific Sessions (Multicast)

```python
# Send to selected peers only
session_ids = [session1.session_id, session2.session_id]
await node.send_to_sessions(
    session_ids=session_ids,
    data=b"Private group message",
    stream_id=0
)
```

**Use case**: Chat room sending message to room participants only.

---

## Receiving Data

### Receive from Any Session

```python
# Receive packets from any connected peer
async for packet in node.receive():
    # packet is ReceivedPacket dataclass with:
    # - session_id: bytes (which session sent this)
    # - stream_id: int (which stream)
    # - data: bytes (decrypted payload)
    
    print(f"From {packet.session_id.hex()}: {packet.data}")
    
    # You can look up the session if needed
    session = node.session_manager.get_session(packet.session_id)
    if session:
        print(f"From peer: {session.peer_node_id.hex()}")
```

**Key points**:

- `receive()` is an async iterator - use `async for`
- Packets arrive as they're received (not ordered across sessions)
- Data is already decrypted - ready to use
- Blocks until data available (or node stops)

---

## Node Statistics

```python
stats = node.get_stats()

print(f"Node ID: {stats['node_id']}")
print(f"Running: {stats['running']}")
print(f"Server mode: {stats['server_mode']}")
print(f"Accepting connections: {stats['accepting_connections']}")

# Transport stats
udp_stats = stats['udp_transport']
print(f"Bytes sent: {udp_stats['bytes_sent']}")
print(f"Bytes received: {udp_stats['bytes_received']}")
print(f"Packets sent: {udp_stats['packets_sent']}")
print(f"Errors: {udp_stats['errors_send']}")

# Session stats
session_stats = stats['sessions']
print(f"Total sessions: {session_stats['total']}")
print(f"Active sessions: {session_stats['active']}")

# WebSocket connections
print(f"WebSocket connections: {stats['websocket_connections']}")
```

---

## Stopping the Node

```python
# Graceful shutdown
await node.stop()

# This will:
# 1. Stop accepting new connections
# 2. Close all active sessions
# 3. Close all WebSocket connections
# 4. Stop UDP transport
# 5. Cancel background tasks
# 6. Clean up resources
```

**Always call `stop()`** when done - ensures clean shutdown and no resource leaks.

---

## Internal Components (How STTNode Works)

### What STTNode Manages Internally

```python
# These are created automatically when you create STTNode:

node.stc                 # STCWrapper - Cryptography
node.node_id             # bytes - Generated from node_seed
node.chamber             # Chamber - Encrypted storage
node.session_manager     # SessionManager - Tracks sessions
node.handshake_manager   # HandshakeManager - Handles authentication
node.udp_transport       # UDPTransport - UDP networking
node.ws_connections      # dict - WebSocket connections
```

You **rarely access these directly** - STTNode handles coordination.

### Frame Routing

When a frame arrives, STTNode routes it:

```python
# Internal flow (simplified):

def _handle_frame_received(frame, peer_addr):
    if frame.frame_type == HANDSHAKE:
        # Route to handshake manager
        await handshake_manager.handle_incoming(peer_addr, frame.payload)
        
    elif frame.frame_type == DATA:
        # Route to session
        session = session_manager.get_session(frame.session_id)
        
        # Decrypt
        frame.decrypt_payload(self.stc)
        
        # Add to receive queue
        await self._recv_queue.put(ReceivedPacket(
            session_id=frame.session_id,
            stream_id=frame.stream_id,
            data=frame.payload
        ))
```

**You don't write this code** - it happens automatically when frames arrive.

---

## Complete Example: Two Nodes Communicating

```python
import asyncio
from seigr_toolset_transmissions import STTNode

async def run_server():
    """Server: Accepts connections and echoes data"""
    shared_seed = b"shared_secret_32bytes_minimum!"
    
    server = STTNode(
        node_seed=b"server_seed_32bytes_minimum!",
        shared_seed=shared_seed,
        host="0.0.0.0",
        port=8080
    )
    
    # Start in server mode
    await server.start(server_mode=True)
    print(f"Server started: {server.node_id.hex()[:16]}...")
    
    # Echo received data back
    async for packet in server.receive():
        print(f"Server received: {packet.data}")
        
        # Echo back to sender
        await server.send_to_sessions(
            session_ids=[packet.session_id],
            data=b"ECHO: " + packet.data
        )

async def run_client():
    """Client: Connects and sends data"""
    shared_seed = b"shared_secret_32bytes_minimum!"
    
    client = STTNode(
        node_seed=b"client_seed_32bytes_minimum!",
        shared_seed=shared_seed,
        host="0.0.0.0",
        port=0  # Random port
    )
    
    # Start (no server mode needed for client)
    await client.start()
    print(f"Client started: {client.node_id.hex()[:16]}...")
    
    # Connect to server
    session = await client.connect_udp("localhost", 8080)
    print(f"Connected! Session: {session.session_id.hex()}")
    
    # Send message
    await client.send_to_sessions(
        session_ids=[session.session_id],
        data=b"Hello from client!"
    )
    
    # Receive echo
    async for packet in client.receive():
        print(f"Client received: {packet.data}")
        break  # Exit after first echo
    
    await client.stop()

# Run both
async def main():
    # Start server in background
    server_task = asyncio.create_task(run_server())
    
    # Give server time to start
    await asyncio.sleep(0.5)
    
    # Run client
    await run_client()
    
    # Stop server
    server_task.cancel()

asyncio.run(main())
```

**Output**:

```
Server started: a3f2e1d0c4b5...
Client started: 9c8b7a6d5e4f...
Connected! Session: 1a2b3c4d5e6f7a8b
Server received: b'Hello from client!'
Client received: b'ECHO: Hello from client!'
```

---

## Advanced Features

### Custom Chamber Path

```python
from pathlib import Path

node = STTNode(
    node_seed=b"seed" * 8,
    shared_seed=b"shared" * 8,
    chamber_path=Path("/custom/storage/location")
)
```

Chamber will store encrypted data at specified location instead of default `~/.seigr/chambers/`.

### Accessing Internal Components

```python
# Get session manager
sessions = node.session_manager.get_active_sessions()
print(f"{len(sessions)} active sessions")

# Get specific session
session = node.session_manager.get_session(session_id)

# Check handshakes in progress
handshakes = node.handshake_manager.active_handshakes
print(f"{len(handshakes)} handshakes in progress")

# Access chamber storage
data_hash = await node.chamber.put(b"Important data")
retrieved = await node.chamber.get(data_hash)
```

---

## Common Patterns

### Server Pattern (Always Listening)

```python
async def run_server():
    node = STTNode(node_seed=seed1, shared_seed=shared, port=8080)
    await node.start(server_mode=True)
    
    # Process incoming data forever
    async for packet in node.receive():
        await handle_packet(packet)
```

### Client Pattern (Connect and Communicate)

```python
async def run_client():
    node = STTNode(node_seed=seed2, shared_seed=shared, port=0)
    await node.start()
    
    # Connect to server
    session = await node.connect_udp("server.example.com", 8080)
    
    # Send/receive
    await node.send_to_sessions([session.session_id], data)
    async for packet in node.receive():
        process(packet.data)
```

### Broadcast Pattern (One-to-Many)

```python
async def broadcast_server():
    node = STTNode(node_seed=seed, shared_seed=shared, port=8080)
    await node.start(server_mode=True)
    
    # Broadcast updates to all clients
    while True:
        update_data = generate_update()
        await node.send_to_all(update_data)
        await asyncio.sleep(1.0)
```

---

## Troubleshooting

### "Handshake failed" Errors

**Cause**: Different `shared_seed` between peers.

**Solution**: Ensure both nodes use identical `shared_seed`:

```python
# Both nodes MUST use this exact seed
shared_seed = b"shared_secret_32bytes_minimum!"
```

### "No active sessions" Warning

**Cause**: Calling `send_to_all()` before any peers connect.

**Solution**: Check session count first:

```python
sessions = node.session_manager.get_active_sessions()
if sessions:
    await node.send_to_all(data)
else:
    print("No peers connected yet")
```

### Port Already in Use

**Cause**: Another process using the port.

**Solution**: Use port 0 for auto-assignment:

```python
node = STTNode(node_seed=seed, shared_seed=shared, port=0)
local_addr = await node.start()
print(f"Assigned port: {local_addr[1]}")
```

---

## Performance Considerations

### Memory Usage

Each STTNode uses approximately:

- Base: ~10 MB (Python runtime, imports)
- Per session: ~100 KB (buffers, state)
- Per active stream: ~50 KB (ordering buffers)

**Example**: Node with 100 sessions and 3 streams each:

```
10 MB + (100 × 100 KB) + (300 × 50 KB) = 35 MB
```

### CPU Usage

- **Idle**: < 1% CPU
- **Handshake**: ~5% CPU per handshake (STC encryption)
- **Data transfer**: Scales with throughput (encryption overhead)

### Network Usage

- **Overhead**: ~60 bytes per frame (header + crypto metadata)
- **Heartbeats**: 1 frame per session every 30 seconds (configurable)
- **Handshake**: 4 frames total (~2 KB including crypto metadata)

---

## Security Notes

### Node Identity

Each node generates ephemeral ID from `node_seed`:

```python
node_id = stc.generate_node_id(b"stt_node_identity")
```

**Non-deterministic**: Same `node_seed` produces different `node_id` each run (privacy).

### Shared Seed Distribution

`shared_seed` MUST be distributed securely:

- ✅ QR code (offline)
- ✅ Secure messaging (encrypted channel)
- ✅ Physical handoff (USB drive)
- ❌ Email (unencrypted)
- ❌ Public GitHub (anyone can see)

### Session Security

All session data encrypted with STC:

- Frame payloads encrypted before sending
- Only peers with matching `shared_seed` can decrypt
- Network sees random encrypted bytes

---

## Related Documentation

- **[Chapter 17: Sessions & SessionManager](17_sessions.md)** - Session management details
- **[Chapter 18: Handshake](18_handshake.md)** - Authentication protocol
- **[Chapter 22: Transport Layer](22_transport.md)** - UDP and WebSocket details
- **[API Reference](../api/API.md#sttnode)** - Complete API documentation

---

## Next Steps

Now that you understand STTNode, learn about:

- **Sessions**: How connections are managed → [Chapter 17](17_sessions.md)
- **Handshake**: How authentication works → [Chapter 18](18_handshake.md)
- **Frames**: Binary protocol details → [Chapter 19](19_frames.md)

---

**Document Version**: 0.2.0a0 (unreleased)  
**Last Updated**: November 25, 2025
