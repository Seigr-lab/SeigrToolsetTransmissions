# Chapter 13: Security Model

## Introduction

This chapter analyzes STT's security properties, threat model, and best practices for secure deployments.

## Security Properties

### What STT Provides

✅ **Confidentiality:** All payloads encrypted with STC (eavesdroppers cannot read data)  
✅ **Integrity:** Authentication tags detect tampering (modified frames rejected)  
✅ **Authentication:** Only peers with correct seed can establish sessions  
✅ **Replay Protection:** Nonces prevent replaying old handshake messages  
✅ **Agnostic Security:** Encryption works on ANY binary data (video, sensors, files, protocols)  

### What STT Does NOT Provide

❌ **Forward Secrecy:** Compromised seed exposes all past sessions (deterministic from seed)  
❌ **Anonymous Communication:** Peers must know each other (shared seed)  
❌ **Public Key Infrastructure:** No certificates, no certificate authorities  
❌ **Post-Quantum Security:** Vulnerable to quantum computers (STC not quantum-resistant)  

## Threat Model

### Assumed Attacker Capabilities

**Network Attacker (Passive):**

- Can observe all network traffic (sniffing)
- Cannot modify packets
- Cannot compromise endpoints

**STT protects against:** Eavesdropping (encryption), traffic analysis of content (encrypted payloads)

**Network Attacker (Active):**

- Can observe and modify packets
- Can inject fake packets
- Cannot compromise endpoints

**STT protects against:** Tampering (integrity tags), impersonation (authentication), replay attacks (nonces)

**Endpoint Attacker:**

- Full access to one endpoint (compromised computer)
- Can read memory, disk, keys

**STT CANNOT protect against:** Stolen seeds, compromised application, malware on endpoint

### Out of Scope

**Not protected:**

- **Traffic analysis:** Attacker can see "Alice and Bob are communicating" (metadata visible)
- **Denial of Service:** Attacker can flood ports, exhaust resources
- **Social engineering:** Attacker tricks user into sharing seed
- **Physical security:** Attacker steals device with seed

## Cryptographic Analysis

### STC Security

**STC (Seigr Temporal Cryptography):**

- Symmetric encryption (shared seed)
- Deterministic key derivation (same seed → same keys)
- No forward secrecy (key compromise exposes past sessions)

**Strength:**

- Assumes seed has 256 bits of entropy (cryptographically random)
- Equivalent to AES-256 security (if seed secure)

**Weakness:**

- Seed compromise is catastrophic (all past/future sessions exposed)
- No key rotation within session (deterministic)

### Nonce Usage

**Handshake nonces:**

- 32 bytes (256 bits) cryptographically random
- Generated per-handshake (never reused)
- Prevent replay attacks
- Contribute to session ID (uniqueness)

**Why secure:**

- Random from `secrets.token_bytes()` (OS entropy)
- Large enough to avoid collisions (2^256 possibilities)

### Session ID Derivation

```python
session_id = (nonce_xor + node_xor)[:8]
```

**Security note:**

- XOR is NOT cryptographic operation here (just mixing)
- Session ID is **not secret** (sent in clear for routing)
- Only used for session identification, not authentication

**Important:** XOR in session ID derivation is **not encryption**!

## Seed Management

### Secure Generation

✅ **DO:**

```python
import secrets
seed = secrets.token_bytes(32)  # Cryptographically secure
```

❌ **DON'T:**

```python
import random
seed = bytes([random.randint(0, 255) for _ in range(32)])  # Predictable!
```

### Secure Storage

**Options (best to worst):**

1. **Hardware Security Module (HSM):** Dedicated cryptographic hardware
2. **OS Keychain:** macOS Keychain, Windows Credential Manager
3. **Encrypted file:** `cryptography` library with key derivation
4. **Environment variable:** Better than hardcoding, but visible in `ps`
5. **Hardcoded (DON'T):** Worst - seed in source code

**Example (encrypted file):**

```python
from cryptography.fernet import Fernet

# One-time: Generate key (protect this!)
key = Fernet.generate_key()
# Save key securely (e.g., keychain)

# Encrypt seed
f = Fernet(key)
encrypted_seed = f.encrypt(seed)
with open('seed.enc', 'wb') as file:
    file.write(encrypted_seed)

# Decrypt seed (in application)
with open('seed.enc', 'rb') as file:
    encrypted_seed = file.read()
seed = f.decrypt(encrypted_seed)
```

### Secure Distribution

**Share seed securely (one-time, out-of-band):**

✅ **Good methods:**

- In-person exchange (write on paper, QR code)
- End-to-end encrypted messaging (Signal, Wire)
- Hardware token (USB drive, handed physically)
- Encrypted email (GPG/PGP - if you know how)

❌ **BAD methods:**

- Unencrypted email (readable by email servers)
- SMS (logged by carriers, not encrypted)
- Public chat (anyone can see)
- HTTP (unencrypted over network)

### Seed Rotation

**Why rotate:**

- Limit exposure window (compromised seed only affects period it was used)
- Good practice (like changing passwords)

**When to rotate:**

- **Immediately:** Suspected compromise (employee leaves, device stolen)
- **Periodically:** Every 6-12 months (normal security hygiene)
- **Never:** Convenience (accept risk)

**How to rotate:**

1. Generate new seed
2. Distribute to all peers (securely)
3. Update all applications
4. Test new seed works
5. Decommission old seed
6. **Keep old seed temporarily** (decrypt old recordings if needed)

## Attack Scenarios

### Passive Eavesdropping

**Attacker:** Sniffs all packets between Alice and Bob

**What attacker sees:**

- Encrypted STT frames (binary blobs)
- Frame sizes, timing
- IP addresses, ports

**What attacker CANNOT see:**

- Plaintext data (STC encrypted)
- Content of messages

**STT protection:** ✅ Effective (STC encryption)

### Active Man-in-the-Middle (MitM)

**Attacker:** Intercepts and modifies packets

**Scenario:**

1. Alice sends handshake HELLO to Bob
2. Attacker intercepts, modifies nonce
3. Bob receives modified HELLO

**STT protection:** ✅ Effective

- Bob's challenge encrypted with seed
- Attacker can't decrypt (no seed)
- Alice's AUTH_PROOF fails (wrong nonce)
- Handshake fails

**Limitation:** If attacker has seed, MitM possible (but then attacker can directly decrypt anyway)

### Replay Attack

**Attacker:** Records handshake, replays later

**Scenario:**

1. Attacker records Alice→Bob handshake packets
2. Days later, replays packets

**STT protection:** ✅ Effective

- Nonces are fresh random (never reused)
- Replayed HELLO has old nonce
- Bob generates new challenge (different from original)
- AUTH_PROOF won't match (calculated with different nonces)
- Handshake fails

### Compromised Seed

**Attacker:** Obtains seed (stolen from disk, memory dump, social engineering)

**STT protection:** ❌ NONE

- Attacker can decrypt all past sessions (if recorded)
- Attacker can impersonate peers in future sessions
- Attacker can MitM future sessions

**Mitigation:**

- Secure seed storage (HSM, encrypted files)
- Seed rotation (limit exposure window)
- **No technical solution** (pre-shared secret model)

### Denial of Service (DoS)

**Attacker:** Floods port with junk packets

**STT protection:** ⚠️ Limited

- Invalid frames rejected early (checksum, parsing)
- But CPU spent processing junk
- Can exhaust resources (memory, CPU)

**Mitigation:**

- Firewall rules (rate limiting)
- IP whitelisting (only known peers)
- **Current:** Seed requirement provides authentication

## Best Practices

### Deployment Security

✅ **DO:**

- Generate seeds cryptographically (`secrets.token_bytes()`)
- Store seeds encrypted (HSM, keychain, encrypted files)
- Use different seeds for different peer pairs (isolation)
- Rotate seeds periodically (every 6-12 months)
- Use firewall rules (limit access to STT ports)
- Monitor for anomalies (unexpected connections)
- Keep STT updated (security patches)

❌ **DON'T:**

- Reuse seeds across environments (dev/staging/prod)
- Hardcode seeds in source code (visible in repos)
- Share seeds over insecure channels (email, SMS)
- Use predictable seeds ("password123")
- Ignore logs (detect attacks)
- Run as root (principle of least privilege)

### Network Security

**Firewall rules (example using `ufw`):**

```bash
# Allow only specific peer IP
sudo ufw allow from 10.0.1.5 to any port 8080 proto udp

# Deny all others
sudo ufw deny 8080/udp
```

**IP whitelisting in STT:**

```python
# Manual implementation (application layer)
allowed_peers = {'10.0.1.5', '10.0.1.6'}

async def handle_connection(peer_addr, peer_id):
    if peer_addr[0] not in allowed_peers:
        raise PermissionError("Peer not whitelisted")
    # Proceed with connection
```

### Defense in Depth

**Layered security:**

1. **Physical:** Secure hardware (locked server rooms)
2. **Network:** Firewall rules (limit access)
3. **Transport:** STT encryption (STC)
4. **Application:** Input validation (don't trust peer data)
5. **System:** OS hardening (SELinux, AppArmor)

**Don't rely on one layer** - assume others may fail.

### Incident Response

**If seed compromised:**

1. **Immediately:** Stop using compromised seed
2. **Rotate:** Generate new seed, distribute securely
3. **Investigate:** How was seed compromised? (Fix root cause)
4. **Assess damage:** What data was exposed? (Notify affected parties)
5. **Prevent:** Improve storage (HSM), access controls

## Compliance Considerations

### GDPR (EU)

**STT implications:**

- Encrypted data-in-transit (satisfies "appropriate technical measures")
- No forward secrecy (potential concern for "privacy by design")
- Peer IP addresses in logs (personal data - handle carefully)

**Recommendations:**

- Document seed management procedures
- Implement data retention policies (rotate/delete old seeds)
- Encrypt logs (peer IPs are personal data)

### HIPAA (US Healthcare)

**STT implications:**

- Encryption required for PHI (Protected Health Information) in transit ✅
- No inherent access controls (application must implement)
- Audit logging (STT provides session logs)

**Recommendations:**

- Use STT for PHI transmission (satisfies encryption requirement)
- Implement access controls in application layer
- Enable detailed logging, retain per HIPAA requirements

### PCI-DSS (Payment Cards)

**STT implications:**

- Encryption required for cardholder data ✅
- TLS alternative (STT not TLS, but STC provides encryption)
- No forward secrecy (may not satisfy strict interpretations)

**Recommendations:**

- Check with QSA (Qualified Security Assessor) if STT acceptable
- May need compensating controls (seed rotation, HSM storage)
- Alternative: Use STT with TLS (WebSocket over WSS)

## Research Areas

**Future security research directions:**

### Key Rotation (Ratcheting)

**Ratcheting keys within session provides forward secrecy:**

- Every N frames, derive new key from previous
- Compromised key doesn't expose past communication
- Signal/Double Ratchet inspiration

**Challenges:**

- Complexity: Session state management
- Out-of-order delivery: Need key history
- Performance: Frequent key derivation overhead

**Status:** Research phase - not implemented

### Post-Quantum Cryptography

**Quantum-resistant algorithms:**

- Replace current STC with post-quantum primitives
- NIST finalists: Kyber (lattice-based), Dilithium (signatures)
- Protects against future quantum computers

**Challenges:**

- STC.hash is NOT post-quantum (uses SHA-256)
- Need quantum-resistant hash function
- Performance: Post-quantum algos are slower

**Status:** Awaiting STC post-quantum support

### Certificate-Based Authentication

**Hybrid authentication (optional):**

- Pre-shared seed + certificates (defense in depth)
- Trust On First Use (TOFU) model
- PKI infrastructure for large deployments

**Challenges:**

- Complexity: Certificate management overhead
- Centralization: PKI introduces trust anchors
- Conflicts with self-sovereign philosophy

**Status:** Research phase - may never implement

## Limitations and Honest Assessment

**STT is NOT:**

- ❌ Zero-trust (requires pre-shared seed - trust established)
- ❌ Forward-secret (no ephemeral keys - seed compromise exposes all)
- ❌ Post-quantum (not quantum-resistant - yet)
- ❌ Anonymous (peers know each other - not Tor-like)

**STT IS:**

- ✅ Encrypted (STC provides confidentiality)
- ✅ Authenticated (only peers with seed connect)
- ✅ Integrity-protected (tampering detected)
- ✅ Suitable for private networks (known peers, pre-authorized)

**Know the trade-offs** - choose appropriate protocol for your threat model.

## Key Takeaways

- **Confidentiality:** STC encrypts all payloads (eavesdropping protected)
- **Integrity:** Authentication tags detect tampering
- **Authentication:** Pre-shared seed required (only authorized peers connect)
- **No forward secrecy:** Compromised seed exposes all sessions
- **Seed management critical:** Generate securely, store encrypted, distribute out-of-band, rotate periodically
- **Threat model:** Protects against network attackers, NOT endpoint compromise
- **Best practices:** HSM/encrypted storage, firewall rules, defense in depth, incident response plan
- **Limitations:** Not anonymous, not forward-secret, not post-quantum (yet)
- **Research areas:** Key rotation, post-quantum crypto, certificate auth (not scheduled)
