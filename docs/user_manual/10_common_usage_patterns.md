# Chapter 10: Common Usage Patterns

## Introduction

This chapter presents practical patterns for using STT in real-world applications, with working code examples.

## Request-Response Pattern

```python
# Server
async def handle_request(session):
    stream = session.get_stream(stream_id=1)
    request = await stream.receive()
    # Process request
    response = process(request)
    await stream.send(response)
    await stream.close()

# Client
stream = session.open_stream()
await stream.send(b"GET /data")
response = await stream.receive()
await stream.close()
```

**Use case:** API-style interactions, RPC

## Publish-Subscribe Pattern

```python
from seigr_toolset_transmissions.dht import KademliaDHT, PubSubManager

# Initialize DHT and pub/sub
dht = KademliaDHT(node_id=my_node_id, port=9337)
await dht.start()
pubsub = PubSubManager(dht=dht)

# Publisher
await pubsub.publish('sensor_data', sensor_reading_bytes)

# Subscriber
def handle_data(topic: str, data: bytes, publisher: DHTNode):
    reading = deserialize(data)
    process_reading(reading)

await pubsub.subscribe('sensor_data', handle_data)
```

**Seigr ecosystem:** DHT-based pub/sub for content distribution

## Bidirectional Streaming

```python
# Both peers send/receive simultaneously
async def send_loop(stream):
    while True:
        data = get_data()
        await stream.send(data)

async def receive_loop(stream):
    while True:
        data = await stream.receive()
        process(data)

await asyncio.gather(send_loop(stream), receive_loop(stream))
```

**Use case:** Video conferencing, real-time collaboration

## File Transfer with Progress

```python
async def send_file_with_progress(stream, filename):
    file_size = os.path.getsize(filename)
    bytes_sent = 0
    
    with open(filename, 'rb') as f:
        while True:
            chunk = f.read(1048576)  # 1 MB
            if not chunk:
                break
            await stream.send(chunk)
            bytes_sent += len(chunk)
            progress = (bytes_sent / file_size) * 100
            print(f"Progress: {progress:.1f}%")
    
    await stream.close()
```

## Multiplexed Application

```python
# Video conferencing: video + audio + chat simultaneously
session = await node.connect(peer_addr, peer_id)

stream_video = session.open_stream(stream_id=1, max_frame_size=32768)
stream_audio = session.open_stream(stream_id=2, max_frame_size=8192)
stream_chat = session.open_stream(stream_id=3)

# Send on all streams concurrently
await asyncio.gather(
    send_video(stream_video),
    send_audio(stream_audio),
    send_chat(stream_chat)
)
```

## Retry and Reconnection

```python
async def robust_connect(node, peer_addr, peer_id, max_retries=5):
    """Connect with exponential backoff."""
    delay = 1.0
    for attempt in range(max_retries):
        try:
            session = await node.connect(peer_addr, peer_id, timeout=10.0)
            return session
        except (ConnectionTimeoutError, ConnectionRefusedError):
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60.0)
            else:
                raise
```

## Keep-Alive Monitoring

```python
def on_session_closed(session_id, reason):
    """React to session failures."""
    if reason == 'timeout':
        logger.warning(f"Session {session_id.hex()} timed out - peer dead?")
        # Trigger reconnection
        asyncio.create_task(reconnect())
    elif reason == 'auth_failure':
        logger.error("Authentication failed - check shared_seed")

node.on_session_closed(on_session_closed)
```

## Content Distribution

```python
from seigr_toolset_transmissions.dht import KademliaDHT, ContentDistribution\n\n# Initialize DHT and content distribution\ndht = KademliaDHT(node_id=my_node_id, port=9337)\nawait dht.start()\ncontent_dist = ContentDistribution(dht=dht, node_id=my_node_id)\n\n# Publish content\ncontent_id = await content_dist.publish_content(my_data)\n\n# Retrieve from multiple providers\nretrieved_data = await content_dist.retrieve_content(content_id)\nassert retrieved_data == my_data  # Verified with STC.hash\n```\n\n## Best Practices

**DO:**

- Use multiple streams for different data types (avoid head-of-line blocking)
- Implement retry logic (network failures common)
- Monitor session health (keep-alive events)
- Close streams when done (resource cleanup)

**DON'T:**

- Send on closed streams (check `stream.is_closed()`)
- Block event loop (use asyncio properly)
- Ignore errors (handle exceptions gracefully)
- Hardcode timeouts (tune per network conditions)

## Key Takeaways

- Request-response: Simple RPC pattern
- Bidirectional: Both peers send/receive concurrently
- Multiplexing: Use separate streams for independent data flows
- Robustness: Retry with exponential backoff
- DHT enables peer/content discovery, content distribution, pub/sub patterns
- Additional features: Adaptive priority, probabilistic delivery, session continuity, affinity pooling
- STT designed for Seigr ecosystem many-to-many scenarios
