# Chapter 5: The Handshake Process

## Introduction

Before two peers can communicate securely, they must perform a **handshake** - a sequence of messages that establishes trust and creates a shared session. This chapter explains STT's 4-message handshake in detail.

**Agnostic Design:** The handshake authenticates peers and establishes encrypted sessions for ANY data exchange. Whether you're streaming video, transferring files, running custom protocols, or storing sensor data - the handshake process is identical. STT doesn't know or care what data will flow through the session.

## Why Do We Need a Handshake?

### The Problem

Imagine you receive a phone call from someone claiming to be your friend:

- How do you know it's really them?
- How do you establish a conversation without someone eavesdropping?
- How do you agree on a "language" (encryption) for your conversation?

The handshake solves these problems for computers.

### Goals of the Handshake

1. **Mutual Authentication**: Both peers verify each other's identity
2. **Session Establishment**: Create a unique session ID for this connection
3. **Key Agreement**: Derive encryption keys for secure communication
4. **Replay Protection**: Ensure old handshake messages can't be reused

## STT's 4-Message Handshake

STT uses a 4-message handshake protocol:

```
Initiator (Alice)          Responder (Bob)
-----------------          ----------------
      |                           |
      |  1. HELLO                 |
      |-------------------------->|
      |                           |
      |  2. RESPONSE              |
      |<--------------------------|
      |                           |
      |  3. AUTH_PROOF            |
      |-------------------------->|
      |                           |
      |  4. FINAL                 |
      |<--------------------------|
      |                           |
   [Session Established]
```

Let's walk through each message step by step.

## Message 1: HELLO

### What Happens

**Alice (Initiator) generates:**

1. A random 32-byte **nonce** (number used once)
2. A **commitment** hash of (node_id + nonce)

**Alice sends to Bob:**

```python
{
  'type': 'HELLO',
  'node_id': alice_node_id,        # 32 bytes
  'nonce': alice_nonce,             # 32 bytes
  'timestamp': current_time_ms,    # milliseconds
  'commitment': hash(node_id + nonce)  # 32 bytes
}
```

### Why the Commitment?

The commitment prevents the responder from changing the initiator's nonce. Bob can't manipulate the nonce because the hash proves what it should be.

**Analogy**: Like sealing your vote in an envelope before submitting it - no one can change it after you've committed.

### Real Example

```
Alice generates nonce: 0xA1B2C3D4...
Alice's node ID:       0x12345678...
Commitment:            hash(0x12345678... + 0xA1B2C3D4...) = 0xDEADBEEF...

Alice sends:
  HELLO {
    node_id: 0x12345678...,
    nonce: 0xA1B2C3D4...,
    commitment: 0xDEADBEEF...
  }
```

## Message 2: RESPONSE

### What Happens

**Bob (Responder) receives HELLO and:**

1. Verifies the commitment matches hash(node_id + nonce)
2. Generates his own random 32-byte nonce
3. Creates a **challenge** by encrypting (alice_nonce + bob_nonce) with STC

**Bob sends to Alice:**

```python
{
  'type': 'RESPONSE',
  'node_id': bob_node_id,               # 32 bytes
  'nonce': bob_nonce,                   # 32 bytes
  'challenge': encrypted_payload,       # variable
  'challenge_metadata': stc_metadata,   # variable
  'timestamp': current_time_ms
}
```

### The Challenge

The challenge is the core of authentication:

```
Plaintext:  alice_nonce + bob_nonce  (64 bytes)
    ↓
[Encrypt with STC using shared_seed]
    ↓
Ciphertext: (encrypted bytes + metadata)
```

**Key point**: Only someone with the same shared_seed can decrypt this!

### Why This Works

- Bob proves he has the shared_seed (he encrypted correctly)
- Alice can verify by decrypting
- If Alice doesn't have the right seed, decryption will fail or give garbage

### Real Example

```
Bob generates nonce: 0xFEDCBA98...
Bob creates challenge payload: alice_nonce (0xA1B2C3D4...) + bob_nonce (0xFEDCBA98...)

Bob encrypts with STC using shared_seed → encrypted_challenge

Bob sends:
  RESPONSE {
    node_id: 0x87654321...,
    nonce: 0xFEDCBA98...,
    challenge: (encrypted bytes),
    challenge_metadata: (STC parameters)
  }
```

## Message 3: AUTH_PROOF

### What Happens

**Alice receives RESPONSE and:**

1. Decrypts the challenge using her STC (with shared_seed)
2. Verifies the decrypted data = (alice_nonce + bob_nonce)
3. Calculates session_id = XOR[alice_nonce, bob_nonce, alice_node_id, bob_node_id](0:8)
4. Encrypts the session_id as proof

**Alice sends to Bob:**

```python
{
  'type': 'AUTH_PROOF',
  'session_id': session_id,           # 8 bytes
  'proof': encrypted_session_id,      # variable
  'proof_metadata': stc_metadata,     # variable
  'timestamp': current_time_ms
}
```

### Session ID Derivation

The session ID is deterministic - both sides calculate it independently using simple mathematical mixing:

```
# XOR nonces together (pure math, not cryptography)
nonce_xor = XOR(alice_nonce, bob_nonce)

# XOR node IDs together
node_xor = XOR(alice_node_id, bob_node_id)

# Combine and take first 8 bytes as session ID
session_id = (nonce_xor + node_xor)[0:8]
```

**Why XOR?**

- **Deterministic**: Same inputs always produce same output - both peers calculate identical session ID
- **Commutative**: `A ⊕ B = B ⊕ A` - order doesn't matter, both peers get same result
- **Simple**: Fast mathematical operation, no cryptographic primitives needed
- **Unique**: Combines random nonces with persistent node IDs

**What XOR is NOT:**

- This is **not encryption** - XOR is just mathematical mixing
- This is **not for security** - just unique session identification
- The nonces themselves provide randomness (from cryptographically secure source)

### The Proof

Alice encrypts the session_id to prove she:

1. Successfully decrypted Bob's challenge (has correct shared_seed)
2. Correctly calculated the session_id
3. Can encrypt data (ready to communicate)

### Real Example

```
Alice decrypts challenge → 0xA1B2C3D4... + 0xFEDCBA98... ✓ (matches!)

Alice calculates:
  session_id = XOR(0xA1B2C3D4..., 0xFEDCBA98..., 0x12345678..., 0x87654321...)[0:8]
             = 0x0123456789ABCDEF

Alice encrypts session_id with STC → encrypted_proof

Alice sends:
  AUTH_PROOF {
    session_id: 0x0123456789ABCDEF,
    proof: (encrypted bytes),
    proof_metadata: (STC parameters)
  }
```

## Message 4: FINAL

### What Happens

**Bob receives AUTH_PROOF and:**

1. Calculates session_id using the same XOR formula
2. Decrypts Alice's proof
3. Verifies decrypted proof matches his calculated session_id
4. Sends confirmation

**Bob sends to Alice:**

```python
{
  'type': 'FINAL',
  'session_id': session_id,    # 8 bytes (confirmation)
  'timestamp': current_time_ms
}
```

### Verification

If Bob's decrypted proof matches his calculated session_id:

- Alice has the correct shared_seed ✓
- Both agree on the session_id ✓
- Session can be established ✓

If verification fails:

- Authentication fails
- Handshake aborted
- Connection refused

### Real Example

```
Bob calculates:
  session_id = XOR(0xA1B2C3D4..., 0xFEDCBA98..., 0x12345678..., 0x87654321...)[0:8]
             = 0x0123456789ABCDEF

Bob decrypts proof → 0x0123456789ABCDEF ✓ (matches!)

Bob sends:
  FINAL {
    session_id: 0x0123456789ABCDEF
  }

Session established successfully!
```

## Complete Flow Example

Let's trace a complete handshake with example values:

```
Alice                                  Bob
-----                                  ---

Generate nonce_A: 0xAAAAAAAA...
node_id_A:        0x11111111...
commitment:       hash(node_id + nonce)

    HELLO ──────────────────────────>
    {
      node_id: 0x11111111...,
      nonce: 0xAAAAAAAA...,
      commitment: 0xCCCCCCCC...
    }
                                      Verify commitment ✓
                                      Generate nonce_B: 0xBBBBBBBB...
                                      node_id_B: 0x22222222...
                                      
                                      Challenge = encrypt(0xAAAAAAAA... + 0xBBBBBBBB...)
    <────────────────────────── RESPONSE
                                      {
                                        node_id: 0x22222222...,
                                        nonce: 0xBBBBBBBB...,
                                        challenge: (encrypted),
                                        challenge_metadata: (...)
                                      }

Decrypt challenge ✓
Verify: 0xAAAAAAAA... + 0xBBBBBBBB... ✓

session_id = XOR(0xAAAAAAAA..., 
                 0xBBBBBBBB..., 
                 0x11111111..., 
                 0x22222222...)[0:8]
           = 0xDDDDDDDDDDDDDDDD

Proof = encrypt(0xDDDDDDDDDDDDDDDD)

    AUTH_PROOF ──────────────────────>
    {
      session_id: 0xDDDDDDDDDDDDDDDD,
      proof: (encrypted),
      proof_metadata: (...)
    }
                                      session_id = XOR(...)[0:8]
                                                 = 0xDDDDDDDDDDDDDDDD
                                      
                                      Decrypt proof → 0xDDDDDDDDDDDDDDDD ✓
                                      Match! ✓
    <────────────────────────────── FINAL
                                      {
                                        session_id: 0xDDDDDDDDDDDDDDDD
                                      }

Session 0xDDDDDDDDDDDDDDDD established!
Both can now create streams and exchange data.
```

## Security Properties

### What the Handshake Achieves

1. **Mutual Authentication**
   - Alice proves she has the shared_seed (decrypts Bob's challenge)
   - Bob proves he has the shared_seed (encrypts valid challenge)

2. **Replay Protection**
   - Fresh nonces each handshake
   - Old HELLO/RESPONSE messages won't work with new nonces
   - Timestamps prevent old messages from being accepted

3. **Man-in-the-Middle (MITM) Resistance**
   - Attacker can't decrypt challenge without shared_seed
   - Attacker can't create valid proof without decrypting challenge
   - Both peers verify each step

4. **Session Uniqueness**
   - Each handshake creates a unique session_id
   - Derived from fresh random nonces + node IDs
   - Cryptographically unlikely to collide

### What Could Go Wrong

**If shared seeds don't match:**

```
Alice has seed:  0xAAAA...
Bob has seed:    0xBBBB...

Alice decrypts challenge → garbage (not alice_nonce + bob_nonce)
Alice's proof will be wrong
Bob rejects AUTH_PROOF
Handshake fails
```

**If network drops a message:**

```
Alice sends HELLO → (lost in network)
Bob never receives it
Timeout occurs
Handshake fails
Alice retries
```

**If attacker intercepts:**

```
Attacker captures: HELLO, RESPONSE, AUTH_PROOF
Attacker tries to decrypt challenge → fails (no shared_seed)
Attacker tries to create valid proof → fails (can't decrypt)
Attacker tries to replay messages → fails (nonces/timestamps checked)
```

## Handshake Timing

Typical handshake duration (on local network):

```
HELLO:      ~1ms  (generate nonce, send)
RESPONSE:   ~5ms  (verify, encrypt challenge, send)
AUTH_PROOF: ~5ms  (decrypt, calculate session_id, encrypt proof, send)
FINAL:      ~5ms  (verify, send confirmation)

Total: ~16ms
```

Over internet (100ms latency):

```
Each round trip: ~200ms
Total: ~400ms (2 round trips)
```

## Comparison with Other Protocols

### TLS 1.3 Handshake

```
Client → ServerHello
Server → ServerHello, Certificate, CertificateVerify, Finished
Client → Finished

1.5 round trips (with 0-RTT: 0 round trips)
Uses deterministic crypto (X25519, Ed25519)
```

### STT Handshake

```
Initiator → HELLO
Responder → RESPONSE
Initiator → AUTH_PROOF
Responder → FINAL

2 round trips (always)
Uses probabilistic crypto (STC)
```

**Trade-off**: STT takes one extra round trip but uses STC exclusively.

## Common Questions

### "Why 4 messages instead of 3?"

The FINAL message confirms Bob successfully verified Alice's proof. Without it, Alice doesn't know if handshake succeeded.

### "Why not use TLS?"

STT uses STC for all cryptography. TLS uses deterministic algorithms incompatible with STC's probabilistic nature.

### "Can handshake fail after FINAL?"

Once FINAL is received, handshake is complete. After that, session-level errors are possible, but not handshake failures.

### "What happens if shared_seed is compromised?"

Attacker can impersonate either peer. Pre-shared seed security is critical. Distribute seeds securely (out-of-band).

## Summary

STT's 4-message handshake:

1. **HELLO**: Initiator commits to nonce and identity
2. **RESPONSE**: Responder encrypts challenge using shared_seed
3. **AUTH_PROOF**: Initiator proves decryption ability and shares session_id
4. **FINAL**: Responder confirms session establishment

This provides mutual authentication, replay protection, and session establishment using only STC cryptography.

## Next Chapter

Now that the session is established through the handshake, we'll explore how data flows through sessions and streams.

Continue to [Chapter 6: Sessions and Connections](06_sessions_connections.md)

---

**Review Questions:**

1. Why does Alice send a commitment in HELLO?
2. What is encrypted in the RESPONSE challenge?
3. How is the session_id calculated?
4. What does Bob verify in AUTH_PROOF?
5. How does the handshake prevent replay attacks?

**Hands-on Exercise:**
Draw a sequence diagram showing the 4 handshake messages with example nonces and session_id calculation.
