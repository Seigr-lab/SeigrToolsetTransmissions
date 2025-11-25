# Chapter 23: Cryptography (STCWrapper)

**Version**: 0.2.0a0 (unreleased)  
**Component**: `STCWrapper`  
**Test Coverage**: 98.78%  
**Cryptographic Engine**: Seigr Toolset Crypto v0.4.1

---

## Overview

**STCWrapper** integrates **STC (Seigr Tree Codec)** cryptography into STT. All encryption, key derivation, and hashing use STC's adaptive, privacy-preserving algorithms.

**What STCWrapper Does**:

- Encrypt/decrypt frames with AEAD-like authentication
- Derive session keys from handshake data
- Generate node identities (privacy-preserving)
- Hash data with non-deterministic PHE (Probabilistic Hash Engine)
- Create streaming contexts for efficient bulk encryption

---

## Modern Crypto Design

STC uses **modern cryptography** principles:

```
Traditional Crypto       STC (Modern)
─────────────────       ────────────
Deterministic hash  →   Non-deterministic PHE
Static keys         →   Adaptive key morphing
Single algorithm    →   Multi-layer encryption
Hash collisions     →   Privacy by randomization
```

**Key Difference**: STC hashes are **not deterministic** - same input produces different output each time. This is intentional for privacy.

---

## Creating STCWrapper

```python
from seigr_toolset_transmissions.crypto import STCWrapper

# Initialize with node seed
stc = STCWrapper(node_seed=b"your_node_seed_32bytes_minimum")

# Each instance has isolated context
# - Own STC context
# - Own stream cache
# - Independent state
```

---

## Frame Encryption

### Encrypting a Frame

```python
# Prepare data
payload = b"Sensitive data"

# Associated data (binds encryption to context)
associated_data = {
    'frame_type': 0x02,
    'session_id': session_id,
    'sequence': 42,
    'stream_id': 0
}

# Encrypt
encrypted_payload, crypto_metadata = stc.encrypt_frame(
    payload,
    associated_data
)

# Result:
# - encrypted_payload: Opaque ciphertext
# - crypto_metadata: ~100 KB STC metadata (first time, cached after)
```

### Decrypting a Frame

```python
# Decrypt (requires same associated_data)
decrypted_payload = stc.decrypt_frame(
    encrypted_payload,
    crypto_metadata,
    associated_data
)

# Tampering with associated_data causes decryption to fail
```

### Why Associated Data?

Binds encryption to frame metadata - prevents attacks:

```python
# Original frame
associated = {'session_id': b'\x01' * 8, 'sequence': 1}
encrypted, meta = stc.encrypt_frame(payload, associated)

# Attacker tries to swap session_id
tampered = {'session_id': b'\x02' * 8, 'sequence': 1}

# Decryption fails ✓
try:
    stc.decrypt_frame(encrypted, meta, tampered)
except Exception:
    print("Tampering detected!")
```

---

## Session Key Derivation

### Derive Session Key

```python
# From handshake data
handshake_data = {
    'nonce_initiator': nonce_i.hex(),
    'nonce_responder': nonce_r.hex(),
    'node_id_initiator': node_i.hex(),
    'node_id_responder': node_r.hex()
}

# Derive 32-byte session key
session_key = stc.derive_session_key(handshake_data)

# Both peers derive SAME key (deterministic from handshake)
```

### Key Rotation

```python
# Rotate to new key
current_key = session.session_key
rotation_nonce = secrets.token_bytes(8)

# Derive new key
new_key = stc.rotate_session_key(current_key, rotation_nonce)

# Old key no longer valid
# Old ciphertexts can't be decrypted with new key (forward secrecy)
```

---

## Node Identity Generation

### Generate Node ID

```python
# Create ephemeral node ID
identity = b"node_identity_data"

node_id = stc.generate_node_id(identity)

# node_id is 32 bytes
# Non-deterministic: Different each time (privacy-preserving)
```

**Why Non-Deterministic?**

Prevents correlation:

```python
# Alice creates two nodes
node1_id = stc1.generate_node_id(b"alice")
node2_id = stc2.generate_node_id(b"alice")

# node1_id != node2_id
# Network observers can't link them to same identity
```

---

## Hashing with PHE

### Hash Data

```python
# Hash with context
data = b"data to hash"
context = {'purpose': 'commitment'}

hash_value = stc.hash_data(data, context)

# hash_value is 32 bytes
# NON-DETERMINISTIC: Changes each call
```

### Why Non-Deterministic Hashing?

Traditional hashing:

```python
# Old crypto (SHA-256)
hash1 = sha256(b"password")
hash2 = sha256(b"password")
# hash1 == hash2 (deterministic)
# → Rainbow tables, collision attacks possible
```

STC PHE:

```python
# Modern crypto (PHE)
hash1 = stc.hash_data(b"password")
hash2 = stc.hash_data(b"password")
# hash1 != hash2 (non-deterministic)
# → No rainbow tables, privacy-preserving
```

**Use Cases**:

- Commitments (can't reverse-engineer)
- Privacy-preserving identifiers
- Where collision resistance + privacy needed

**Don't Use For**:

- Session establishment (use key derivation instead)
- Deduplication (hashes won't match)
- Signatures (use deterministic crypto)

---

## Streaming Contexts

For bulk encryption (e.g., large file transfers):

### Create Streaming Context

```python
# Create context for session + stream
stream_context = stc.create_stream_context(
    session_id=session.session_id,
    stream_id=1
)

# Cached per (session_id, stream_id) pair
# Reuse for multiple encryptions
```

### Encrypt with Stream Context

```python
# Encrypt large data efficiently
chunk1 = b"X" * 65536  # 64 KB
chunk2 = b"Y" * 65536

# Stream context reused (faster)
enc1 = stream_context.encrypt(chunk1)
enc2 = stream_context.encrypt(chunk2)

# No metadata regeneration - very fast
```

---

## Complete Example: Encrypted Communication

```python
import asyncio
import secrets
from seigr_toolset_transmissions.crypto import STCWrapper

async def encrypted_comm_example():
    # Create two nodes with shared seed for handshake
    shared_seed = b"shared_seed_32bytes_minimum!!"
    
    alice_stc = STCWrapper(b"alice" * 8 + shared_seed)
    bob_stc = STCWrapper(b"bob__" * 8 + shared_seed)
    
    # Handshake
    nonce_alice = secrets.token_bytes(32)
    nonce_bob = secrets.token_bytes(32)
    
    # Derive session key (both peers get same key)
    handshake_data = {
        'nonce_alice': nonce_alice.hex(),
        'nonce_bob': nonce_bob.hex(),
        'purpose': 'session'
    }
    
    alice_key = alice_stc.derive_session_key(handshake_data)
    bob_key = bob_stc.derive_session_key(handshake_data)
    
    print(f"Keys match: {alice_key == bob_key}")  # True
    
    # Alice sends encrypted message
    message = b"Secret data"
    associated = {'sequence': 1, 'session_id': b'\x01' * 8}
    
    encrypted, metadata = alice_stc.encrypt_frame(message, associated)
    
    print(f"Encrypted: {encrypted[:32].hex()}...")
    
    # Bob decrypts
    decrypted = bob_stc.decrypt_frame(encrypted, metadata, associated)
    
    print(f"Decrypted: {decrypted}")  # b"Secret data"
    
    # Tamper detection
    tampered_assoc = {'sequence': 2, 'session_id': b'\x01' * 8}  # Wrong!
    
    try:
        bob_stc.decrypt_frame(encrypted, metadata, tampered_assoc)
    except Exception:
        print("Tampering detected! ✓")

asyncio.run(encrypted_comm_example())
```

---

## Security Properties

### Encryption

- **Algorithm**: STC adaptive encryption
- **Key Size**: 256 bits (32 bytes)
- **AEAD**: Associated data authenticated
- **Forward Secrecy**: Key rotation supported

### Key Derivation

- **Input**: Handshake nonces + node IDs
- **Output**: 256-bit session key
- **Deterministic**: Both peers derive same key
- **Context Binding**: Cannot reuse keys across sessions

### Hashing (PHE)

- **Non-Deterministic**: Different output each time
- **Privacy-Preserving**: No correlation attacks
- **Collision Resistant**: Adaptive morphing
- **Context Binding**: Optional context dict

---

## Common Patterns

### Key Hierarchy

```python
class KeyHierarchy:
    def __init__(self, master_seed):
        self.master = STCWrapper(master_seed)
    
    def derive_session_key(self, session_id: bytes):
        """Derive session key from master"""
        return self.master.derive_session_key({'session_id': session_id.hex()})
    
    def derive_stream_key(self, session_id: bytes, stream_id: int):
        """Derive stream key from session"""
        session_key = self.derive_session_key(session_id)
        
        # Create stream wrapper
        stream_stc = STCWrapper(session_key)
        return stream_stc.derive_session_key({'stream_id': stream_id})

# Usage
hierarchy = KeyHierarchy(b"master_seed_32bytes!!")
session_key = hierarchy.derive_session_key(b"\x01" * 8)
stream_key = hierarchy.derive_stream_key(b"\x01" * 8, stream_id=1)
```

### Metadata Caching

```python
class MetadataCache:
    def __init__(self, stc):
        self.stc = stc
        self.cache = {}
    
    def encrypt_with_cache(self, payload, session_id, stream_id):
        """Cache metadata per session/stream"""
        cache_key = (session_id, stream_id)
        
        # First encryption generates metadata
        encrypted, metadata = self.stc.encrypt_frame(
            payload,
            {'session_id': session_id, 'stream_id': stream_id}
        )
        
        if cache_key not in self.cache:
            self.cache[cache_key] = metadata
        
        return encrypted, self.cache[cache_key]

# Reuse metadata for subsequent encryptions (faster)
```

---

## Troubleshooting

### Decryption Fails

**Problem**: `decrypt_frame()` raises exception

**Causes**:

- Wrong STCWrapper seed
- Tampered associated_data
- Corrupted metadata

**Solution**: Verify associated_data matches:

```python
# Encryption
enc, meta = stc.encrypt_frame(payload, assoc)

# Decryption MUST use SAME assoc
dec = stc.decrypt_frame(enc, meta, assoc)  # ✓ Works

# Different assoc fails
dec = stc.decrypt_frame(enc, meta, different_assoc)  # ✗ Fails
```

### Hashes Don't Match

**Problem**: Expected deterministic hash, got different values

**Cause**: PHE is non-deterministic by design

**Solution**: Use key derivation for deterministic values:

```python
# Wrong: PHE for session ID
session_id = stc.hash_data(nonce1 + nonce2)  # ✗ Changes each time

# Right: Key derivation for session ID
session_id = stc.derive_session_key({
    'nonce1': nonce1.hex(),
    'nonce2': nonce2.hex()
})[:8]  # ✓ Deterministic (first 8 bytes)
```

### Large Metadata Size

**Problem**: First encryption generates ~100 KB metadata

**Cause**: STC metadata includes full context

**Solution**: Cache and reuse metadata:

```python
# First frame: metadata generated
enc1, meta = stc.encrypt_frame(payload1, assoc)

# Reuse metadata for subsequent frames (much smaller overhead)
# Stream layer handles this automatically
```

---

## Performance Considerations

**Encryption Speed**:

- Frame encryption: ~0.5ms per operation
- Streaming context: ~0.1ms per chunk (cached)
- Key derivation: ~1ms

**Metadata Overhead**:

- First frame: ~100 KB (one-time)
- Subsequent frames: Reuse cached metadata
- Network overhead: Send metadata once per session

**Optimization**:

```python
# Slow: Create new wrapper each time
for data in chunks:
    stc = STCWrapper(seed)  # ✗ Expensive
    enc, meta = stc.encrypt_frame(data, assoc)

# Fast: Reuse wrapper and stream context
stc = STCWrapper(seed)  # ✓ Once
stream_ctx = stc.create_stream_context(session_id, stream_id)

for data in chunks:
    enc = stream_ctx.encrypt(data)  # ✓ Fast
```

---

## Related Documentation

- **[Chapter 18: Handshake](18_handshake.md)** - Uses STCWrapper for authentication
- **[Chapter 19: Frames](19_frames.md)** - Frame encryption details
- **[Chapter 21: Chamber](21_chamber.md)** - Encrypted storage
- **[STC Documentation](https://seigr.net/stc/)** - Full STC specification
- **[API Reference](../api/API.md#crypto)** - Complete API

---

**Document Version**: 0.2.0a0 (unreleased)  
**Last Updated**: November 25, 2025
