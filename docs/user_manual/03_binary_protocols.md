# Chapter 3: Binary Protocols and Data

## Introduction

STT uses binary protocols rather than text-based protocols. This chapter explains what that means, why it matters, and how to work with binary data.

## What is Binary Data?

### At the Computer Level

Computers store and process everything as binary: sequences of 0s and 1s.

**Example:**

```
The letter 'A' in binary: 01000001
The number 65 in binary:  01000001
```

These are the same! Context determines meaning.

### Bytes and Bits

- **Bit**: A single 0 or 1
- **Byte**: 8 bits together (e.g., 01000001)
- **Hexadecimal**: A convenient way to write bytes (e.g., 0x41 for 01000001)

**Conversion example:**

```
Binary:      01010011 01010100
Hexadecimal: 0x53 0x54
Text (ASCII): "ST"
```

These are three ways of representing the same data.

## Text vs Binary Protocols

### Text-Based Protocols

Examples: HTTP, SMTP, FTP (control channel)

**How they work:**

```
Client sends: "GET /index.html HTTP/1.1\r\nHost: example.com\r\n\r\n"
Server sends: "HTTP/1.1 200 OK\r\nContent-Length: 1234\r\n\r\n<html>..."
```

Everything is readable text (strings of characters).

**Advantages:**

- Human-readable (you can read it directly)
- Easy to debug (use telnet or text editors)
- Simple to implement (string manipulation)

**Disadvantages:**

- Larger size (text is verbose)
- Slower parsing (need to parse strings)
- Ambiguous (what if data contains special characters?)

### Binary Protocols

Examples: STT, HTTP/2, WebSocket, BitTorrent

**How they work:**

```
Client sends: [0x53][0x54][0x01][0x00000001][0x00][0x0A][...]
```

Data is raw bytes with structured meaning.

**Advantages:**

- Smaller size (compact representation)
- Faster processing (direct byte manipulation)
- Precise (no ambiguity, each byte has defined meaning)

**Disadvantages:**

- Not human-readable (need tools to inspect)
- Harder to debug (can't just read it)
- Requires precise specification (byte-level detail)

## STT's Binary Format

### Frame Structure

STT frames have this binary structure:

```
+--------+------+------------+-----------+----------+-------+
| Magic  | Type | Session ID | Stream ID | Sequence | Flags |
| 2 bytes| 1 byte| 8 bytes   | varint    | varint   | 1 byte|
+--------+------+------------+-----------+----------+-------+
        ↓
+---------------+---------+--------------------+-----------+
| Payload Length| Payload | Crypto Meta Length | Crypto Meta|
| varint        | variable| varint             | variable  |
+---------------+---------+--------------------+-----------+
```

**Let's break this down:**

#### Magic Bytes (2 bytes)

```
0x53 0x54  (ASCII "ST")
```

Purpose: Identify this as an STT frame (not random garbage).

#### Type (1 byte)

```
0x01 = Handshake frame
0x02 = Data frame
0x03 = Control frame
0x04 = Stream control frame
0x05 = Auth frame
```

Purpose: Tells receiver how to interpret the frame.

#### Session ID (8 bytes)

```
Example: 0x01 0x23 0x45 0x67 0x89 0xAB 0xCD 0xEF
```

Purpose: Identifies which session this frame belongs to.

#### Stream ID (varint)

```
Stream 1:    0x01             (1 byte)
Stream 127:  0x7F             (1 byte)
Stream 300:  0xAC 0x02        (2 bytes)
Stream 16384: 0x80 0x80 0x01  (3 bytes)
```

Purpose: Identifies which stream within the session.

**Varint explained**: Small numbers use fewer bytes. This saves space since most applications use low stream IDs.

#### Sequence Number (varint)

```
Sequence 0:   0x00
Sequence 100: 0x64
Sequence 1000: 0xE8 0x07
```

Purpose: Ordering - ensures data arrives in correct order.

#### Flags (1 byte)

```
Bit 0: Final frame in stream
Bit 1: Error condition
Bit 2-7: Reserved
```

Purpose: Special conditions or metadata.

#### Payload

```
Encrypted data (variable length)
```

Purpose: Your actual data, encrypted with STC.

### Varint Encoding Explained

Varint (variable-length integer) saves space:

**Standard integer (always 4 bytes):**

```
1:      0x00 0x00 0x00 0x01  (4 bytes)
127:    0x00 0x00 0x00 0x7F  (4 bytes)
300:    0x00 0x00 0x01 0x2C  (4 bytes)
```

**Varint (uses only bytes needed):**

```
1:      0x01             (1 byte)
127:    0x7F             (1 byte)
300:    0xAC 0x02        (2 bytes)
```

**How it works:**

- If the high bit is 0, this is the last byte
- If the high bit is 1, more bytes follow
- The other 7 bits contain data

**Example: Encoding 300**

```
300 in binary: 100101100

Split into 7-bit groups: 0000010 0101100
Reverse order: 0101100 0000010
Add continuation bits: 10101100 00000010
Result: 0xAC 0x02
```

You don't need to understand the encoding details - STT handles this automatically. Just know that small numbers = small size.

## STT Binary Serialization

### Supported Data Types

STT can serialize these Python types to binary:

**Basic Types:**

- `None` → 0x00
- `False` → 0x01
- `True` → 0x02

**Numbers:**

- `int` (signed/unsigned, 8/16/32/64 bit) → 0x10-0x17
- `float` (32 bit) → 0x20
- `float` (64 bit) → 0x21

**Bytes and Strings:**

- `bytes` → 0x30 + length + data
- `str` (UTF-8) → 0x31 + length + UTF-8 bytes

**Collections:**

- `list` → 0x40 + length + items
- `dict` → 0x41 + length + key-value pairs

### Example: Encoding a Dict

Python dict:

```python
{'name': 'Alice', 'age': 30}
```

Binary representation:

```
0x41                    # Dict type tag
0x02                    # 2 items
  0x31 0x04 'name'      # String key "name" (0x31 = string, 0x04 = length 4)
  0x31 0x05 'Alice'     # String value "Alice"
  0x31 0x03 'age'       # String key "age"
  0x11 0x1E             # Int8 value 30 (0x11 = int8, 0x1E = 30)
```

**Why this format?**

- Compact (no wasted space)
- Deterministic (same data = same bytes)
- No parsing ambiguity (exact byte meaning)

### Deterministic Serialization

STT ensures that serializing the same data always produces the same bytes:

**Dictionary keys are sorted:**

```python
{'b': 2, 'a': 1}  →  [always serialized as] → {'a': 1, 'b': 2}
```

This matters for cryptographic hashes - we need consistent bytes for consistent hashes.

## Working with Binary Data

### Reading Binary (Hex Dump)

When debugging, you'll see hex dumps:

```
0000: 53 54 01 01 23 45 67 89  AB CD EF 01 00 00 05 48  ST..#Eg........H
0010: 65 6C 6C 6F                                       ello
```

**How to read this:**

- Left column: Byte offset (position in data)
- Middle columns: Bytes in hexadecimal
- Right column: ASCII representation (. = non-printable)

**Example breakdown:**

```
53 54 → Magic bytes "ST"
01    → Type 0x01 (Handshake)
01 23 45 67 89 AB CD EF → Session ID
01    → Stream ID 1 (varint)
00    → Sequence 0 (varint)
00    → Flags 0
05    → Payload length 5 (varint)
48 65 6C 6C 6F → "Hello" (payload)
```

### Inspecting STT Frames

To inspect STT frames, you can:

1. **Use STT's built-in tools:**

```python
frame = STTFrame.from_bytes(binary_data)
print(f"Type: {frame.frame_type}")
print(f"Session: {frame.session_id.hex()}")
print(f"Stream: {frame.stream_id}")
```

2. **Use hexdump utilities:**

```bash
# Linux/Mac
hexdump -C frame.bin

# Python
import binascii
print(binascii.hexlify(binary_data))
```

3. **Use Wireshark** (future: when STT dissector exists)

## Size Comparisons

Let's compare text vs binary for a typical message:

### Text Protocol (JSON)

```json
{
  "type": "data",
  "session": "0123456789ABCDEF",
  "stream": 1,
  "sequence": 42,
  "data": "Hello"
}
```

**Size: ~120 bytes** (with whitespace and quotes)

### Binary Protocol (STT Frame)

```
Magic:    0x53 0x54         (2 bytes)
Type:     0x02              (1 byte)
Session:  0x01...0xEF       (8 bytes)
Stream:   0x01              (1 byte, varint)
Sequence: 0x2A              (1 byte, varint)
Flags:    0x00              (1 byte)
Length:   0x05              (1 byte, varint)
Data:     "Hello"           (5 bytes)
Meta:     (varies)          (~16 bytes for crypto)
```

**Size: ~36 bytes**

**Savings: 70%** (36 bytes vs 120 bytes)

Over millions of messages, this adds up significantly.

## Practical Implications

### What This Means for You

1. **You can't "read" STT traffic directly**
   - Need tools to inspect binary frames
   - Can't use telnet or curl
   - Debugging requires STT-aware tools

2. **Data is transmitted efficiently**
   - Smaller bandwidth usage
   - Faster transmission
   - Lower latency

3. **No serialization options**
   - Must use STT's binary format
   - Can't substitute JSON or XML
   - Format is part of the protocol

4. **Exact byte-level compatibility**
   - All STT implementations must agree on format
   - Versioning is critical
   - No "loose" parsing

## Common Questions

### "Can I use JSON instead of binary?"

**No.** STT's binary format is integral to the protocol. You can put JSON inside the encrypted payload, but the frame structure is always binary.

### "How do I debug if I can't read the bytes?"

Use STT's logging and inspection tools. The library provides methods to decode frames into human-readable representations.

### "Is binary more secure than text?"

Not inherently. Security comes from encryption, not encoding. Binary just makes it impossible to accidentally leak data in readable form.

### "What if the binary format changes?"

STT includes version numbers in frames. Different versions can coexist. When the format changes, the version number increments.

## Summary

- Binary protocols use raw bytes instead of text strings
- STT frames have a precise binary structure with specific byte meanings
- Varint encoding saves space for small numbers
- Binary serialization is compact, deterministic, and unambiguous
- Tools are needed to inspect binary data
- The efficiency gains justify the added complexity

## Next Chapter

Now that you understand binary protocols, we'll explore encryption - how STT keeps your data secure using STC.

Continue to [Chapter 4: Understanding Encryption](04_understanding_encryption.md)

---

**Review Questions:**

1. What are the magic bytes in an STT frame and why do they exist?
2. How does varint encoding save space?
3. Why is deterministic serialization important?
4. What's the approximate size difference between JSON and STT binary for a small message?

**Hands-on Exercise:**
Given these bytes: `53 54 02 01 23 45 67 89 AB CD EF 01 00 00`

1. Identify the magic bytes
2. What is the frame type?
3. What is the session ID?
4. What is the stream ID?
