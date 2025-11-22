# Chapter 11: Error Handling

## Introduction

Robust STT applications handle errors gracefully. This chapter covers error types, recovery strategies, and best practices.

**Agnostic Design:** STT errors are transport-level (connection failed, session timeout, frame corruption). Errors NEVER assume data semantics - a `StreamClosedError` is the same whether the stream carried video, files, or sensor data. Application-level errors (invalid video codec, corrupted file) are YOUR responsibility.

## Error Hierarchy

```
STTError (base)
├── ConnectionError
│   ├── ConnectionTimeoutError
│   ├── ConnectionRefusedError
│   └── AuthenticationError
├── SessionError
│   ├── SessionClosedError
│   └── SessionTimeoutError
├── StreamError
│   ├── StreamClosedError
│   └── TooManyStreamsError
└── ProtocolError
    ├── InvalidFrameError
    └── EncryptionError
```

## Connection Errors

### Authentication Failure

```python
try:
    session = await node.connect(peer_addr, peer_id)
except AuthenticationError:
    logger.error("Wrong shared_seed - authentication failed")
    # Fix: Verify both peers use identical seed
```

**Causes:**

- Mismatched seeds
- Seed corruption
- Wrong peer_node_id

**Recovery:** No automatic - must fix configuration

### Connection Timeout

```python
try:
    session = await node.connect(peer_addr, peer_id, timeout=10.0)
except ConnectionTimeoutError:
    logger.warning("Handshake timeout - peer slow/unreachable")
    # Retry or try different transport
```

**Causes:**

- Peer offline/crashed
- Network issues (packet loss)
- Firewall blocking
- Wrong IP/port

**Recovery:** Retry with exponential backoff

### Connection Refused

```python
try:
    session = await node.connect(peer_addr, peer_id)
except ConnectionRefusedError:
    logger.error("Peer not listening - check IP/port")
    # Verify peer is running, correct address
```

**Causes:**

- Peer not started
- Wrong port
- Firewall blocking

**Recovery:** Fix configuration, retry

## Session Errors

### Session Closed Unexpectedly

```python
try:
    await stream.send(data)
except SessionClosedError as e:
    logger.error(f"Session closed: {e.reason}")
    if e.reason == 'timeout':
        # Peer died (keep-alive timeout)
        await reconnect()
    elif e.reason == 'error':
        # Protocol error - check logs
        logger.debug(f"Details: {e}")
```

**Causes:**

- Keep-alive timeout (peer crashed)
- Graceful close (peer called `session.close()`)
- Protocol error (invalid frames)

**Recovery:** Reconnect (new session)

### Stream Closed

```python
try:
    data = await stream.receive()
except StreamClosedError:
    logger.info("Stream closed by peer - normal end")
    # Don't reconnect - this is expected for finite transfers
```

**Causes:**

- Peer called `stream.close()` (normal)
- Session closed (fatal - all streams close)

**Recovery:** None needed if expected; reconnect session if unexpected

## Protocol Errors

### Invalid Frame

```python
# STT handles these internally - rare in application code
try:
    await stream.send(data)
except InvalidFrameError as e:
    logger.error(f"Protocol error: {e}")
    # Bug in STT or corrupted network - report issue
```

**Causes:**

- Corrupted packets (checksums detect)
- Software bug
- Incompatible STT versions

**Recovery:** Close session, reconnect

### Encryption Error

```python
try:
    await stream.send(data)
except EncryptionError as e:
    logger.error(f"STC encryption failed: {e}")
    # Serious - check seed, STC library
```

**Causes:**

- STC library issue
- Corrupted seed
- Memory corruption

**Recovery:** Restart application, verify seed

## Timeout Handling

### Send Timeout

```python
try:
    await asyncio.wait_for(stream.send(data), timeout=30.0)
except asyncio.TimeoutError:
    logger.warning("Send timed out - receiver slow/blocked")
    # Flow control backpressure - receiver can't keep up
    # Options: wait longer, reduce send rate, abort
```

**Causes:**

- Slow receiver (backpressure)
- Network congestion
- Buffer overflow

**Recovery:** Increase timeout, reduce send rate, increase buffers

### Receive Timeout

```python
try:
    data = await asyncio.wait_for(stream.receive(), timeout=10.0)
except asyncio.TimeoutError:
    logger.warning("No data received in 10s")
    # Peer may be slow, or has nothing to send
```

**Causes:**

- Peer has no data to send (normal)
- Peer slow
- Network issues

**Recovery:** Retry or proceed without data

## Retry Strategies

### Exponential Backoff

```python
async def retry_with_backoff(func, max_retries=5, initial_delay=1.0):
    """Generic retry with exponential backoff."""
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return await func()
        except (ConnectionTimeoutError, ConnectionRefusedError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"Attempt {attempt+1} failed: {e}, retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60.0)  # Cap at 60s
            else:
                logger.error("Max retries exceeded")
                raise

# Usage
session = await retry_with_backoff(
    lambda: node.connect(peer_addr, peer_id)
)
```

### Circuit Breaker

```python
class CircuitBreaker:
    """Prevent repeated failing calls."""
    def __init__(self, failure_threshold=5, timeout=60.0):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half_open
    
    async def call(self, func):
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'half_open'
            else:
                raise Exception("Circuit breaker open")
        
        try:
            result = await func()
            if self.state == 'half_open':
                self.state = 'closed'
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
            raise

# Usage
breaker = CircuitBreaker()
session = await breaker.call(lambda: node.connect(peer_addr, peer_id))
```

## Graceful Degradation

```python
async def connect_with_fallback(node, peer_addr, peer_id):
    """Try UDP first, fallback to WebSocket."""
    try:
        # Try UDP (faster)
        return await node.connect(peer_addr, peer_id, transport='udp', timeout=5.0)
    except (ConnectionTimeoutError, ConnectionRefusedError):
        logger.warning("UDP failed, trying WebSocket...")
        # Fallback to WebSocket (firewall-friendly)
        try:
            return await node.connect(peer_addr, peer_id, transport='websocket', timeout=10.0)
        except Exception as e:
            logger.error(f"Both transports failed: {e}")
            raise
```

## Error Recovery Patterns

### Stateless Recovery

```python
# No state to preserve - just reconnect
async def stateless_operation():
    while True:
        try:
            session = await node.connect(peer_addr, peer_id)
            result = await do_work(session)
            await session.close()
            return result
        except SessionClosedError:
            logger.warning("Session died, retrying...")
            await asyncio.sleep(1.0)
```

### Stateful Recovery

```python
# Preserve state across reconnections
class StatefulClient:
    def __init__(self, node, peer_addr, peer_id):
        self.node = node
        self.peer_addr = peer_addr
        self.peer_id = peer_id
        self.session = None
        self.checkpoint = 0  # Track progress
    
    async def resume_transfer(self, data, chunk_size=1024):
        """Resume from checkpoint on reconnection."""
        while self.checkpoint < len(data):
            if not self.session or self.session.state != SessionState.ESTABLISHED:
                await self.reconnect()
            
            try:
                chunk = data[self.checkpoint:self.checkpoint + chunk_size]
                await self.stream.send(chunk)
                self.checkpoint += len(chunk)
            except SessionClosedError:
                logger.warning(f"Disconnected at {self.checkpoint}, reconnecting...")
                # Will reconnect on next iteration
    
    async def reconnect(self):
        """Reconnect and restore stream."""
        self.session = await retry_with_backoff(
            lambda: self.node.connect(self.peer_addr, self.peer_id)
        )
        self.stream = self.session.open_stream()
```

## Logging and Diagnostics

### Comprehensive Logging

```python
import logging

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stt_debug.log'),
        logging.StreamHandler()
    ]
)

# Exception logging
try:
    session = await node.connect(peer_addr, peer_id)
except Exception as e:
    logger.exception("Connection failed")  # Includes stack trace
```

### Error Metrics

```python
from collections import defaultdict

class ErrorTracker:
    """Track error rates for monitoring."""
    def __init__(self):
        self.error_counts = defaultdict(int)
        self.total_calls = 0
    
    def record_error(self, error_type):
        self.error_counts[error_type.__class__.__name__] += 1
        self.total_calls += 1
    
    def get_error_rate(self, error_type):
        count = self.error_counts.get(error_type.__name__, 0)
        return count / max(self.total_calls, 1)
    
    def report(self):
        for error_type, count in self.error_counts.items():
            rate = (count / self.total_calls) * 100
            logger.info(f"{error_type}: {count} ({rate:.2f}%)")

tracker = ErrorTracker()

try:
    session = await node.connect(peer_addr, peer_id)
except Exception as e:
    tracker.record_error(e)
```

## Best Practices

**DO:**

- Catch specific exceptions (not bare `except:`)
- Log errors with context (include peer_id, session_id)
- Implement retry logic (network failures common)
- Use timeouts (prevent infinite blocking)
- Monitor error rates (detect systemic issues)

**DON'T:**

- Silently ignore errors (`except: pass`)
- Retry infinitely (use max_retries)
- Block event loop (use async properly)
- Assume errors are bugs (network failures normal)

## Key Takeaways

- Error hierarchy: Connection → Session → Stream → Protocol
- Authentication errors: No recovery - fix seed
- Connection timeouts: Retry with exponential backoff
- Session closed: Reconnect (new session)
- Stream closed: Expected for finite transfers
- Timeouts: Use `asyncio.wait_for()` consistently
- Retry patterns: Exponential backoff, circuit breaker
- Graceful degradation: Fallback transports (UDP → WebSocket)
- Logging: DEBUG level for troubleshooting, metrics for monitoring
