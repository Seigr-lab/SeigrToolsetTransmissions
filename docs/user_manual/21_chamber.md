# Chapter 21: Chamber Storage

**Version**: 0.2.0a0 (unreleased)  
**Component**: `Chamber`  
**Test Coverage**: 96.97%

---

## Overview

**Chamber** provides encrypted persistent storage using STC. Think of it as a secure vault where STT stores sensitive data.

All data in Chamber is:

- **Encrypted** with STC before writing to disk
- **Hash-addressed** for content verification
- **Node-isolated** (each node has separate storage directory)

---

## What is Chamber Used For?

Chamber stores:

- Session state (for recovery after restart)
- Peer information (known nodes)
- Configuration data
- Application data needing encryption at rest

**Not used for**:

- Live session data (kept in memory)
- Temporary buffers
- Large files (use external storage with STC encryption)

---

## Creating a Chamber

```python
from pathlib import Path
from seigr_toolset_transmissions.chamber import Chamber
from seigr_toolset_transmissions.crypto import STCWrapper

# Initialize STC
stc = STCWrapper(node_seed=b"node_seed_32bytes_minimum!!!")

# Create chamber
chamber = Chamber(
    chamber_path=Path("./stt_storage"),
    node_id=b"node_identifier_32_bytes_long",
    stc_wrapper=stc
)

# Chamber directory structure:
# ./stt_storage/
#   └── 6e6f64655f696465/   (node_id hex prefix)
#       ├── key1.stt
#       ├── key2.stt
#       └── ...
```

---

## Storing Data

Store any serializable Python object:

```python
# Store simple data
chamber.store("user_config", {
    'username': 'alice',
    'preferences': {'theme': 'dark'}
})

# Store bytes
chamber.store("session_state", b"\x01\x02\x03\x04")

# Store complex structures
chamber.store("peers", [
    {'node_id': 'abc123', 'address': '10.0.0.1:8080'},
    {'node_id': 'def456', 'address': '10.0.0.2:8080'}
])
```

**What happens internally**:

1. Data serialized to bytes
2. Encrypted with STC
3. Written to `{chamber_path}/{node_id_hex}/{key}.stt`

---

## Retrieving Data

```python
# Retrieve data
config = chamber.retrieve("user_config")

print(config)
# {'username': 'alice', 'preferences': {'theme': 'dark'}}

# Data automatically:
# 1. Read from disk
# 2. Decrypted with STC
# 3. Deserialized to original type
```

### Handling Missing Keys

```python
from seigr_toolset_transmissions.utils.exceptions import STTChamberError

try:
    data = chamber.retrieve("nonexistent_key")
except STTChamberError:
    print("Key not found!")
    data = None  # Use default
```

---

## Deleting Data

```python
# Delete key
chamber.delete("old_config")

# Key no longer exists
try:
    chamber.retrieve("old_config")
except STTChamberError:
    print("Deleted!")
```

---

## Listing Keys

```python
# Get all stored keys
keys = chamber.list_keys()

print(f"Stored keys: {keys}")
# ['user_config', 'session_state', 'peers']
```

---

## Checking Key Existence

```python
# Check if key exists
if chamber.exists("session_state"):
    state = chamber.retrieve("session_state")
else:
    state = initialize_new_state()
```

---

## Complete Example: Session Recovery

```python
import asyncio
from pathlib import Path
from seigr_toolset_transmissions import STTNode
from seigr_toolset_transmissions.chamber import Chamber
from seigr_toolset_transmissions.crypto import STCWrapper

async def session_recovery_example():
    node_seed = b"node_seed_32bytes_minimum!!!"
    shared_seed = b"shared_secret_32bytes_minimum!"
    
    # Create node with chamber
    node = STTNode(
        node_seed=node_seed,
        shared_seed=shared_seed,
        chamber_path=Path("./stt_storage"),
        port=8080
    )
    
    await node.start(server_mode=True)
    
    # Store session info
    session_data = {
        'active_sessions': [],
        'peer_list': [
            {'node_id': 'peer1', 'last_seen': 1700000000},
            {'node_id': 'peer2', 'last_seen': 1700000100}
        ]
    }
    
    node.chamber.store("session_backup", session_data)
    print("Session data stored")
    
    # Simulate restart
    await node.stop()
    
    # Create new node instance
    node2 = STTNode(
        node_seed=node_seed,  # Same seed
        shared_seed=shared_seed,
        chamber_path=Path("./stt_storage"),
        port=8080
    )
    
    await node2.start(server_mode=True)
    
    # Recover session data
    recovered = node2.chamber.retrieve("session_backup")
    print(f"Recovered peers: {len(recovered['peer_list'])}")
    
    await node2.stop()

asyncio.run(session_recovery_example())
```

---

## Encryption Model

### How Data is Encrypted

```python
# When storing:
plaintext = serialize(data)

# Encrypt with associated data
associated_data = {
    'key': 'my_key',
    'node_id': node_id.hex(),
    'purpose': 'chamber_storage'
}

encrypted, metadata = stc.encrypt_frame(plaintext, associated_data)

# Store both encrypted data + metadata
storage_file = {
    'encrypted': encrypted,
    'metadata': metadata,
    'key': 'my_key',
    'associated_data': associated_data
}
```

### Why Associated Data?

Binds encryption to context:

- **key**: Prevents key swap attacks
- **node_id**: Ensures data can't be moved to different node
- **purpose**: Prevents repurposing encrypted data

Tampering with any of these causes decryption to fail.

---

## Node Isolation

Each node has its own storage directory:

```
chamber_path/
  ├── 6e6f64655f696465/  ← Node A (node_id=6e6f64...)
  │   ├── config.stt
  │   └── peers.stt
  │
  └── 616c6963655f6e6f/  ← Node B (node_id=616c69...)
      ├── config.stt
      └── state.stt
```

**Why?** Prevents data corruption if multiple nodes share same chamber_path.

---

## File Format

Each `.stt` file contains:

```python
{
    'encrypted': b'\x9a\x2f\x1c...',  # Encrypted payload
    'metadata': b'\x01\x02...',        # STC crypto metadata
    'key': 'user_config',              # Storage key
    'associated_data': {               # Context binding
        'key': 'user_config',
        'node_id': '6e6f64...',
        'purpose': 'chamber_storage'
    }
}
```

Serialized with STT serialization format (see [Chapter 24](24_binary_streaming.md)).

---

## Common Patterns

### Configuration Management

```python
class ConfigManager:
    def __init__(self, chamber):
        self.chamber = chamber
        self.config_key = "app_config"
    
    def load_config(self):
        """Load or create default config"""
        try:
            return self.chamber.retrieve(self.config_key)
        except STTChamberError:
            # Create default
            default = {'version': 1, 'settings': {}}
            self.chamber.store(self.config_key, default)
            return default
    
    def update_setting(self, key, value):
        """Update single setting"""
        config = self.load_config()
        config['settings'][key] = value
        self.chamber.store(self.config_key, config)

# Usage
config_mgr = ConfigManager(node.chamber)
config_mgr.update_setting('log_level', 'DEBUG')
```

### Peer Database

```python
class PeerDB:
    def __init__(self, chamber):
        self.chamber = chamber
    
    def add_peer(self, node_id: bytes, address: str):
        """Add or update peer"""
        peers = self.get_all_peers()
        peers[node_id.hex()] = {
            'address': address,
            'last_seen': time.time()
        }
        self.chamber.store("peer_database", peers)
    
    def get_all_peers(self):
        """Get all known peers"""
        try:
            return self.chamber.retrieve("peer_database")
        except STTChamberError:
            return {}
    
    def get_peer(self, node_id: bytes):
        """Get specific peer"""
        peers = self.get_all_peers()
        return peers.get(node_id.hex())

# Usage
peer_db = PeerDB(node.chamber)
peer_db.add_peer(b"peer_node_id_32bytes!!!!!!!", "10.0.0.1:8080")
```

### Cache with Expiration

```python
import time

class ChamberCache:
    def __init__(self, chamber):
        self.chamber = chamber
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """Store with expiration"""
        cache_entry = {
            'value': value,
            'expires_at': time.time() + ttl
        }
        self.chamber.store(f"cache_{key}", cache_entry)
    
    def get(self, key: str):
        """Get if not expired"""
        try:
            entry = self.chamber.retrieve(f"cache_{key}")
            
            if time.time() < entry['expires_at']:
                return entry['value']
            else:
                # Expired
                self.chamber.delete(f"cache_{key}")
                return None
        except STTChamberError:
            return None

# Usage
cache = ChamberCache(node.chamber)
cache.set("temp_data", {'foo': 'bar'}, ttl=60)  # 60 second TTL
```

---

## Troubleshooting

### Decryption Failure

**Problem**: `STTChamberError` when retrieving

**Causes**:

- Different STCWrapper seed used for encryption vs decryption
- Corrupted file
- Tampered associated_data

**Solution**: Ensure same seed:

```python
# Must use same node_seed
stc1 = STCWrapper(node_seed=b"seed1...")
chamber1 = Chamber(..., stc_wrapper=stc1)
chamber1.store("key", data)

# This will fail - different seed
stc2 = STCWrapper(node_seed=b"seed2...")  # ✗ Wrong!
chamber2 = Chamber(..., stc_wrapper=stc2)
chamber2.retrieve("key")  # Decryption fails!
```

### Key Not Found

**Problem**: Key doesn't exist

**Solution**: Check before retrieving:

```python
if chamber.exists("my_key"):
    data = chamber.retrieve("my_key")
else:
    data = default_value
```

### File Permission Errors

**Problem**: Can't write to chamber directory

**Solution**: Ensure write permissions:

```python
chamber_path = Path("./stt_storage")
chamber_path.mkdir(parents=True, exist_ok=True)

# Check permissions
if not os.access(chamber_path, os.W_OK):
    print("No write permission!")
```

---

## Performance Considerations

**Storage Overhead**:

- Metadata size: ~100 KB per file (STC metadata)
- Encryption time: ~0.5ms per operation
- Disk I/O: Depends on filesystem

**Optimization Tips**:

1. **Batch writes**: Group related data in single key
2. **Compress large data**: Before storing
3. **Use cache**: Avoid repeated retrieval

```python
# Bad: Multiple small writes
for i in range(100):
    chamber.store(f"item_{i}", data[i])  # ✗ Slow

# Good: Single batched write
chamber.store("all_items", data)  # ✓ Fast
```

---

## Security Notes

**Encryption**:

- All data encrypted with STC
- Associated data prevents context swap
- Metadata binding ensures integrity

**Key Management**:

- Storage keys are plaintext (filenames)
- Use non-sensitive keys (e.g., "config" not "password123")
- Sensitive key names stored in encrypted index if needed

**Node Isolation**:

- Each node_id gets separate directory
- No cross-node data access
- Prevents multi-tenant data leaks

---

## Related Documentation

- **[Chapter 16: STTNode](16_sttnode.md)** - Uses chamber for storage
- **[Chapter 23: Cryptography](23_cryptography.md)** - STC encryption details
- **[Chapter 24: Binary Streaming](24_binary_streaming.md)** - Serialization format
- **[API Reference](../api/API.md#chamber)** - Complete API

---

**Document Version**: 0.2.0a0 (unreleased)  
**Last Updated**: November 25, 2025
