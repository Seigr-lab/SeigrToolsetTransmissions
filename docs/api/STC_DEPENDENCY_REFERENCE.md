# Seigr Toolset Crypto (STC) - External Dependency Reference

> **IMPORTANT**: This document describes the **external STC cryptography library** that STT depends on.  
> **STC Package**: `seigr-toolset-crypto>=0.4.0` (separate package, separate repository)  
> **Import**: `from interfaces.api import stc_api`  
> **This is NOT part of STT** - it's a dependency. For STT APIs, see `API.md`.

**STC Version Required**: >=0.4.0  
**STT Version**: 0.2.0a0 (unreleased)

---

## Architecture Overview

STC provides post-classical cryptography through five core components:

1. **CEL** (Continuous Entropy Lattice) - Evolving entropy field
2. **PHE** (Probabilistic Hashing Engine) - Context-dependent hashing
3. **CKE** (Contextual Key Emergence) - Ephemeral key derivation
4. **DSF** (Data State Folding) - Tensor-based encryption
5. **PCF** (Polymorphic Cryptographic Flow) - Algorithmic morphing

---

## High-Level API (stc_api module)

### Initialization

```python
from interfaces.api import stc_api

# Full context initialization
context = stc_api.STCContext(
    seed: Union[str, bytes, int],
    lattice_size: int = 128,           # CEL lattice dimension
    depth: int = 6,                     # CEL lattice depth
    morph_interval: int = 100,          # PCF morph frequency
    adaptive_difficulty: str = 'balanced',  # 'paranoid', 'balanced', 'fast'
    adaptive_morphing: bool = True      # Enable context-adaptive morphing
)

# Quick initialization (simpler)
context = stc_api.initialize(
    seed: Union[str, bytes, int],
    lattice_size: int = 256,
    depth: int = 8,
    morph_interval: int = 100,
    adaptive_difficulty: str = 'balanced',
    adaptive_morphing: bool = True
) -> STCContext
```

### Encryption/Decryption

#### Standard Encryption
```python
# Context-based encryption
encrypted_bytes, metadata = context.encrypt(
    data: Union[str, bytes],
    context_data: Optional[Dict[str, Any]] = None,
    password: Optional[str] = None,
    use_decoys: bool = True
) -> Tuple[bytes, Dict[str, Any]]

decrypted = context.decrypt(
    encrypted_data: bytes,
    metadata: Dict[str, Any],
    context_data: Optional[Dict[str, Any]] = None,
    password: Optional[str] = None
) -> Union[str, bytes]

# Quick encryption (creates context automatically)
encrypted_bytes, metadata, context = stc_api.quick_encrypt(
    data: Union[str, bytes],
    seed: Union[str, bytes, int]
) -> Tuple[bytes, Dict[str, Any], STCContext]

decrypted = stc_api.quick_decrypt(
    encrypted_data: bytes,
    metadata: Dict[str, Any],
    seed: Union[str, bytes, int]
) -> Union[str, bytes]

# Module-level functions (create ephemeral context)
encrypted_bytes, metadata = stc_api.encrypt(
    data: Union[str, bytes],
    context: STCContext,
    context_data: Optional[Dict[str, Any]] = None
) -> Tuple[bytes, Dict[str, Any]]

decrypted = stc_api.decrypt(
    encrypted_data: bytes,
    metadata: Dict[str, Any],
    context: STCContext,
    context_data: Optional[Dict[str, Any]] = None
) -> Union[str, bytes]
```

#### Streaming Encryption (v0.3.0)
```python
# Encrypt large data in chunks - yields encrypted chunks
for chunk_idx, encrypted_chunk in context.encrypt_stream(
    data: Union[str, bytes],
    chunk_size: int = 1024 * 1024,      # 1MB chunks default
    password: Optional[str] = None,
    use_decoys: bool = True,
    progress_callback: Optional[callable] = None
):
    if chunk_idx == 'metadata':
        # Last yield is metadata
        metadata_bytes = encrypted_chunk
    else:
        # Regular chunk
        store_chunk(chunk_idx, encrypted_chunk)

# Decrypt stream
decrypted_data = context.decrypt_stream(
    encrypted_chunks: List[bytes],
    metadata: Dict[str, Any],
    password: Optional[str] = None,
    progress_callback: Optional[callable] = None
) -> Union[str, bytes]
```

### Hashing

```python
# Context-based probabilistic hash
hash_bytes = context.hash(
    data: Union[str, bytes],
    context_data: Optional[Dict[str, Any]] = None
) -> bytes

# Module-level hash
hash_bytes = stc_api.hash_data(
    data: Union[str, bytes],
    context: STCContext,
    context_data: Optional[Dict[str, Any]] = None
) -> bytes
```

### Key Derivation

```python
# Derive key from context
key_bytes = context.derive_key(
    context_data: Dict[str, Any],
    key_size: int = 32
) -> bytes
```

### Metadata Management

```python
# Encrypt metadata with password
encrypted_meta = stc_api.encrypt_metadata(
    metadata: Dict[str, Any],
    password: str,
    use_differential: bool = True,
    seed: Union[str, bytes, int, None] = None
) -> Dict[str, Any]

# Decrypt metadata
decrypted_meta = stc_api.decrypt_metadata(
    encrypted_data: Dict[str, Any],
    password: str,
    seed: Union[str, bytes, int, None] = None
) -> Dict[str, Any]

# Inject decoy vectors (polymorphic obfuscation)
obfuscated = stc_api.inject_decoy_vectors(
    real_metadata: Dict[str, Any],
    password: str,
    num_decoys: int = 3,
    variable_sizes: bool = True,
    randomize_count: bool = True,
    timing_randomization: bool = True,
    noise_padding: bool = False
) -> Dict[str, Any]

# Extract real vector from decoys
real_meta = stc_api.extract_real_vector(
    obfuscated: Dict[str, Any],
    password: str
) -> Dict[str, Any]
```

### TLV Serialization (Self-Sovereign Binary Format)

```python
# Serialize to binary TLV format
tlv_bytes = stc_api.serialize_metadata_tlv(
    metadata: Dict[str, Any],
    version: int = 1
) -> bytes

# Deserialize from TLV
metadata = stc_api.deserialize_metadata_tlv(
    data: bytes
) -> Dict[str, Any]

# Detect metadata version
version = stc_api.detect_metadata_version(
    data: Union[bytes, str]
) -> int  # Returns METADATA_VERSION_TLV (0x01)
```

### State Management

```python
# Save complete context state
state_dict = context.save_state(
    filepath: Optional[str] = None
) -> Dict[str, Any]

# Get entropy profile
profile = context.get_entropy_profile() -> Dict[str, Any]

# Set minimum entropy threshold
context.set_minimum_entropy_threshold(
    threshold: Optional[float] = 0.7
)

# Get adaptive difficulty status
status = context.get_adaptive_difficulty_status() -> Dict[str, Any]

# Get context status string
status_str = context.get_status() -> str
```

---

## Core Component APIs

### CEL (Continuous Entropy Lattice)

```python
from core.cel import cel

# Create CEL instance
cel_instance = stc_api.initialize_cel(
    seed: Union[str, bytes, int],
    lattice_size: int = 256,
    depth: int = 8
) -> ContinuousEntropyLattice

# Methods
cel_instance.update(context: Dict[str, Any])          # Update entropy state
snapshot = cel_instance.snapshot() -> Dict[str, Any]  # Get state snapshot
cel_instance.restore_snapshot(snapshot: Dict)         # Restore from snapshot
entropy = cel_instance.extract_entropy(size: int) -> bytes
profile = cel_instance.get_entropy_profile() -> Dict
hash_val = cel_instance.get_state_hash() -> bytes
audit = cel_instance.get_audit_log() -> List[Dict]
```

### PHE (Probabilistic Hashing Engine)

```python
from core.phe import phe

# Create PHE instance
phe_instance = stc_api.create_phe(
    cel_snapshot: Optional[Dict[str, Any]] = None
) -> ProbabilisticHashingEngine

# Methods
hash_bytes = phe_instance.digest(
    data: Union[str, bytes],
    context: Optional[Dict] = None
) -> bytes

verified = phe_instance.verify(
    data: Union[str, bytes],
    hash_value: bytes,
    context: Optional[Dict] = None
) -> bool

phe_instance.map_entropy(cel_snapshot: Dict)
trace = phe_instance.trace(data: Union[str, bytes]) -> Dict
audit = phe_instance.get_audit_log() -> List[Dict]
```

### CKE (Contextual Key Emergence)

```python
from core.cke import cke

# Create CKE instance
cke_instance = stc_api.create_cke() -> ContextualKeyEmergence

# Methods
key_vector = cke_instance.derive(
    context: Dict[str, Any]
) -> numpy.ndarray

subkey = cke_instance.derive_subkey(
    base_key: numpy.ndarray,
    index: int,
    purpose: str
) -> numpy.ndarray

combined = cke_instance.combine(
    keys: List[numpy.ndarray]
) -> numpy.ndarray

key_bytes = cke_instance.get_key_bytes(
    key_vector: numpy.ndarray,
    size: int = 32
) -> bytes

cke_instance.discard()  # Securely discard ephemeral keys
```

### DSF (Data State Folding)

```python
from core.dsf import dsf

# Create DSF instance
dsf_instance = stc_api.create_dsf() -> DataStateFolding

# Methods
encrypted = dsf_instance.fold(
    data: Union[bytes, str],
    key_vector: numpy.ndarray,
    cel_snapshot: Optional[Dict[str, Any]] = None
) -> bytes

decrypted = dsf_instance.unfold(
    folded_data: bytes,
    key_vector: numpy.ndarray,
    cel_snapshot: Optional[Dict[str, Any]] = None
) -> bytes

verified = dsf_instance.verify_integrity(
    data: bytes,
    expected_hash: bytes
) -> bool
```

### PCF (Polymorphic Cryptographic Flow)

```python
from core.pcf import pcf

# Create PCF instance
pcf_instance = stc_api.create_pcf(
    morph_interval: int = 100,
    adaptive_morphing: bool = True
) -> PolymorphicCryptographicFlow

# Methods
pcf_instance.bind(cel_snapshot: Dict)
pcf_instance.cycle()  # Trigger morph event
params = pcf_instance.get_folding_parameters() -> Dict
order = pcf_instance.get_operation_order() -> List[str]
description = pcf_instance.describe() -> str
meta_state = pcf_instance.get_meta_state() -> Dict
adaptive_status = pcf_instance.get_adaptive_status() -> Dict
next_morph = pcf_instance.predict_next_morph() -> int

state_dict = pcf_instance.export_state() -> Dict
pcf_instance.import_state(state_dict: Dict)
pcf_instance.set_morph_interval(interval: int)
```

### State Manager

```python
from core.state import state

# Create state manager
sm = stc_api.create_state_manager() -> StateManager

# Methods (to be defined based on actual implementation)
```

---

## Data Flow for STT Integration

### For Frame Encryption (AEAD-like)

```python
# Initialize context once per session
context = stc_api.initialize(seed=session_seed)

# Encrypt frame payload
frame_data = b"binary payload"
associated_data = {"frame_type": type, "session_id": sid, "seq": seq}

encrypted, metadata = context.encrypt(
    data=frame_data,
    context_data=associated_data
)

# On receiving side
decrypted = context.decrypt(
    encrypted_data=encrypted,
    metadata=metadata,
    context_data=associated_data
)
```

### For Content Hashing (Node IDs, Content Addressing)

```python
# Hash public key to create node ID
node_id = context.hash(public_key_bytes)

# Hash content for content addressing
content_hash = context.hash(file_content)
```

### For Key Derivation (Session Keys, Subkeys)

```python
# Derive session key from handshake context
session_key = context.derive_key(
    context_data={
        'hello_nonce': hello_nonce,
        'response_nonce': resp_nonce,
        'ephemeral_key': eph_key
    },
    key_size=32
)
```

### For Streaming Data (Live Streaming)

```python
# Streaming encryption for large transfers
chunks = []
metadata = None

for chunk_idx, encrypted_chunk in context.encrypt_stream(
    data=large_video_data,
    chunk_size=64 * 1024  # 64KB chunks for low latency
):
    if chunk_idx == 'metadata':
        metadata = encrypted_chunk
    else:
        # Send chunk immediately (streaming)
        await send_chunk(chunk_idx, encrypted_chunk)

# Decryption
decrypted = context.decrypt_stream(
    encrypted_chunks=received_chunks,
    metadata=metadata
)
```

---

## Key Characteristics for STT

### What STC Provides

1. **Encryption**: DSF fold/unfold with AEAD-like properties via associated data
2. **Hashing**: PHE digest for content addressing and node IDs
3. **Key Derivation**: CKE derive for session keys and subkeys
4. **Streaming**: Native chunked encryption/decryption for large data
5. **Metadata Protection**: Built-in metadata encryption with decoy injection
6. **Self-Sovereignty**: No external crypto dependencies, custom binary TLV format
7. **Adaptability**: Automatic difficulty scaling, attack detection
8. **Persistence**: State snapshots for deterministic reproduction

### What STC Does NOT Provide

1. **No X25519/Ed25519**: No traditional elliptic curve operations (need to verify)
2. **No Standard AEAD**: Uses DSF fold (different from AES-GCM/ChaCha20-Poly1305)
3. **No Traditional KDF**: Uses CKE derive (different from HKDF/PBKDF2)
4. **No Standard Hash**: Uses PHE digest (different from SHA-256/BLAKE3)
5. **No Digital Signatures**: Need to verify if signing capability exists

### Critical Questions for STT Design

1. **Handshake Crypto**: Does STC provide key agreement (like X25519)? Or do we need to implement our own?
2. **Digital Signatures**: Can STC sign/verify for authentication? Or external implementation needed?
3. **WebSocket SHA-1**: Browser WebSocket handshake requires SHA-1 + base64. Do we use STC.hash or make exception?
4. **Performance**: What are encryption/decryption speeds for realtime streaming?
5. **Nonce/IV Management**: How does STC handle nonce reuse prevention for AEAD?

---

## Integration Strategy for STT

### Phase 1: Verify Capabilities
- [ ] Test if STC can perform key agreement (DH/ECDH equivalent)
- [ ] Test if STC can sign/verify (Ed25519 equivalent)
- [ ] Benchmark encryption speed for streaming (target: >100MB/s)
- [ ] Verify AEAD properties (authentication + encryption)

### Phase 2: Core Integration
- [ ] Replace all hashlib usage with `stc_api.hash_data()`
- [ ] Replace frame encryption with `context.encrypt()` + associated_data
- [ ] Replace session key derivation with `context.derive_key()`
- [ ] Implement handshake using STC primitives

### Phase 3: Streaming Layer
- [ ] Use `context.encrypt_stream()` for large file transfers
- [ ] Implement chunked streaming for live video/audio
- [ ] Add flow control for streaming chunks
- [ ] Test low-latency streaming (<100ms)

### Phase 4: WebSocket Native
- [ ] Implement RFC 6455 handshake (SHA-1 exception for browser compat)
- [ ] Use STC for WebSocket frame encryption
- [ ] Binary tunnel mode for pure STT over WS

---

## Version Information

- **STC Version**: 0.3.1
- **Python Requirement**: 3.8+ (uses numpy)
- **Dependencies**: numpy (only external dependency)
- **License**: (need to check)

---

## Next Steps

1. **Run STC capability tests** to verify key agreement and signing
2. **Benchmark streaming performance** to validate realtime requirements
3. **Design STT handshake** using only STC primitives
4. **Create STC wrapper layer** in STT to centralize all crypto calls
5. **Build streaming foundation** using `encrypt_stream`/`decrypt_stream`
