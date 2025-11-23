# Appendix B: Frame Format Reference

## Introduction

This appendix provides the complete binary specification for STT frames - the low-level wire format.

**Agnostic Design:** Frame format makes ZERO assumptions about payload content. DATA frames carry encrypted bytes - STT doesn't parse, inspect, or care what those bytes represent (video, files, sensor readings, custom protocols). Only YOU define payload semantics. Custom frame types (0x80-0xFF) let you extend the protocol for ANY binary data format.

## Frame Structure

All STT frames follow this structure:

```
+------------------+
| Frame Header     | Fixed size (varies by frame type)
+------------------+
| Payload          | Variable size (encrypted for data frames)
+------------------+
| Checksum         | 4 bytes (CRC32)
+------------------+
```

## Frame Header (Common Fields)

All frames start with these fields:

```
Offset | Size | Field           | Description
-------|------|-----------------|---------------------------
0      | 1    | version         | Protocol version (0x01 for v0.2.0)
1      | 1    | frame_type      | See Frame Types below
2      | 2    | flags           | Bit flags (endianness, encryption, etc.)
4      | 8    | session_id      | Session identifier (0 for handshake frames)
12     | 2    | stream_id       | Stream identifier (0 for session-level)
14     | 4    | sequence_number | Frame sequence within stream
18     | 4    | payload_length  | Length of payload in bytes
22     | 2    | header_checksum | CRC16 of header (for early validation)
```

**Total header size:** 24 bytes (fixed)

## Frame Types

| Value | Name                 | Description |
|-------|----------------------|-------------|
| 0x01  | HELLO                | Handshake initiation |
| 0x02  | CHALLENGE            | Handshake challenge |
| 0x03  | AUTH_PROOF           | Handshake authentication |
| 0x04  | FINAL                | Handshake completion |
| 0x10  | DATA                 | Application data |
| 0x11  | ACK                  | Acknowledgment |
| 0x12  | NACK                 | Negative acknowledgment (request retransmit) |
| 0x13  | KEEP_ALIVE           | Keep-alive ping |
| 0x14  | KEEP_ALIVE_ACK       | Keep-alive response |
| 0x20  | STREAM_OPEN          | Open new stream |
| 0x21  | STREAM_CLOSE         | Close stream |
| 0x22  | STREAM_FIN           | Stream finished (no more data) |
| 0x30  | SESSION_CLOSE        | Close session |
| 0xFF  | ERROR                | Protocol error |

## Flags Field

Bit flags (16 bits):

```
Bit  | Meaning
-----|---------------------------
0    | Big endian (1) or little endian (0)
1    | Payload encrypted (1) or plaintext (0)
2    | Compression enabled (1) or not (0)
3    | Priority frame (1) or normal (0)
4-15 | Reserved (must be 0)
```

**Current v0.2.0-alpha:**

- Always little endian (bit 0 = 0)
- DATA frames encrypted (bit 1 = 1)
- No compression (bit 2 = 0)
- No priority (bit 3 = 0)

## Handshake Frames

### HELLO Frame (0x01)

```
Common Header (24 bytes)
+------------------+
| our_nonce        | 32 bytes (random)
| node_id          | 32 bytes (peer's node ID)
| timestamp        | 8 bytes (Unix timestamp in ms)
+------------------+
Total payload: 72 bytes
```

### CHALLENGE Frame (0x02)

```
Common Header (24 bytes)
+------------------+
| our_nonce        | 32 bytes (random)
| encrypted_challenge | Variable (STC-encrypted)
|  - Contains:     |
|    - peer's nonce (echoed) |
|    - our_node_id |
|    - timestamp   |
| challenge_metadata | Variable (STC parameters)
+------------------+
```

### AUTH_PROOF Frame (0x03)

```
Common Header (24 bytes)
+------------------+
| session_id       | 8 bytes (derived from nonces)
| encrypted_proof  | Variable (STC-encrypted session_id)
| proof_metadata   | Variable (STC parameters)
+------------------+
```

### FINAL Frame (0x04)

```
Common Header (24 bytes)
+------------------+
| status           | 1 byte (0x00 = success, 0x01+ = error codes)
| message          | Variable (optional error message)
+------------------+
```

## Data Frames

### DATA Frame (0x10)

```
Common Header (24 bytes)
+------------------+
| encrypted_payload | Variable (STC-encrypted application data)
| payload_metadata  | Variable (STC parameters: nonce, tag)
+------------------+
```

**Payload encryption:**

```python
{
    'ciphertext': bytes,  # Encrypted data
    'nonce': bytes,       # STC nonce (uniqueness)
    'tag': bytes,         # Authentication tag
    'metadata': {
        'algorithm': 'STC-v1',
        'seed_version': 1
    }
}
```

### ACK Frame (0x11)

```
Common Header (24 bytes)
+------------------+
| acked_seq_start  | 4 bytes (first sequence number acknowledged)
| acked_seq_end    | 4 bytes (last sequence number acknowledged)
| window_size      | 4 bytes (receiver's available buffer)
+------------------+
Total payload: 12 bytes
```

### NACK Frame (0x12)

```
Common Header (24 bytes)
+------------------+
| missing_seq_count | 2 bytes (number of missing sequences)
| missing_seqs      | Variable (list of 4-byte sequence numbers)
+------------------+
```

## Control Frames

### KEEP_ALIVE Frame (0x13)

```
Common Header (24 bytes)
+------------------+
| timestamp        | 8 bytes (sender's current time)
+------------------+
Total payload: 8 bytes
```

### STREAM_OPEN Frame (0x20)

```
Common Header (24 bytes)
+------------------+
| stream_id        | 2 bytes (requested stream ID)
| max_frame_size   | 4 bytes (preferred frame size for this stream)
| purpose          | Variable (human-readable label, optional)
+------------------+
```

### SESSION_CLOSE Frame (0x30)

```
Common Header (24 bytes)
+------------------+
| reason_code      | 1 byte (see Reason Codes below)
| reason_message   | Variable (human-readable explanation)
+------------------+
```

## Varint Encoding

STT uses **varint** encoding for variable-length integers (e.g., payload_length in some contexts):

**Format:**

- MSB (bit 7) indicates continuation (1 = more bytes, 0 = last byte)
- Remaining 7 bits are data

**Example:**

```
Value 300 (0x012C):
Binary: 0000 0001 0010 1100
Varint: 1010 1100  0000 0010
Bytes:  0xAC       0x02
```

**Current v0.2.0-alpha:** Fixed 4-byte lengths (no varint yet). Planned for v0.6.0 optimization.

## Checksum Calculation

### Header Checksum (CRC16)

```python
import binascii

def calculate_header_checksum(header_bytes):
    """CRC16-CCITT over first 22 bytes of header."""
    return binascii.crc_hqx(header_bytes[:22], 0xFFFF) & 0xFFFF
```

### Frame Checksum (CRC32)

```python
def calculate_frame_checksum(frame_bytes):
    """CRC32 over entire frame (header + payload)."""
    return binascii.crc32(frame_bytes) & 0xFFFFFFFF
```

## Example: Parsing DATA Frame

```python
def parse_data_frame(frame_bytes):
    """Parse DATA frame from bytes."""
    # Header (24 bytes)
    version = frame_bytes[0]
    frame_type = frame_bytes[1]
    flags = int.from_bytes(frame_bytes[2:4], 'little')
    session_id = frame_bytes[4:12]
    stream_id = int.from_bytes(frame_bytes[12:14], 'little')
    sequence_number = int.from_bytes(frame_bytes[14:18], 'little')
    payload_length = int.from_bytes(frame_bytes[18:22], 'little')
    header_checksum = int.from_bytes(frame_bytes[22:24], 'little')
    
    # Validate header checksum
    expected_checksum = calculate_header_checksum(frame_bytes[:22])
    assert header_checksum == expected_checksum, "Header checksum mismatch"
    
    # Payload
    payload = frame_bytes[24:24+payload_length]
    
    # Frame checksum (last 4 bytes)
    frame_checksum = int.from_bytes(frame_bytes[-4:], 'little')
    expected_frame_checksum = calculate_frame_checksum(frame_bytes[:-4])
    assert frame_checksum == expected_frame_checksum, "Frame checksum mismatch"
    
    # Decrypt payload if encrypted
    if flags & 0x02:  # Encrypted bit
        # Use STC to decrypt
        plaintext = STC.decrypt(payload, derived_key)
        return plaintext
    else:
        return payload
```

## Wire Format Examples

### HELLO Frame (hex dump)

```
01 01 00 00 00 00 00 00 | Version, Type, Flags, Session ID (part)
00 00 00 00 00 00 00 00 | Stream ID, Seq, Length (part)
48 00 00 00 A3 F2       | Length, Header CRC
A1 B2 C3 D4 ... (32)    | our_nonce
12 34 56 78 ... (32)    | node_id
E8 03 00 00 00 00 00 00 | timestamp
9F 8E 7D 6C             | Frame CRC32
```

### DATA Frame (hex dump)

```
01 10 02 00 01 23 45 67 | Version, Type, Flags (encrypted), Session ID (part)
89 AB CD EF 00 01 00 00 | Session ID (cont), Stream ID 1, Seq 0
00 10 00 00 10 00 B4 A2 | Length 4096, Header CRC
7A 3F 8B ... (encrypted) | Encrypted payload (4096 bytes)
12 34 56 78             | Frame CRC32
```

## Protocol Version Compatibility

**Current version:** 0x01 (v0.2.0-alpha)

**Future versions:**

- 0x02: v0.4.0 (DHT extensions)
- 0x03: v0.6.0 (priority, QoS)

**Backward compatibility:**

- Peers must have matching version (checked in HELLO)
- Future: Negotiation (lowest common version)

## Key Takeaways

- All frames: 24-byte header + variable payload + 4-byte checksum
- Frame types: Handshake (0x01-0x04), Data (0x10-0x14), Control (0x20-0x30)
- Flags: Endianness, encryption, compression, priority
- Checksums: CRC16 for header, CRC32 for entire frame
- Payload: Encrypted for DATA frames (STC), plaintext for control frames
- Sequence numbers: Track ordering per stream
- Session ID: 8 bytes, derived from handshake nonces (XOR mixing)
