# Chapter 4: Understanding Encryption (STC)

## Introduction

STT uses **STC (Seigr Temporal Cryptography)** exclusively for all encryption. This chapter explains what STC is, how it works at a conceptual level, and how STT uses it - without requiring cryptography expertise.

**Agnostic Note:** STC encrypts bytes. It doesn't care if those bytes are video, sensor data, files, or protocol messages. STT + STC = secure binary transport with zero semantic assumptions.

**Key takeaway:** STC is a custom cryptographic system using pre-shared seeds. It's different from standard systems like TLS/SSL, and you don't need to understand its internals to use STT effectively.

## What is STC?

### The Basics

**STC** is a cryptographic library that provides:

- **Encryption**: Scrambling data so only intended recipient can read it
- **Decryption**: Unscrambling data back to original
- **Hashing**: Creating fixed-size fingerprints of data (content addressing)
- **Key derivation**: Generating encryption keys from seeds

**Analogy:** STC is like a special lock-and-key system. Instead of exchanging physical keys, both parties start with the same "seed" (a shared secret), and STC generates matching locks and keys for both sides.

### STC vs Standard Cryptography (TLS)

| Aspect | TLS (Standard Web Security) | STC (Seigr Temporal Cryptography) |
|--------|----------------------------|-----------------------------------|
| **Key Exchange** | Public key cryptography (RSA, ECDH) | Pre-shared seeds |
| **Setup** | No prior setup (server has certificate) | Both peers need same seed beforehand |
| **Trust Model** | Certificate authorities (CAs) | Direct trust (you shared the seed) |
| **Use Case** | Public internet (connect to anyone) | Private networks (pre-authorized peers) |
| **Standardization** | IETF standards (RFC 5246, 8446) | Custom (Seigr ecosystem) |
| **Forward Secrecy** | Yes (ephemeral keys) | No (deterministic from seed) |

**Why STC instead of TLS?**

- **Content addressing**: STC.hash is integral to Seigr ecosystem (content IDs)
- **Deterministic**: Same seed always generates same keys (useful for distributed systems)
- **Simpler trust model**: No certificate infrastructure needed
- **Seigr ecosystem integration**: Designed specifically for this use case

**Trade-off:** Requires out-of-band seed distribution (you must share seeds securely before connecting).

## How STT Uses STC

### Pre-Shared Seeds

Before two peers can communicate, they must **share a seed** securely:

```
Alice and Bob meet in person
Alice: "Let's use seed: correct-horse-battery-staple-12345"
Bob writes it down

Later, Alice and Bob use this seed to establish STT session
```

**Important:** Seed sharing happens **outside** STT. Methods:

- In-person exchange
- Secure messaging (Signal, encrypted email)
- QR code
- Hardware security module
- Any trusted channel

**STT never transmits seeds over the network** - they must be shared beforehand.

### Seed to Keys

STC derives encryption keys from the seed using deterministic algorithms:

```
Shared Seed: "correct-horse-battery-staple-12345"
       ↓
   [STC Key Derivation]
       ↓
Encryption Key (256-bit): 0xA1B2C3D4...
Decryption Key (256-bit): 0xA1B2C3D4...  (same - symmetric)
```

**Both peers derive identical keys** from the same seed, so:

- Alice encrypts with key derived from seed
- Bob decrypts with key derived from same seed
- No key exchange needed (both have same key)

### Encryption in Practice

Every STT frame is encrypted before transmission:

```
Alice wants to send: "Hello Bob"
       ↓
[Encode to binary]: 0x48656C6C6F20426F62
       ↓
[STC Encrypt with derived key]
       ↓
Encrypted: 0x7A3F... (looks random)
       ↓
[Transmit over network]
       ↓
Bob receives: 0x7A3F...
       ↓
[STC Decrypt with same derived key]
       ↓
Decrypted: 0x48656C6C6F20426F62
       ↓
"Hello Bob" ✓
```

**Eavesdropper sees:** Encrypted bytes (0x7A3F...) - meaningless without the seed.

## STC Hashing

### Content Addressing

STC also provides **hashing** - creating unique fingerprints of data:

```
Data: "The quick brown fox jumps over the lazy dog"
       ↓
  [STC.hash]
       ↓
Hash: 0xD7A8FBB3...  (256-bit fingerprint)
```

**Properties:**

- **Unique**: Different data produces different hash (extremely likely)
- **Deterministic**: Same data always produces same hash
- **One-way**: Cannot reverse hash to get original data
- **Probabilistic**: STC.hash intentionally allows collisions (design choice for Seigr)

### Use in Seigr Ecosystem

**Content addressing** means data is identified by its hash:

```
File: "video.mp4" (100 MB)
STC.hash: 0xABC123...

In Seigr network:
- File stored at DHT key 0xABC123...
- Anyone with hash 0xABC123... can request file
- When received, verify: STC.hash(received_data) == 0xABC123...
```

**STT uses STC.hash for:**

- DHT node distances (XOR metric in Kademlia)
- Content discovery and addressing
- Chunk verification in content distribution

## Encryption Metadata

### What Gets Encrypted

STT encrypts the **payload** of each frame:

```
Frame Structure:

+------------------+
| Header           | ← NOT encrypted (routing info)
|  - Frame Type    |
|  - Stream ID     |
|  - Length        |
+------------------+
| Payload          | ← ENCRYPTED (your data)
|  - Your actual   |
|    data here     |
+------------------+
```

**Why header not encrypted?**

- STT needs to route frame to correct stream
- Length needed to parse frame boundaries
- Minimal information leakage (just "a frame exists on stream 3")

**Analogy:** Like an envelope - the address is visible (postal service needs it), but the letter inside is sealed.

### Encryption Parameters

Each encrypted payload includes **metadata** so receiver knows how to decrypt:

```python
{
    'ciphertext': b'\x7A\x3F...',  # Encrypted data
    'nonce': b'\xA1\xB2...',       # Random value (uniqueness)
    'tag': b'\xF3\xE4...',         # Authentication tag (integrity)
    # STC-specific parameters
    'seed_version': 1,             # Which seed was used
    'algorithm': 'STC-v1'          # Which STC algorithm
}
```

**Nonce:** Random value ensuring same plaintext encrypts differently each time
**Tag:** Cryptographic checksum proving data wasn't tampered with

**Receiver uses this metadata** to call STC decryption correctly.

## Security Properties

### What STC Provides

✅ **Confidentiality**: Eavesdroppers cannot read data (encryption)  
✅ **Integrity**: Tampering detected (authentication tags)  
✅ **Authentication**: Only peers with correct seed can decrypt (pre-shared seed)  
✅ **Determinism**: Same seed produces same keys (useful for Seigr)

### What STC Does NOT Provide

❌ **Forward Secrecy**: Compromised seed exposes all past sessions  
❌ **Public Key Infrastructure**: No certificate authorities, no PKI  
❌ **Anonymous Communication**: Peers must share seeds (know each other)  
❌ **Post-Quantum Security**: Vulnerable to quantum computers (currently)

### Threat Model

**STC protects against:**

- Passive eavesdropping (network sniffing)
- Man-in-the-middle without seed (attacker can't decrypt)
- Data tampering (authentication tags)

**STC does NOT protect against:**

- Stolen seeds (if attacker gets your seed, they can decrypt everything)
- Compromised endpoints (if Alice's computer is hacked, STC can't help)
- Traffic analysis (attacker can see "Alice and Bob are communicating", just not what)

**Important:** Secure your seeds! If an attacker gets your seed, they can:

- Decrypt all past traffic (if they recorded it)
- Impersonate you in future connections
- Read all future traffic

## Practical Implications

### Seed Management

**Good practices:**

1. **Generate strong seeds**: Use cryptographically random sources

   ```python
   import secrets
   seed = secrets.token_urlsafe(32)  # 256-bit seed
   ```

2. **Share seeds securely**: Never send seeds over unencrypted channels
   - ✅ In-person exchange
   - ✅ Encrypted messaging (Signal)
   - ❌ Email (unencrypted)
   - ❌ SMS (unencrypted)

3. **Rotate seeds periodically**: Generate new seeds for long-term relationships
   - Monthly: High security environments
   - Yearly: Normal usage
   - Never: Convenience (accept risk)

4. **Different seeds for different purposes**: Don't reuse seeds

   ```
   Alice-Bob file sharing: seed_1
   Alice-Carol video calls: seed_2
   Alice-Dave messaging: seed_3
   ```

### Performance

**STC is fast** - encryption/decryption are efficient:

- Typical: <1ms for 1KB payload on modern CPU
- Streaming: Gigabit speeds achievable
- Overhead: ~50 bytes per encrypted payload (metadata)

**Negligible performance impact** for most applications.

### Limitations

**Seed distribution is manual:**

- Can't connect to arbitrary peers (like HTTPS can)
- Requires planning (seed exchange before use)
- Doesn't scale to "millions of unknown peers" (public internet use case)

**Perfect for:**

- Known peer networks (you decide who to trust)
- Private applications
- Seigr ecosystem (content-addressed, pre-authorized peers)

**Not suitable for:**

- Public web servers (can't pre-share seeds with everyone)
- Anonymous systems (like Tor)
- Zero-setup protocols (like HTTP)

## XOR is NOT Encryption

### Common Confusion

You may see **XOR (⊕)** operations in STT code, particularly in session ID derivation:

```python
# Session ID mixing (from handshake)
nonce_xor = bytes(a ^ b for a, b in zip(our_nonce, peer_nonce))
node_xor = bytes(a ^ b for a, b in zip(our_node_id, peer_node_id))
session_id = (nonce_xor + node_xor)[:8]
```

**This is NOT encryption!** XOR here is just simple mathematical mixing to combine inputs deterministically.

**Why it looks confusing:**

- XOR is used in some encryption algorithms (like one-time pad)
- Seeing `^` operator might suggest cryptography
- **But in STT:** XOR is only for session ID derivation (mixing two random nonces to create a unique ID)

**Actual encryption:** Done by STC library (complex algorithms, not simple XOR)

### Real Encryption Happens in STC

```python
# This is NOT how STC encryption works (oversimplified)
encrypted = plaintext ^ key  ❌

# This is closer to reality (still simplified)
encrypted = STC.encrypt(
    plaintext=data,
    key=derived_key,
    nonce=random_nonce,
    algorithm='STC-v1'
)  ✓
```

STC uses sophisticated cryptographic algorithms - far more complex than XOR.

## Comparison with Other Systems

### STC vs TLS/SSL

**When to use TLS:**

- Public web servers (anyone can connect)
- Standard PKI (browsers trust CAs)
- Need forward secrecy
- Regulatory compliance (PCI-DSS requires TLS)

**When to use STC (STT):**

- Seigr ecosystem applications
- Private peer networks (pre-authorized)
- Content-addressed systems (STC.hash integration)
- Deterministic keys useful (same seed = same keys)

### STC vs WireGuard/VPN

**WireGuard** also uses pre-shared keys (similar concept):

- **WireGuard**: Network-level VPN (tunnel all traffic)
- **STT**: Application-level protocol (specific sessions/streams)

**Use WireGuard when:** You want to encrypt entire network connection  
**Use STT when:** You want application-specific encrypted channels

### STC vs GPG/PGP

**GPG** uses public key cryptography:

- **GPG**: Encrypt files/messages for specific recipients (public keys)
- **STC**: Symmetric encryption with pre-shared seeds

**Different trust models:**

- GPG: Web of trust or PKI
- STC: Direct trust (you shared the seed)

## Visual Summary

```
                STC in STT Architecture

+--------------------------------------------------+
|            Application Layer                     |
|  Your data: "Hello World"                       |
+--------------------------------------------------+
                       ↓
+--------------------------------------------------+
|             STC Encryption                       |
|  Seed → Derived Key → Encrypt                   |
|  Output: 0x7A3F... (encrypted)                  |
+--------------------------------------------------+
                       ↓
+--------------------------------------------------+
|            Frame Layer                           |
|  Header (unencrypted) | Payload (encrypted)     |
+--------------------------------------------------+
                       ↓
+--------------------------------------------------+
|            Transport (UDP/WebSocket)            |
|  Transmit encrypted frames                      |
+--------------------------------------------------+

                  [Network]

+--------------------------------------------------+
|  Receiver: Decrypt with same derived key        |
|  Output: "Hello World" ✓                        |
+--------------------------------------------------+
```

## Common Misconceptions

### "STC is weaker than TLS"

**Reality:** Different trade-offs, not inherently weaker

- TLS: Public key crypto (RSA/ECC) + symmetric (AES)
- STC: Symmetric only (pre-shared seeds)
- Both use strong symmetric encryption for bulk data

**Trade-off:** STC requires pre-shared seeds (less convenient), but simpler trust model (no CAs).

### "I need to understand STC internals to use STT"

**Reality:** No - treat STC as black box

- STT handles all STC calls
- You just provide seeds
- STC library does the hard work

**Analogy:** You don't need to understand TLS internals to use HTTPS.

### "Seeds are passwords"

**Reality:** Seeds are cryptographic keys, not passwords

- **Passwords**: Human-memorable, moderate entropy
- **Seeds**: Machine-generated, high entropy (256-bit)

**Generate seeds programmatically:**

```python
import secrets
seed = secrets.token_bytes(32)  # 256-bit random seed
```

Don't use "password123" as a seed!

### "XOR in handshake means weak crypto"

**Reality:** XOR is for session ID mixing, not encryption

- Session ID derivation uses XOR (simple math)
- Actual encryption uses STC (complex crypto)
- See section "XOR is NOT Encryption" above

## Best Practices

### Seed Generation

✅ **DO:**

- Use cryptographically secure random number generators (`secrets` module)
- Generate 256-bit (32 bytes) seeds minimum
- Store seeds securely (encrypted key stores, HSMs)

❌ **DON'T:**

- Use predictable seeds ("password", "12345")
- Reuse seeds across different peer relationships
- Store seeds in plaintext files
- Send seeds over unencrypted channels

### Seed Distribution

✅ **DO:**

- Exchange seeds in-person when possible
- Use end-to-end encrypted messaging (Signal)
- Use QR codes for local exchange (same room)
- Document which seed is for which peer

❌ **DON'T:**

- Email seeds (unencrypted)
- SMS seeds (unencrypted, logged by carriers)
- Post seeds publicly (obvious!)
- Assume obscurity = security

### Seed Rotation

✅ **DO:**

- Plan seed rotation schedule (yearly minimum)
- Re-key after employee departures (enterprise)
- Rotate after suspected compromise (immediately)

❌ **DON'T:**

- Use same seed forever (no forward secrecy)
- Rotate too frequently (operational burden)
- Forget old seeds (might need for recovery)

## Testing Your Understanding

1. **What is the primary difference between STC and TLS?**
   - STC uses pre-shared seeds; TLS uses public key cryptography

2. **Does STT encrypt frame headers?**
   - No - headers are unencrypted (routing info), payloads are encrypted

3. **Is the XOR operation in session ID derivation a form of encryption?**
   - No - it's simple mathematical mixing, not cryptographic encryption

4. **Can you connect to any STT peer without prior setup?**
   - No - you need to share a seed securely beforehand

5. **Does STC provide forward secrecy?**
   - No - compromised seed exposes all past sessions (deterministic keys)

6. **Why does Seigr ecosystem use STC instead of standard TLS?**
   - Content addressing (STC.hash), deterministic keys, simpler trust model for private networks

## Next Steps

Now that you understand encryption in STT:

- **Chapter 5**: Learn the handshake process (how seeds are used to establish sessions)
- **Chapter 6**: Explore sessions and connections (encrypted communication channels)
- **Chapter 13**: Study the security model (threat analysis, best practices)

**Remember:** You don't need to become a cryptography expert to use STT effectively. Understanding the concepts in this chapter is sufficient for practical use.

---

**Key Takeaways:**

- STC is symmetric encryption with pre-shared seeds (different from TLS)
- All STT payloads are encrypted; headers are not
- XOR in session ID derivation is mixing, not encryption
- Secure seed management is critical (strong generation, secure distribution, periodic rotation)
- STC designed for Seigr ecosystem (content addressing, deterministic keys)
- Current limitations: no forward secrecy, requires pre-shared seeds
