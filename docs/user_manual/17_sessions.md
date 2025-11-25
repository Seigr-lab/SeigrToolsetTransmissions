# Chapter 17: Sessions & SessionManager

**Version**: 0.2.0a0 (unreleased)  
**Components**: `STTSession`, `SessionManager`  
**Test Coverage**: STTSession 100%, SessionManager 100%

---

## Overview

A **session** represents a connection between two STT nodes. Think of it like a phone call - once established, both parties can communicate securely until one hangs up.

**STTSession** tracks a single connection.  
**SessionManager** manages multiple connections simultaneously.

---

## STTSession - Single Connection

### What is a Session?

A session is created after a successful handshake and provides:

- Unique session ID (8 bytes)
- Encryption key for all data
- State tracking (active, closing, closed)
- Statistics (bytes sent/received, errors)
- Key rotation for forward secrecy

### Creating a Session

Sessions are **created automatically** during handshake:

```python
# You don't manually create sessions - handshake does it
session = await node.connect_udp("peer.example.com", 8080)

# Session is ready to use
print(f"Session ID: {session.session_id.hex()}")
```

### Session Properties

```python
# Identity
session.session_id        # bytes (8 bytes) - Unique identifier
session.peer_node_id      # bytes (32 bytes) - Peer's node ID

# Cryptography  
session.session_key       # bytes (32 bytes) - Symmetric encryption key
session.key_version       # int - Current key version (for rotation)

# State
session.state             # int - Session state (see below)
session.capabilities      # int - Peer capabilities (future use)

# Timestamps
session.created_at        # float - Unix timestamp when created
session.last_active       # float - Last activity timestamp
session.last_key_rotation # float - When key was last rotated

# Transport (added by STTNode)
session.peer_addr         # tuple - (ip, port) for routing
session.transport_type    # str - 'udp' or 'websocket'
```

### Session States

```python
from seigr_toolset_transmissions.utils.constants import (
    STT_SESSION_STATE_HANDSHAKE,  # 0x00 - Authenticating
    STT_SESSION_STATE_ACTIVE,     # 0x01 - Ready for data
    STT_SESSION_STATE_CLOSING,    # 0x02 - Graceful shutdown
    STT_SESSION_STATE_CLOSED      # 0x03 - Terminated
)

# Check state
if session.state == STT_SESSION_STATE_ACTIVE:
    print("Session ready!")

# Helper methods
if session.is_active():
    print("Can send/receive data")
```

### Session Statistics

```python
stats = session.get_statistics()

# Returns dict with:
{
    'session_id': '1a2b3c4d5e6f7a8b',
    'peer_node_id': 'a1b2c3...',
    'state': 1,  # ACTIVE
    'created_at': 1700000000.0,
    'uptime': 120.5,  # seconds
    'bytes_sent': 102400,
    'bytes_received': 204800,
    'packets_sent': 50,
    'packets_received': 100,
    'send_errors': 0,
    'receive_errors': 0
}
```

### Recording Traffic

STTNode automatically records traffic, but you can do it manually:

```python
# Record sent data
session.record_frame_sent(payload_size=1024)

# Record received data  
session.record_frame_received(payload_size=2048)

# Record errors
session.record_send_error()
session.record_receive_error()
```

### Key Rotation (Forward Secrecy)

Rotate the session key to ensure old encrypted data can't be decrypted if current key compromised:

```python
# Rotate to new key
new_key = await session.rotate_key()

# Session key updated
print(f"Key version: {session.key_version}")  # Incremented
print(f"Last rotation: {session.last_key_rotation}")

# Old ciphertexts can't be decrypted with new key
```

**When to rotate**:

- Periodically (e.g., every hour)
- After transmitting sensitive data
- If you suspect key compromise

---

## SessionManager - Multiple Connections

### What Does SessionManager Do?

Manages multiple active sessions:

- Creates and tracks sessions
- Looks up sessions by ID
- Closes sessions gracefully  
- Provides aggregate statistics

### Accessing SessionManager

```python
# Via STTNode
manager = node.session_manager

# SessionManager is automatically created when you create STTNode
```

### Creating Sessions

Usually done automatically by handshake, but you can create manually:

```python
session = await manager.create_session(
    session_id=b"12345678",  # 8 bytes
    peer_node_id=peer_id,    # 32 bytes
    capabilities=0            # Peer capabilities
)

# Session added to manager's tracking
```

### Looking Up Sessions

```python
# Get session by ID
session = manager.get_session(session_id)

if session:
    print(f"Found session with peer {session.peer_node_id.hex()}")
else:
    print("Session not found")

# Check if session exists
if manager.has_session(session_id):
    print("Session exists")
```

### Getting All Sessions

```python
# Get all active sessions
active_sessions = manager.get_active_sessions()

print(f"Active sessions: {len(active_sessions)}")
for session in active_sessions:
    print(f"  {session.session_id.hex()} - {session.peer_node_id.hex()[:16]}...")
```

### Closing Sessions

```python
# Close specific session
await manager.close_session(session_id)

# Close all sessions (called by node.stop())
await manager.close_all_sessions()
```

### Session Count

```python
# Get total session count (including closed)
total = manager.get_session_count()
print(f"Total sessions: {total}")

# Get only active count
active = len(manager.get_active_sessions())
print(f"Active: {active}")
```

### Manager Statistics

```python
stats = manager.get_stats()

# Returns dict:
{
    'total': 10,      # Total sessions created
    'active': 5,      # Currently active
    'closing': 1,     # Gracefully closing
    'closed': 4       # Terminated
}
```

---

## Complete Example: Session Lifecycle

```python
import asyncio
from seigr_toolset_transmissions import STTNode

async def session_lifecycle():
    # Create nodes
    shared_seed = b"shared_secret_32bytes_minimum!"
    
    server = STTNode(
        node_seed=b"server" * 8,
        shared_seed=shared_seed,
        port=8080
    )
    await server.start(server_mode=True)
    
    client = STTNode(
        node_seed=b"client" * 8,
        shared_seed=shared_seed,
        port=0
    )
    await client.start()
    
    # Connect - creates session
    print("1. Creating session...")
    session = await client.connect_udp("localhost", 8080)
    print(f"   Session ID: {session.session_id.hex()}")
    print(f"   State: {session.state} (ACTIVE)")
    
    # Use session
    print("\n2. Using session...")
    await client.send_to_sessions([session.session_id], b"Test data")
    
    # Check statistics
    print("\n3. Session stats:")
    stats = session.get_statistics()
    print(f"   Bytes sent: {stats['bytes_sent']}")
    print(f"   Uptime: {stats['uptime']:.2f}s")
    
    # Rotate key
    print("\n4. Rotating key...")
    old_version = session.key_version
    await session.rotate_key()
    print(f"   Key version: {old_version} → {session.key_version}")
    
    # Check manager
    print("\n5. Manager stats:")
    mgr_stats = client.session_manager.get_stats()
    print(f"   Total sessions: {mgr_stats['total']}")
    print(f"   Active: {mgr_stats['active']}")
    
    # Close session
    print("\n6. Closing session...")
    await client.session_manager.close_session(session.session_id)
    print(f"   State: {session.state} (CLOSED)")
    
    # Cleanup
    await client.stop()
    await server.stop()

asyncio.run(session_lifecycle())
```

---

## Session Security

### Session Keys

Each session has unique encryption key derived during handshake:

```python
# Derived from handshake nonces + node IDs
session_key = XOR(nonce_initiator, nonce_responder, node_id_i, node_id_r)

# Used for all frame encryption in this session
```

**Properties**:

- **Unique**: Different for every session
- **Symmetric**: Both peers have same key
- **Ephemeral**: Exists only while session active
- **Rotatable**: Can be changed for forward secrecy

### Session ID Generation

Session ID created during handshake:

```python
# XOR of nonces and node IDs (8 bytes)
session_id = derive_session_id(
    nonce_initiator,
    nonce_responder, 
    node_id_initiator,
    node_id_responder
)
```

**Why XOR?**:

- Deterministic (both peers calculate same ID)
- Non-reversible (can't extract nonces/IDs)
- Unique (collision probability negligible)

---

## Common Patterns

### Session Pool Pattern

```python
class SessionPool:
    def __init__(self, node):
        self.node = node
    
    async def get_or_create(self, peer_host, peer_port):
        # Check existing sessions
        sessions = self.node.session_manager.get_active_sessions()
        
        for session in sessions:
            if hasattr(session, 'peer_addr'):
                if session.peer_addr == (peer_host, peer_port):
                    return session
        
        # Create new session
        return await self.node.connect_udp(peer_host, peer_port)
```

### Session Health Monitoring

```python
async def monitor_sessions(node):
    while True:
        sessions = node.session_manager.get_active_sessions()
        
        for session in sessions:
            # Check if stale
            idle_time = time.time() - session.last_active
            
            if idle_time > 300:  # 5 minutes
                print(f"Session {session.session_id.hex()} is stale")
                await node.session_manager.close_session(session.session_id)
        
        await asyncio.sleep(60)  # Check every minute
```

### Periodic Key Rotation

```python
async def rotate_keys_periodically(node, interval=3600):
    """Rotate all session keys every hour"""
    while True:
        await asyncio.sleep(interval)
        
        sessions = node.session_manager.get_active_sessions()
        for session in sessions:
            await session.rotate_key()
            print(f"Rotated key for {session.session_id.hex()}")
```

---

## Troubleshooting

### Session Not Found

**Problem**: `manager.get_session(session_id)` returns `None`

**Causes**:

- Session already closed
- Wrong session_id (typo in bytes)
- Session created on different node

**Solution**: Check session exists before using:

```python
session = manager.get_session(session_id)
if session and session.is_active():
    # Use session
    pass
else:
    # Reconnect or handle error
    pass
```

### Session State Mismatch

**Problem**: Session shows ACTIVE but can't send data

**Cause**: Transport disconnected but session not updated

**Solution**: Check both session state and transport:

```python
if session.is_active() and node.udp_transport.is_running:
    await send_data(session)
```

---

## Related Documentation

- **[Chapter 16: STTNode](16_sttnode.md)** - Main runtime
- **[Chapter 18: Handshake](18_handshake.md)** - How sessions are created
- **[Chapter 20: Streams](20_streams.md)** - Multiplexed channels within sessions
- **[API Reference](../api/API.md#session-management)** - Complete API

---

**Document Version**: 0.2.0a0 (unreleased)  
**Last Updated**: November 25, 2025
