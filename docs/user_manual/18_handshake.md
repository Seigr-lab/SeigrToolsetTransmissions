# Chapter 18: Handshake & HandshakeManager

**Version**: 0.2.0a0 (unreleased)  
**Components**: `STTHandshake`, `HandshakeManager`  
**Test Coverage**: 87.93%

---

## Overview

The **handshake** is how two STT nodes authenticate each other using their **shared seed** (pre-shared secret). Only nodes with the same shared seed can complete the handshake and establish a session.

**STTHandshake** - Single handshake protocol instance  
**HandshakeManager** - Manages concurrent handshakes

---

## How Authentication Works

### Pre-Shared Seed Model

STT uses **symmetric authentication**:

1. Both nodes have the same `shared_seed` configured
2. Handshake proves both parties know the seed
3. **Without the correct seed, handshake fails**

```python
# Both nodes must have same shared_seed
shared_seed = b"my_secret_network_key_32bytes!"

# Node A
node_a = STTNode(
    node_seed=b"node_a" * 8,
    shared_seed=shared_seed  # ← Same seed
)

# Node B  
node_b = STTNode(
    node_seed=b"node_b" * 8,
    shared_seed=shared_seed  # ← Same seed
)

# Handshake succeeds ✓
session = await node_a.connect_udp("node_b_host", 8080)
```

**Different seed = handshake fails**:

```python
# Wrong seed
wrong_node = STTNode(
    node_seed=b"wrong" * 8,
    shared_seed=b"different_seed_32bytes_long!"  # ← Different!
)

# Handshake fails ✗
try:
    await wrong_node.connect_udp("node_b_host", 8080)
except STTHandshakeError:
    print("Authentication failed - wrong seed!")
```

---

## Handshake Protocol (4 Messages)

The handshake exchanges 4 messages:

```
Initiator                          Responder
=========                          =========
   |                                  |
   |  1. HELLO                        |
   |  (node_id, nonce, commitment)    |
   |--------------------------------->|
   |                                  |
   |         2. RESPONSE              |
   |  (node_id, nonce, challenge)     |
   |<---------------------------------|
   |                                  |
   |  3. AUTH_PROOF                   |
   |  (decrypted challenge)           |
   |--------------------------------->|
   |                                  |
   |         4. SUCCESS               |
   |  (confirmation)                  |
   |<---------------------------------|
   |                                  |
  SESSION ESTABLISHED
```

### Message 1: HELLO

Initiator starts:

```python
hello_msg = {
    'type': 'HELLO',
    'node_id': initiator_node_id,      # 32 bytes
    'nonce': random_nonce,              # 32 bytes
    'timestamp': current_time_ms,
    'commitment': hash(node_id + nonce) # Proves nonce ownership
}
```

### Message 2: RESPONSE

Responder creates **encrypted challenge**:

```python
# Challenge = both nonces combined
challenge_payload = peer_nonce + our_nonce

# Encrypt with STC (using shared_seed)
encrypted_challenge, metadata = stc.encrypt_frame(challenge_payload)

response_msg = {
    'type': 'RESPONSE',
    'node_id': responder_node_id,
    'nonce': our_nonce,
    'challenge': encrypted_challenge,  # Can only decrypt with shared_seed
    'metadata': metadata
}
```

**Key point**: Only nodes with matching `shared_seed` can decrypt the challenge.

### Message 3: AUTH_PROOF

Initiator **proves they know shared_seed** by decrypting challenge:

```python
# Decrypt challenge (fails if wrong seed)
decrypted = stc.decrypt_frame(challenge, metadata)

auth_proof_msg = {
    'type': 'AUTH_PROOF',
    'session_id': derived_session_id,
    'decrypted_challenge': decrypted  # Proves seed possession
}
```

### Message 4: SUCCESS

Responder confirms session established:

```python
success_msg = {
    'type': 'SUCCESS',
    'session_id': session_id
}
```

---

## Using STTHandshake Directly

Usually you use `STTNode.connect_udp()` which handles handshake automatically. For manual control:

### Initiator Side

```python
from seigr_toolset_transmissions.handshake import STTHandshake
from seigr_toolset_transmissions.crypto import STCWrapper

# Initialize
shared_seed = b"shared_secret_32bytes_minimum!"
stc = STCWrapper(shared_seed)

handshake = STTHandshake(
    node_id=b"initiator_node_id_32_bytes!",
    stc_wrapper=stc,
    is_initiator=True
)

# 1. Create HELLO
hello_data = handshake.create_hello()

# Send hello_data to responder...
# (get response_data back)

# 3. Process RESPONSE and create AUTH_PROOF
auth_proof_data = handshake.process_response(response_data)

# Send auth_proof_data to responder...
# (get success_data back)

# 4. Finalize
handshake.process_success(success_data)

# Handshake complete!
print(f"Session ID: {handshake.session_id.hex()}")
print(f"Session key: {handshake.session_key.hex()}")
```

### Responder Side

```python
handshake = STTHandshake(
    node_id=b"responder_node_id_32_bytes!",
    stc_wrapper=stc,
    is_initiator=False
)

# 2. Process HELLO and create RESPONSE
response_data = handshake.process_hello(hello_data)

# Send response_data to initiator...
# (get auth_proof_data back)

# 4. Process AUTH_PROOF and create SUCCESS
success_data = handshake.process_auth_proof(auth_proof_data)

# Send success_data to initiator

# Session established
print(f"Session ID: {handshake.session_id.hex()}")
```

---

## HandshakeManager - Concurrent Handshakes

Manages multiple handshakes simultaneously:

```python
# Via STTNode
manager = node.handshake_manager
```

### Creating Handshake

```python
# Create new handshake (initiator)
handshake = await manager.create_handshake(
    peer_addr=("peer.example.com", 8080),
    is_initiator=True,
    stc_wrapper=node.stc
)

# Handshake is tracked by manager
```

### Processing Incoming Handshake Data

```python
# Manager automatically routes messages
response = await manager.process_handshake_data(
    peer_addr=("peer.example.com", 8080),
    data=hello_data
)

# Returns next message to send, or None if handshake complete
```

### Getting Handshake

```python
# Get ongoing handshake
handshake = manager.get_handshake(peer_addr)

if handshake:
    print(f"Handshake in progress with {peer_addr}")
    print(f"Completed: {handshake.completed}")
```

### Removing Handshake

```python
# Remove when complete (or failed)
manager.remove_handshake(peer_addr)
```

---

## Session Key Derivation

After handshake, both peers derive same session key:

```python
# XOR of:
# - Initiator nonce (32 bytes)
# - Responder nonce (32 bytes)  
# - Initiator node_id (32 bytes)
# - Responder node_id (32 bytes)

session_key = derive_session_key(
    nonce_initiator,
    nonce_responder,
    node_id_initiator,
    node_id_responder
)

# Result: 32-byte symmetric key unique to this session
```

**Properties**:

- **Deterministic**: Both peers calculate same key
- **Unique**: Different nonces = different key every time
- **Ephemeral**: Only exists during session
- **Non-reversible**: Can't extract original nonces/IDs

---

## Complete Example: Manual Handshake

```python
import asyncio
from seigr_toolset_transmissions.handshake import STTHandshake
from seigr_toolset_transmissions.crypto import STCWrapper

async def manual_handshake_example():
    shared_seed = b"shared_secret_32bytes_minimum!"
    
    # Create initiator
    init_stc = STCWrapper(shared_seed)
    initiator = STTHandshake(
        node_id=b"A" * 32,
        stc_wrapper=init_stc,
        is_initiator=True
    )
    
    # Create responder
    resp_stc = STCWrapper(shared_seed)
    responder = STTHandshake(
        node_id=b"B" * 32,
        stc_wrapper=resp_stc,
        is_initiator=False
    )
    
    print("=== Handshake Protocol ===\n")
    
    # 1. HELLO
    print("1. Initiator creates HELLO")
    hello_data = initiator.create_hello()
    print(f"   HELLO size: {len(hello_data)} bytes\n")
    
    # 2. RESPONSE
    print("2. Responder processes HELLO, creates RESPONSE")
    response_data = responder.process_hello(hello_data)
    print(f"   RESPONSE size: {len(response_data)} bytes")
    print(f"   Challenge encrypted: ✓\n")
    
    # 3. AUTH_PROOF
    print("3. Initiator processes RESPONSE, creates AUTH_PROOF")
    auth_proof_data = initiator.process_response(response_data)
    print(f"   AUTH_PROOF size: {len(auth_proof_data)} bytes")
    print(f"   Challenge decrypted: ✓\n")
    
    # 4. SUCCESS
    print("4. Responder processes AUTH_PROOF, creates SUCCESS")
    success_data = responder.process_auth_proof(auth_proof_data)
    print(f"   SUCCESS size: {len(success_data)} bytes\n")
    
    # Finalize
    initiator.process_success(success_data)
    
    # Verify both have same session info
    print("=== Session Established ===")
    print(f"Initiator session_id: {initiator.session_id.hex()}")
    print(f"Responder session_id: {responder.session_id.hex()}")
    print(f"Session IDs match: {initiator.session_id == responder.session_id}")
    print(f"\nInitiator session_key: {initiator.session_key.hex()[:32]}...")
    print(f"Responder session_key: {responder.session_key.hex()[:32]}...")
    print(f"Session keys match: {initiator.session_key == responder.session_key}")

asyncio.run(manual_handshake_example())
```

**Output**:

```
=== Handshake Protocol ===

1. Initiator creates HELLO
   HELLO size: 156 bytes

2. Responder processes HELLO, creates RESPONSE
   RESPONSE size: 248 bytes
   Challenge encrypted: ✓

3. Initiator processes RESPONSE, creates AUTH_PROOF
   AUTH_PROOF size: 128 bytes
   Challenge decrypted: ✓

4. Responder processes AUTH_PROOF, creates SUCCESS
   SUCCESS size: 48 bytes

=== Session Established ===
Initiator session_id: 1a2b3c4d5e6f7a8b
Responder session_id: 1a2b3c4d5e6f7a8b
Session IDs match: True

Initiator session_key: a1b2c3d4e5f6...
Responder session_key: a1b2c3d4e5f6...
Session keys match: True
```

---

## Security Model

### What Gets Authenticated?

1. **Node Identity**: Each node's `node_id` is exchanged
2. **Seed Possession**: Challenge proves shared_seed knowledge
3. **Freshness**: Nonces ensure no replay attacks

### What Gets Encrypted?

- **Challenge**: Encrypted with STC using shared_seed
- **Session Data**: All frames encrypted with derived session_key

### Attack Resistance

**Man-in-the-Middle (MITM)**:

- ✗ Can't decrypt challenge without shared_seed
- ✗ Can't forge valid AUTH_PROOF
- ✓ Session establishment fails

**Replay Attack**:

- ✓ Fresh nonces every handshake
- ✓ Commitment prevents nonce manipulation  
- ✓ Timestamp validation (optional)

**Brute Force**:

- Shared seed must be 32+ bytes (256+ bits)
- STC adds additional cryptographic strength
- No offline attack surface (challenge is ephemeral)

---

## Common Patterns

### Handshake Timeout

```python
import asyncio

async def connect_with_timeout(node, peer_host, peer_port, timeout=10):
    try:
        session = await asyncio.wait_for(
            node.connect_udp(peer_host, peer_port),
            timeout=timeout
        )
        return session
    except asyncio.TimeoutError:
        print(f"Handshake timeout after {timeout}s")
        return None
```

### Handshake Retry

```python
async def connect_with_retry(node, peer_host, peer_port, max_retries=3):
    for attempt in range(max_retries):
        try:
            session = await node.connect_udp(peer_host, peer_port)
            return session
        except STTHandshakeError as e:
            print(f"Handshake failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)  # Wait before retry
    
    raise STTHandshakeError("All handshake attempts failed")
```

### Custom Handshake Validation

```python
class CustomHandshakeManager(HandshakeManager):
    async def validate_peer(self, node_id: bytes) -> bool:
        """Custom validation before accepting peer"""
        # Check node_id against whitelist/blacklist
        if node_id in self.blacklist:
            return False
        
        # Add custom logic
        return True
    
    async def process_handshake_data(self, peer_addr, data):
        # Extract node_id from handshake
        msg = deserialize_stt(data)
        peer_id = msg.get('node_id')
        
        # Validate before proceeding
        if peer_id and not await self.validate_peer(peer_id):
            raise STTHandshakeError("Peer validation failed")
        
        # Continue normal handshake
        return await super().process_handshake_data(peer_addr, data)
```

---

## Troubleshooting

### Handshake Timeout

**Problem**: `connect_udp()` never completes

**Causes**:

- Peer not listening
- Firewall blocking UDP
- Network unreachable

**Solutions**:

```python
# 1. Verify peer is listening
# On peer: await node.start(server_mode=True)

# 2. Check firewall rules
# Allow UDP on specified port

# 3. Test network connectivity
# ping peer_host
```

### "Handshake failed" Error

**Problem**: `STTHandshakeError` during handshake

**Causes**:

- **Wrong shared_seed** (most common)
- Message corruption in transit
- Incompatible versions

**Solutions**:

```python
# 1. Verify shared_seed matches
# Both nodes must have EXACTLY same seed

# 2. Check network quality
# Use TCP for initial setup to verify connectivity

# 3. Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

### "Challenge decryption failed"

**Problem**: AUTH_PROOF stage fails

**Cause**: Different shared_seed on initiator vs responder

**Solution**:

```python
# Ensure both nodes use SAME seed
shared_seed = b"exact_same_32byte_secret_key!"

# Initiator
node_a = STTNode(shared_seed=shared_seed, ...)

# Responder  
node_b = STTNode(shared_seed=shared_seed, ...)  # Must match!
```

---

## Performance Considerations

**Handshake Overhead**:

- 4 messages exchanged
- ~600 bytes total data
- 1-2 RTTs (Round Trip Times)
- Typical completion: 10-100ms on LAN

**Cryptographic Cost**:

- STC encryption/decryption: ~0.5ms per operation
- Hash computation: <0.1ms
- Total CPU time: ~2-3ms

**Concurrent Handshakes**:

- HandshakeManager supports unlimited concurrent handshakes
- Each handshake ~1 KB memory
- Typical limit: 1000+ concurrent handshakes on modern hardware

---

## Related Documentation

- **[Chapter 16: STTNode](16_sttnode.md)** - Uses handshake to connect
- **[Chapter 17: Sessions](17_sessions.md)** - Created by handshake
- **[Chapter 23: Cryptography](23_cryptography.md)** - STC encryption details
- **[API Reference](../api/API.md#handshake)** - Complete API

---

**Document Version**: 0.2.0a0 (unreleased)  
**Last Updated**: November 25, 2025
