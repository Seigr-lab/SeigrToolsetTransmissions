# Appendix D: Error Code Reference

## Introduction

Complete listing of all STT error codes, causes, and recovery actions.

**Agnostic Design:** Error codes are transport-level ONLY. Errors describe protocol failures (handshake timeout, stream closed, frame corruption), never data-level issues. STT will NEVER raise "InvalidVideoCodecError" or "CorruptedFileError" - those are application-layer concerns. If you receive corrupted application data, STT delivered valid encrypted bytes - YOUR code validates data semantics.

## Error Code Format

STT errors follow hierarchy:

```
Error Code (8-bit): XXYY
  XX = Category (connection, session, stream, protocol)
  YY = Specific error within category
```

## Connection Errors (0x01XX)

### 0x0101: CONNECTION_TIMEOUT

**Meaning:** Handshake did not complete within timeout period

**Causes:**

- Peer offline/crashed
- Network unreachable (firewall, routing)
- Slow network (high latency)
- Wrong IP/port

**Recovery:**

- Retry with exponential backoff
- Increase timeout for slow networks
- Verify peer reachability (ping, traceroute)
- Try fallback transport (WebSocket)

**Example:**

```python
try:
    session = await node.connect(peer_addr, peer_id, timeout=10.0)
except ConnectionTimeoutError as e:
    print(f"Error code: {e.code:#06x}")  # 0x0101
    # Retry or try WebSocket
```

### 0x0102: CONNECTION_REFUSED

**Meaning:** Peer actively rejected connection

**Causes:**

- Peer not listening on port
- Firewall blocking
- Port forwarding misconfigured
- Wrong port number

**Recovery:**

- Verify peer is running (`netstat -tulpn | grep PORT`)
- Check firewall rules
- Verify port forwarding (if behind NAT)
- Confirm correct port in configuration

### 0x0103: AUTHENTICATION_FAILED

**Meaning:** Handshake authentication failed (wrong seed)

**Causes:**

- Mismatched shared_seed (most common)
- Seed corruption
- Wrong peer_node_id

**Recovery:**

- **No automatic recovery** - fix configuration
- Verify both peers use identical seed
- Check seed not corrupted (hex encoding issues)
- Confirm peer_node_id matches

### 0x0104: NETWORK_UNREACHABLE

**Meaning:** Cannot route packets to peer

**Causes:**

- No network connectivity
- Invalid IP address
- Routing issues

**Recovery:**

- Check network connectivity (ping gateway)
- Verify IP address correct
- Check routing tables
- Try different network interface

### 0x0105: PROTOCOL_VERSION_MISMATCH

**Meaning:** Incompatible STT protocol versions

**Causes:**

- Peer using different STT version
- Outdated client/server

**Recovery:**

- Upgrade to matching versions

## Session Errors (0x02XX)

### 0x0201: SESSION_CLOSED

**Meaning:** Session terminated (gracefully or error)

**Causes:**

- Peer called `session.close()` (graceful)
- Keep-alive timeout (peer died)
- Protocol error (invalid frames)
- Network failure

**Recovery:**

- If graceful: Expected, no recovery needed
- If timeout: Reconnect (new session)
- If error: Check logs, fix protocol issue

**Reason codes (embedded in error):**

- `'graceful'`: Normal close
- `'timeout'`: Keep-alive timeout
- `'error'`: Protocol error
- `'auth_failure'`: Post-handshake auth issue

### 0x0202: SESSION_TIMEOUT

**Meaning:** Keep-alive timeout exceeded

**Causes:**

- Peer crashed/hung
- Network partition (complete loss)
- Peer overloaded (not responding)

**Recovery:**

- Reconnect (new session)
- Check peer health (logs, monitoring)
- Adjust keep_alive_timeout for unstable networks

### 0x0203: TOO_MANY_SESSIONS

**Meaning:** Exceeded max_concurrent_sessions limit

**Causes:**

- Too many active sessions
- Session leaks (not closing properly)

**Recovery:**

- Close unused sessions
- Increase max_concurrent_sessions (if resources permit)
- Fix session leaks (ensure `session.close()` called)

### 0x0204: SESSION_NOT_FOUND

**Meaning:** Session ID not recognized

**Causes:**

- Session expired/closed
- Invalid session ID in frame
- Out-of-order frame (session closed between send/receive)

**Recovery:**

- Reconnect (create new session)
- Check session state before using

## Stream Errors (0x03XX)

### 0x0301: STREAM_CLOSED

**Meaning:** Stream terminated

**Causes:**

- Peer called `stream.close()` (normal)
- Session closed (all streams close)
- Stream timeout (no activity)

**Recovery:**

- If expected (finite transfer): No recovery needed
- If unexpected: Check logs, may indicate session issue
- Open new stream if needed

### 0x0302: TOO_MANY_STREAMS

**Meaning:** Exceeded max_concurrent_streams limit

**Causes:**

- Too many open streams on session
- Stream leaks (not closing)

**Recovery:**

- Close unused streams
- Increase max_concurrent_streams
- Fix stream leaks (ensure `stream.close()` called)

### 0x0303: STREAM_ID_CONFLICT

**Meaning:** Stream ID already in use

**Causes:**

- Manually specified stream_id already used
- Race condition (both peers open same ID simultaneously)

**Recovery:**

- Use auto-assignment (don't specify stream_id)
- Coordinate stream IDs (e.g., client uses even, server uses odd)

### 0x0304: FLOW_CONTROL_VIOLATION

**Meaning:** Sender exceeded receiver's advertised window

**Causes:**

- Software bug (sender ignored backpressure)
- Corrupted flow control messages

**Recovery:**

- Report bug (should not happen in correct implementation)
- Restart session

## Protocol Errors (0x04XX)

### 0x0401: INVALID_FRAME

**Meaning:** Frame structure invalid

**Causes:**

- Corrupted packet (checksum mismatch)
- Software bug (malformed frame generation)
- Incompatible protocol versions

**Recovery:**

- Frame discarded, sender retransmits (automatic)
- If repeated: Check network quality (corruption rate)
- If software bug: Report issue, upgrade STT

### 0x0402: ENCRYPTION_ERROR

**Meaning:** STC encryption/decryption failed

**Causes:**

- Corrupted seed
- STC library bug
- Memory corruption

**Recovery:**

- Restart application
- Verify seed integrity
- Report bug if reproducible

### 0x0403: CHECKSUM_MISMATCH

**Meaning:** Frame checksum invalid

**Causes:**

- Network corruption (bit flips)
- Software bug (incorrect calculation)

**Recovery:**

- Frame discarded, retransmitted (automatic)
- High rate (>5%): Check network hardware (bad cable, interference)

### 0x0404: UNKNOWN_FRAME_TYPE

**Meaning:** Unrecognized frame type

**Causes:**

- Protocol version mismatch
- Corrupted frame type field
- Unknown frame type

**Recovery:**

- Verify protocol versions match
- Upgrade to latest STT version
- Frame discarded (non-fatal)

### 0x0405: HANDSHAKE_FAILURE

**Meaning:** Generic handshake error

**Causes:**

- Various handshake issues (see sub-codes)

**Sub-codes:**

- 0x0405_01: NONCE_REUSE (security violation)
- 0x0405_02: TIMESTAMP_EXPIRED (replay attack?)
- 0x0405_03: CHALLENGE_DECRYPT_FAILED (wrong seed)
- 0x0405_04: PROOF_VERIFICATION_FAILED (wrong session_id)

**Recovery:**

- Most: Retry handshake (transient issue)
- Nonce reuse: Serious bug, report
- Decrypt failed: Fix seed mismatch

## Transport Errors (0x05XX)

### 0x0501: UDP_SEND_FAILED

**Meaning:** UDP socket send failed

**Causes:**

- Network interface down
- OS buffer full
- Permissions issue

**Recovery:**

- Check network connectivity
- Retry send
- Increase send_buffer_size

### 0x0502: WEBSOCKET_CLOSED

**Meaning:** WebSocket connection closed

**Causes:**

- Peer closed connection (normal or error)
- Network failure
- Proxy dropped connection

**Recovery:**

- Reconnect (new session)
- Check peer logs for reason
- Verify proxy (if used)

### 0x0503: WEBSOCKET_HANDSHAKE_FAILED

**Meaning:** WebSocket upgrade failed

**Causes:**

- Server not WebSocket-capable
- Proxy blocking upgrade
- TLS certificate invalid (if WSS)

**Recovery:**

- Verify server supports WebSocket
- Check proxy configuration
- Verify TLS cert (if using WSS)

### 0x0504: TLS_ERROR

**Meaning:** TLS handshake/verification failed

**Causes:**

- Invalid certificate
- Cert expired
- Hostname mismatch
- Untrusted CA

**Recovery:**

- Verify certificate validity
- Check system time (cert dates)
- Update CA certificates

## Application Errors (0x06XX)

### 0x0601: TIMEOUT

**Meaning:** Generic operation timeout

**Causes:**

- Send timeout (flow control backpressure)
- Receive timeout (no data available)
- Operation took too long

**Recovery:**

- Increase timeout (for slow operations)
- Check flow control (receiver slow?)
- Retry operation

### 0x0602: BUFFER_OVERFLOW

**Meaning:** Internal buffer exceeded

**Causes:**

- Receiver too slow (backpressure)
- Sender too fast
- Insufficient buffer size

**Recovery:**

- Increase buffer sizes (recv_buffer_size, stream_recv_buffer)
- Slow down sender
- Consume data faster (receiver)

### 0x0603: RESOURCE_EXHAUSTED

**Meaning:** System resources depleted

**Causes:**

- Out of memory
- Too many file descriptors
- CPU overloaded

**Recovery:**

- Reduce load (fewer sessions/streams)
- Increase system limits (`ulimit -n`)
- Add resources (RAM, CPU)

## Error Handling Patterns

### Retry with Backoff

```python
async def retry_on_timeout(func, max_retries=5):
    delay = 1.0
    for attempt in range(max_retries):
        try:
            return await func()
        except ConnectionTimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
                delay *= 2
            else:
                raise
```

### Graceful Degradation

```python
try:
    session = await node.connect(peer_addr, peer_id, transport='udp')
except ConnectionRefusedError:
    # Fallback to WebSocket
    session = await node.connect(peer_addr, peer_id, transport='websocket')
```

### Circuit Breaker

```python
if error_rate > 0.5:  # 50% errors
    # Stop trying, circuit open
    raise Exception("Circuit breaker open")
```

## Logging Error Details

```python
import logging

try:
    session = await node.connect(peer_addr, peer_id)
except STTError as e:
    logging.error(
        f"Connection failed: code={e.code:#06x}, "
        f"message={e.message}, peer={peer_id}"
    )
    # Include context for debugging
```

## Error Code Summary Table

| Code | Name | Category | Recoverable |
|------|------|----------|-------------|
| 0x0101 | CONNECTION_TIMEOUT | Connection | Yes (retry) |
| 0x0102 | CONNECTION_REFUSED | Connection | Yes (fix config) |
| 0x0103 | AUTHENTICATION_FAILED | Connection | No (fix seed) |
| 0x0104 | NETWORK_UNREACHABLE | Connection | Yes (check network) |
| 0x0105 | PROTOCOL_VERSION_MISMATCH | Connection | No (upgrade) |
| 0x0201 | SESSION_CLOSED | Session | Yes (reconnect) |
| 0x0202 | SESSION_TIMEOUT | Session | Yes (reconnect) |
| 0x0203 | TOO_MANY_SESSIONS | Session | Yes (close some) |
| 0x0204 | SESSION_NOT_FOUND | Session | Yes (reconnect) |
| 0x0301 | STREAM_CLOSED | Stream | Yes (reopen) |
| 0x0302 | TOO_MANY_STREAMS | Stream | Yes (close some) |
| 0x0303 | STREAM_ID_CONFLICT | Stream | Yes (auto-assign) |
| 0x0304 | FLOW_CONTROL_VIOLATION | Stream | No (bug) |
| 0x0401 | INVALID_FRAME | Protocol | Auto (retransmit) |
| 0x0402 | ENCRYPTION_ERROR | Protocol | No (serious) |
| 0x0403 | CHECKSUM_MISMATCH | Protocol | Auto (retransmit) |
| 0x0404 | UNKNOWN_FRAME_TYPE | Protocol | Partial (discard) |
| 0x0405 | HANDSHAKE_FAILURE | Protocol | Yes (retry) |
| 0x0501 | UDP_SEND_FAILED | Transport | Yes (retry) |
| 0x0502 | WEBSOCKET_CLOSED | Transport | Yes (reconnect) |
| 0x0503 | WEBSOCKET_HANDSHAKE_FAILED | Transport | Yes (fix config) |
| 0x0504 | TLS_ERROR | Transport | Yes (fix cert) |
| 0x0601 | TIMEOUT | Application | Yes (retry/increase) |
| 0x0602 | BUFFER_OVERFLOW | Application | Yes (increase buffer) |
| 0x0603 | RESOURCE_EXHAUSTED | Application | Yes (reduce load) |

## Key Takeaways

- Error codes: 8-bit (0xXXYY), category + specific
- Connection errors: Retry (timeout), fix config (refused), fix seed (auth)
- Session errors: Reconnect (closed/timeout), manage limits (too many)
- Stream errors: Reopen (closed), close unused (too many)
- Protocol errors: Mostly auto-recovered (retransmission), report serious bugs
- Transport errors: Reconnect or fix configuration
- Application errors: Increase resources or reduce load
- Always log with context (error code, peer, timestamp)
- Implement retries with exponential backoff
- Use circuit breakers to prevent cascading failures
