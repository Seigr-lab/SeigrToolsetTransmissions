# Chapter 12: Performance and Optimization

## Introduction

This chapter explains how to tune STT for maximum performance in various scenarios.

**Agnostic Design:** Performance tuning (frame sizes, buffer management, concurrency) applies to ALL use cases. Whether you're optimizing for live video streaming, bulk file transfers, or IoT sensor networks - the same STT tuning parameters apply. STT doesn't optimize based on data type - YOU choose parameters based on your performance requirements (latency vs throughput).

## Benchmarking Baseline

**Typical performance (localhost, UDP):**

- Latency: ~0.5-2ms (round-trip)
- Throughput: ~500 Mbps (single stream, 64 KB frames)
- Sessions: ~500 concurrent (modern hardware)

**Over network:**

- Latency: Network RTT + ~1ms STT overhead
- Throughput: Limited by bandwidth, ~90% efficiency

## Throughput Optimization

### Frame Size Tuning

**Larger frames = higher throughput:**

```python
# High-throughput file transfer
stream = session.open_stream(
    max_frame_size=65536  # 64 KB (max practical)
)
```

**Trade-off:** Higher latency per frame (takes longer to send 64 KB than 4 KB)

**Small frames = lower latency:**

```python
# Low-latency chat
stream = session.open_stream(
    max_frame_size=4096  # 4 KB
)
```

**Rule of thumb:**

- Real-time (chat, gaming): 4-8 KB
- Streaming (video): 16-32 KB
- Bulk transfer (files): 64 KB

### Buffer Sizing

**Increase socket buffers for high bandwidth:**

```python
node = STTNode(
    recv_buffer_size=8388608,  # 8 MB
    send_buffer_size=8388608
)
```

**Formula:** `buffer_size = bandwidth * RTT * 2`

Example:

- 1 Gbps link
- 100ms RTT
- Buffer = 1000 Mbps *0.1s* 2 = 25 MB

**OS limits (Linux):**

```bash
sudo sysctl -w net.core.rmem_max=16777216  # 16 MB
sudo sysctl -w net.core.wmem_max=16777216
```

### Disable Nagle-Like Buffering

**For low latency:**

```python
stream = session.open_stream(
    no_delay=True  # Send immediately (no buffering)
)
```

**Use when:** Real-time applications where latency > throughput

## Latency Optimization

### Transport Selection

**UDP:** Lowest latency (~1ms overhead)
**WebSocket:** Higher latency (~10-20ms overhead from TCP)

**Use UDP unless firewall requires WebSocket**

### Keep-Alive Tuning

```python
node = STTNode(
    keep_alive_interval=5.0,  # More frequent (default 10s)
    keep_alive_timeout=15.0   # Faster detection (default 30s)
)
```

**Trade-off:** More frequent keep-alives = higher overhead but faster failure detection

### Frame Processing

**Batch receives (reduce syscalls):**

```python
async def receive_batch(stream, batch_size=10):
    """Receive multiple frames efficiently."""
    batch = []
    for _ in range(batch_size):
        data = await stream.receive()
        batch.append(data)
    return batch
```

## Memory Optimization

### Stream Limits

**Limit concurrent streams:**

```python
node = STTNode(
    max_concurrent_streams=128  # Lower than default 256
)
```

**Per-stream memory:** ~100 KB (buffers + metadata)

- 128 streams = ~13 MB
- 256 streams = ~26 MB

### Buffer Reuse

**Avoid allocating large buffers repeatedly:**

```python
# Bad: Allocates new buffer each time
for data in large_dataset:
    await stream.send(data)  # New bytes object each iteration

# Good: Reuse buffer
buffer = bytearray(1048576)  # 1 MB reusable buffer
for data in large_dataset:
    buffer[:len(data)] = data
    await stream.send(buffer[:len(data)])
```

## CPU Optimization

### Encryption Overhead

**STC encryption is main CPU cost:**

- Typical: ~50-100 MB/s per CPU core
- Multi-core: Scales linearly (each session independent)

**No way to reduce** (STC required for security)

**Workaround:** Use multiple cores (multiple sessions)

### Profiling

```python
import cProfile

def profile_session():
    cProfile.run('asyncio.run(my_stt_function())', 'profile_stats')

# Analyze
import pstats
p = pstats.Stats('profile_stats')
p.sort_stats('cumulative').print_stats(20)
```

**Look for:**

- Time in STC encrypt/decrypt (expected - cannot optimize)
- Time in frame serialization (optimize if high)
- Time in application logic (optimize your code)

## Scaling to Many Sessions

### Event Loop Tuning

**Use uvloop (faster event loop):**

```bash
pip install uvloop
```

```python
import uvloop
uvloop.install()

# Now asyncio.run() uses uvloop (10-50% faster)
```

### Content-Affinity Session Pooling

**STT 0.2.0a0 includes hash-neighborhood clustering:**

```python
from seigr_toolset_transmissions.session import ContentAffinityPool

# Create affinity pool
pool = ContentAffinityPool(dht=node.dht, max_pool_size=100)

# Add session to pool
content_hash = stc.hash_data(initial_content)
pool.add_session(session, content_hash)

# Get session for related content
related_hash = stc.hash_data(related_content)
try:
    session = pool.get_session_for_content(related_hash)
    # Likely to have related content cached!
except PoolMissError:
    # No suitable session, create new one
    session = await node.connect(peer_addr, peer_id)
    pool.add_session(session, related_hash)
```

**How it works:**

1. **Hash-based clustering**: Sessions grouped by STC.hash prefix (first 4 bytes)
2. **XOR distance affinity**: Kademlia metric determines content similarity
3. **Automatic rebalancing**: Sessions migrate between pools as traffic patterns change
4. **LRU eviction**: Least-recently-used sessions evicted when pool full

**Benefits:**

- **Cache locality**: Related content requests use same session
- **Load distribution**: Sessions allocated based on content hash distribution
- **Hash-based clustering**: Content groups by STC.hash proximity

Sessions are pooled by content hash proximity rather than by transport endpoint.

## Network Optimization

### Path MTU Discovery

**Avoid fragmentation:**

```python
# Set frame size to MTU - overhead
# Typical Ethernet: 1500 - 20 (IP) - 8 (UDP) - 50 (STT header) = ~1400 bytes

stream = session.open_stream(
    max_frame_size=1400  # Fits in single packet
)
```

**Less fragmentation = lower packet loss**

### QoS and Traffic Shaping

**Prioritize STT traffic (router/firewall):**

```bash
# Linux tc (traffic control)
sudo tc qdisc add dev eth0 root handle 1: htb default 12
sudo tc class add dev eth0 parent 1: classid 1:1 htb rate 100mbit

# Prioritize UDP port 8080 (STT)
sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 \\
    match ip dport 8080 0xffff flowid 1:1
```

**Mark packets (future STT feature):** DSCP values for QoS

## Monitoring and Metrics

### Performance Metrics

```python
# Get session stats
stats = session.get_stats()

print(f"Bytes sent: {stats.bytes_sent}")
print(f"Bytes received: {stats.bytes_received}")
print(f"RTT: {stats.rtt_ms:.2f} ms")
print(f"Loss rate: {stats.loss_rate * 100:.2f}%")
print(f"Throughput: {stats.throughput_mbps:.2f} Mbps")
```

**Monitor:**

- RTT: Latency (should be stable)
- Loss rate: < 1% good, > 5% problematic
- Throughput: Compare to link capacity

### Bottleneck Detection

**CPU-bound:** High CPU usage (~100% on cores)

- **Solution:** More cores, reduce sessions per node

**Network-bound:** Low CPU, low throughput

- **Solution:** Check bandwidth, reduce frame size, check loss rate

**Memory-bound:** High memory usage, swapping

- **Solution:** Reduce buffers, limit concurrent streams

## Benchmarking Tools

### Simple Benchmark

```python
import time
import asyncio

async def benchmark_throughput(session, data_size=100*1024*1024):
    """Measure throughput (MB/s)."""
    stream = session.open_stream(max_frame_size=65536)
    
    chunk = b'x' * 1048576  # 1 MB chunk
    chunks_to_send = data_size // len(chunk)
    
    start = time.time()
    for _ in range(chunks_to_send):
        await stream.send(chunk)
    await stream.flush()
    elapsed = time.time() - start
    
    throughput = (data_size / elapsed) / (1024 * 1024)
    print(f"Throughput: {throughput:.2f} MB/s")
    
    await stream.close()
```

### Latency Benchmark

```python
async def benchmark_latency(session, iterations=1000):
    """Measure round-trip latency (ms)."""
    stream = session.open_stream()
    
    latencies = []
    for _ in range(iterations):
        start = time.time()
        await stream.send(b'ping')
        await stream.receive()  # Wait for echo
        latency_ms = (time.time() - start) * 1000
        latencies.append(latency_ms)
    
    avg = sum(latencies) / len(latencies)
    p50 = sorted(latencies)[len(latencies) // 2]
    p99 = sorted(latencies)[int(len(latencies) * 0.99)]
    
    print(f"Avg latency: {avg:.2f} ms")
    print(f"P50 latency: {p50:.2f} ms")
    print(f"P99 latency: {p99:.2f} ms")
```

## Configuration Presets

### Low Latency (Real-Time)

```python
node = STTNode(
    transport='udp',
    max_frame_size=4096,
    no_delay=True,
    recv_buffer_size=524288,  # 512 KB (smaller)
    send_buffer_size=524288
)
```

**Use case:** Gaming, VoIP, chat

### High Throughput (Bulk Transfer)

```python
node = STTNode(
    transport='udp',
    max_frame_size=65536,
    recv_buffer_size=8388608,  # 8 MB
    send_buffer_size=8388608,
    max_concurrent_streams=64  # Focus bandwidth
)
```

**Use case:** File transfer, video distribution

### Balanced (General Purpose)

```python
node = STTNode(
    transport='udp',
    max_frame_size=16384,  # 16 KB (default)
    recv_buffer_size=2097152,  # 2 MB
    send_buffer_size=2097152,
    max_concurrent_streams=256
)
```

**Use case:** Mixed workload

## Best Practices

**DO:**

- Benchmark in realistic environment (not just localhost)
- Monitor metrics (loss rate, RTT, throughput)
- Tune frame size for use case (latency vs throughput)
- Use UDP for performance (unless firewall blocks)
- Profile before optimizing (measure, don't guess)

**DON'T:**

- Optimize prematurely (measure first)
- Ignore network conditions (check loss, latency)
- Saturate link (leave headroom for bursts)
- Use tiny buffers (causes packet loss under load)
- Assume localhost performance = production (network differs)

## Key Takeaways

- Throughput: Large frames (64 KB), large buffers (8 MB), UDP transport
- Latency: Small frames (4 KB), no_delay=True, UDP transport, frequent keep-alives
- Memory: Limit concurrent streams, reuse buffers
- CPU: STC encryption dominates (use multiple cores via multiple sessions)
- Scaling: Event loop (uvloop), content-affinity pooling, adaptive priority
- Monitor: RTT, loss rate, throughput to detect bottlenecks
- Benchmark: Measure in realistic environment before production
