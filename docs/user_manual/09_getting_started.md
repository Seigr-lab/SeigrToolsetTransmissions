# Chapter 9: Getting Started

## Introduction

This chapter provides practical, step-by-step instructions for setting up STT, running your first program, and building basic applications. By the end, you'll have a working STT installation and understand the fundamentals through hands-on examples.

## Quick Start

### Installation

```bash
cd "e:\SEIGR DEV\SeigrToolsetTransmissions"
pip install -e .
```

### Verify Installation

```bash
# Run tests
pytest

# Check version
python3 -c "import seigr_toolset_transmissions; print(seigr_toolset_transmissions.__version__)"
```

### Quick Examples: Agnostic Primitives

**Example 1: Binary Streaming (Agnostic - could be video, sensors, anything)**

```python
import asyncio
from seigr_toolset_transmissions import StreamEncoder, StreamDecoder, STCWrapper

async def main():
    stc = STCWrapper(b"seed_32_bytes_minimum_required!!")
    session_id = b"session1"
    stream_id = 1
    
    # Encode arbitrary bytes (STT doesn't know what they represent)
    encoder = StreamEncoder(stc, session_id, stream_id, mode='live')
    decoder = StreamDecoder(stc, session_id, stream_id)
    
    # Send bytes (could be video frames, sensor data, anything)
    data = b"Your data here - STT just sees bytes"
    async for seq, encrypted_segment in encoder.send(data):
        decoder.receive_segment(encrypted_segment, seq)
    
    # Receive decrypted bytes
    decrypted = await decoder.receive_all()
    print(f"Got {len(decrypted)} bytes - YOU decide what they mean")

asyncio.run(main())
```

**Example 2: Hash-Addressed Storage (Agnostic byte buckets)**

```python
import asyncio
from seigr_toolset_transmissions import BinaryStorage, STCWrapper

async def main():
    stc = STCWrapper(b"seed_32_bytes_minimum_required!!")
    storage = BinaryStorage(stc)
    
    # Store ANY binary data (images, documents, sensor logs, etc.)
    data = b"Arbitrary binary content"
    hash_address = await storage.store(data)
    print(f"Stored at: {hash_address}")
    
    # Retrieve by hash
    retrieved = await storage.retrieve(hash_address)
    assert retrieved == data

asyncio.run(main())
```

### Basic Two-Node Example (Session/Stream API)

**Server** (`server.py`):

```python
import asyncio
from seigr_toolset_transmissions import STTNode

async def main():
    node = STTNode(
        node_seed=b"server_seed_32_bytes_minimum!!!",
        shared_seed=b"shared_secret_32_bytes_minimum!",
        port=9000
    )
    
    local_addr = await node.start()
    print(f"Server on {local_addr}")
    
    # Receive data
    async for packet in node.receive():
        print(f"Got: {packet.data}")
    
    await node.stop()

asyncio.run(main())
```

**Client** (`client.py`):

```python
import asyncio
from seigr_toolset_transmissions import STTNode

async def main():
    await asyncio.sleep(1)  # Wait for server
    
    node = STTNode(
        node_seed=b"client_seed_32_bytes_minimum!!!",
        shared_seed=b"shared_secret_32_bytes_minimum!"
    )
    
    await node.start()
    
    # Connect to server
    session = await node.connect_udp("127.0.0.1", 9000)
    print(f"Connected: {session.session_id.hex()}")
    
    # Send data
    stream = await session.stream_manager.create_stream()
    await stream.send(b"Hello from client!")
    
    await asyncio.sleep(2)
    await node.stop()

asyncio.run(main())
```

## Prerequisites

### System Requirements

**Operating Systems:**

- Linux (Ubuntu 20.04+, Debian 11+, Fedora 35+, Arch)
- macOS (11.0 Big Sur or later)
- Windows (10/11 with WSL2 recommended)

**Python:**

- Python 3.9+ required
- Python 3.11+ recommended (better performance)

**Check Python version:**

```bash
python3 --version
# Output: Python 3.11.5 (or higher)
```

**Networking:**

- Internet connection (for installation)
- UDP port access (or WebSocket fallback)
- No restrictive firewall (or ability to configure rules)

### Installing Python

**Linux (Ubuntu/Debian):**

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

**macOS:**

```bash
brew install python@3.11
```

**Windows:**
Download from python.org or use WSL2:

```bash
wsl --install
# Then follow Linux instructions inside WSL
```

## Installation

### Using pip (Recommended)

**Install STT package:**

```bash
pip3 install seigr-toolset-transmissions
```

**Verify installation:**

```python
python3 -c "import seigr_toolset_transmissions; print(seigr_toolset_transmissions.__version__)"
# Output: 0.2.0-alpha
```

### From Source (Development)

**Clone repository:**

```bash
git clone https://github.com/Seigr-lab/SeigrToolsetTransmissions.git
cd SeigrToolsetTransmissions
```

**Create virtual environment:**

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows
```

**Install dependencies:**

```bash
pip install -e .  # Editable install
# or
pip install -r requirements.txt
```

**Run tests (optional):**

```bash
pytest
# Expected: 90%+ test coverage
```

### Troubleshooting Installation

**Problem: `pip3: command not found`**

```bash
# Install pip
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py
```

**Problem: Permission denied**

```bash
# Use --user flag
pip3 install --user seigr-toolset-transmissions
```

**Problem: Dependency conflicts**

```bash
# Use virtual environment (isolated)
python3 -m venv stt_env
source stt_env/bin/activate
pip install seigr-toolset-transmissions
```

## Your First STT Program

### Two-Peer Echo Example

Let's create a simple echo server and client.

**Step 1: Generate shared seed**

```python
# generate_seed.py
import secrets

seed = secrets.token_bytes(32)  # 256-bit seed
print(f"Shared seed (hex): {seed.hex()}")
print(f"Shared seed (bytes): {seed}")
```

**Run it:**

```bash
python3 generate_seed.py
# Output: Shared seed (hex): a1b2c3d4...
# Copy this seed for both server and client
```

**Step 2: Create echo server**

```python
# echo_server.py
import asyncio
from seigr_toolset_transmissions.node import STTNode

async def handle_client(session):
    """Echo back everything received."""
    print(f"Client connected: {session.session_id.hex()}")
    
    # Open stream for communication
    stream = session.get_stream(stream_id=1)
    
    while True:
        try:
            # Receive data
            data = await stream.receive()
            print(f"Received: {data}")
            
            # Echo back
            await stream.send(data)
            print(f"Echoed: {data}")
        
        except Exception as e:
            print(f"Error: {e}")
            break
    
    print("Client disconnected")

async def main():
    # Replace with your generated seed
    shared_seed = bytes.fromhex("a1b2c3d4...")  # FROM STEP 1
    
    node = STTNode(
        node_id=b"EchoServer",
        port=8080,
        shared_seed=shared_seed,
        transport='udp'
    )
    
    # Register session handler
    node.on_session_established(handle_client)
    
    # Start listening
    await node.start()
    print("Echo server listening on port 8080...")
    
    # Keep running
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
```

**Step 3: Create echo client**

```python
# echo_client.py
import asyncio
from seigr_toolset_transmissions.node import STTNode

async def main():
    # Replace with your generated seed (SAME AS SERVER)
    shared_seed = bytes.fromhex("a1b2c3d4...")  # FROM STEP 1
    
    node = STTNode(
        node_id=b"EchoClient",
        shared_seed=shared_seed
    )
    
    await node.start()
    
    # Connect to server
    session = await node.connect(
        peer_address=('127.0.0.1', 8080),  # Localhost for testing
        peer_node_id=b"EchoServer"
    )
    
    print("Connected to echo server")
    
    # Open stream
    stream = session.open_stream(stream_id=1)
    
    # Send messages
    messages = [b"Hello", b"World", b"STT Echo Test"]
    
    for msg in messages:
        # Send
        await stream.send(msg)
        print(f"Sent: {msg}")
        
        # Receive echo
        echo = await stream.receive()
        print(f"Received echo: {echo}")
        assert echo == msg, "Echo mismatch!"
    
    # Cleanup
    await stream.close()
    await session.close()
    await node.stop()
    
    print("All messages echoed successfully!")

if __name__ == '__main__':
    asyncio.run(main())
```

**Step 4: Run the example**

**Terminal 1 (server):**

```bash
python3 echo_server.py
# Output: Echo server listening on port 8080...
```

**Terminal 2 (client):**

```bash
python3 echo_client.py
# Output:
# Connected to echo server
# Sent: b'Hello'
# Received echo: b'Hello'
# Sent: b'World'
# Received echo: b'World'
# Sent: b'STT Echo Test'
# Received echo: b'STT Echo Test'
# All messages echoed successfully!
```

**Server output:**

```
Client connected: 0123456789abcdef
Received: b'Hello'
Echoed: b'Hello'
Received: b'World'
Echoed: b'World'
Received: b'STT Echo Test'
Echoed: b'STT Echo Test'
Client disconnected
```

**Success!** You've established an encrypted STT session and exchanged data.

## Understanding the Example

### Key Components

**1. Shared Seed:**

```python
shared_seed = bytes.fromhex("a1b2c3d4...")
```

- **Must be identical** on both peers
- Generated securely (cryptographically random)
- Enables STC encryption

**2. STTNode:**

```python
node = STTNode(node_id=b"EchoServer", port=8080, shared_seed=shared_seed)
```

- **node_id**: Unique identifier for this peer
- **port**: Listen port (server) or random (client)
- **shared_seed**: For STC encryption

**3. Session:**

```python
session = await node.connect(('127.0.0.1', 8080), b"EchoServer")
```

- Establishes encrypted connection
- Performs handshake (4 messages)
- Returns session object

**4. Stream:**

```python
stream = session.open_stream(stream_id=1)
```

- Multiplexed channel within session
- Can have many streams per session

**5. Send/Receive:**

```python
await stream.send(data)
data = await stream.receive()
```

- Encrypted automatically (STC)
- Ordered delivery guaranteed
- Async operations (non-blocking)

### What Happens Behind the Scenes

**Client connects:**

1. Client sends HELLO (nonce, node_id)
2. Server sends CHALLENGE (nonce, encrypted challenge)
3. Client sends AUTH_PROOF (proves correct seed)
4. Server sends FINAL (confirms authentication)
5. **Session established** (~20-50ms)

**Data transfer:**

1. Client calls `stream.send(b"Hello")`
2. STT frames data (adds headers)
3. STC encrypts payload
4. UDP sends to server
5. Server receives UDP packet
6. STC decrypts payload
7. STT delivers to application
8. Echo: Server sends back (same process in reverse)

**All transparent to your code!**

## File Transfer Example

Let's build something more useful: file transfer.

**sender.py:**

```python
import asyncio
from seigr_toolset_transmissions.node import STTNode

async def send_file(session, filename):
    """Send file to peer."""
    stream = session.open_stream(max_frame_size=65536)  # 64 KB frames
    
    with open(filename, 'rb') as f:
        bytes_sent = 0
        while True:
            chunk = f.read(1048576)  # 1 MB chunks
            if not chunk:
                break
            await stream.send(chunk)
            bytes_sent += len(chunk)
            print(f"Sent {bytes_sent / 1024 / 1024:.2f} MB...")
    
    await stream.close()
    print(f"File {filename} sent successfully!")

async def main():
    shared_seed = bytes.fromhex("a1b2c3d4...")  # Your seed
    
    node = STTNode(node_id=b"Sender", shared_seed=shared_seed)
    await node.start()
    
    session = await node.connect(('127.0.0.1', 8080), b"Receiver")
    await send_file(session, 'large_file.bin')
    
    await session.close()
    await node.stop()

if __name__ == '__main__':
    asyncio.run(main())
```

**receiver.py:**

```python
import asyncio
from seigr_toolset_transmissions.node import STTNode

async def receive_file(session, output_filename):
    """Receive file from peer."""
    stream = session.get_stream(stream_id=1)
    
    with open(output_filename, 'wb') as f:
        bytes_received = 0
        while True:
            try:
                chunk = await stream.receive()
                f.write(chunk)
                bytes_received += len(chunk)
                print(f"Received {bytes_received / 1024 / 1024:.2f} MB...")
            except StreamClosedError:
                break  # Sender finished
    
    print(f"File saved to {output_filename}")

async def handle_client(session):
    await receive_file(session, 'received_file.bin')

async def main():
    shared_seed = bytes.fromhex("a1b2c3d4...")  # Same seed as sender
    
    node = STTNode(
        node_id=b"Receiver",
        port=8080,
        shared_seed=shared_seed
    )
    
    node.on_session_established(handle_client)
    await node.start()
    
    print("Waiting for file...")
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
```

**Usage:**

```bash
# Terminal 1
python3 receiver.py

# Terminal 2
dd if=/dev/zero of=large_file.bin bs=1M count=100  # Create 100 MB test file
python3 sender.py
```

**Output:**

- Encrypted file transfer over STT
- ~100 Mbps throughput (localhost)
- ~10-50 Mbps over network (depends on bandwidth)

## Configuration Guide

### Common Configurations

**Production server:**

```python
node = STTNode(
    node_id=b"ProductionServer",
    port=8080,
    shared_seed=load_seed_from_secure_storage(),
    transport='udp',
    recv_buffer_size=4194304,  # 4 MB
    send_buffer_size=4194304,
    keep_alive_interval=10.0,
    keep_alive_timeout=30.0,
    max_concurrent_streams=256
)
```

**Firewall-friendly client:**

```python
node = STTNode(
    node_id=b"Client",
    shared_seed=seed,
    transport='websocket',  # Through firewalls
    proxy='http://proxy.company.com:8080'  # If needed
)
```

**Low-latency real-time:**

```python
node = STTNode(
    node_id=b"RealTimeNode",
    shared_seed=seed,
    transport='udp',
    no_delay=True,  # Disable Nagle-like buffering
    max_frame_size=4096  # Small frames for low latency
)
```

**High-throughput bulk transfer:**

```python
node = STTNode(
    node_id=b"BulkTransfer",
    shared_seed=seed,
    transport='udp',
    max_frame_size=65536,  # Large frames
    send_buffer_size=8388608  # 8 MB
)
```

### Environment Variables

**Override defaults:**

```bash
export STT_SHARED_SEED="a1b2c3d4..."
export STT_PORT=8080
export STT_TRANSPORT=udp
export STT_LOG_LEVEL=DEBUG

python3 my_stt_app.py
```

**Load in code:**

```python
import os

node = STTNode(
    node_id=b"MyNode",
    port=int(os.getenv('STT_PORT', 8080)),
    shared_seed=bytes.fromhex(os.getenv('STT_SHARED_SEED')),
    transport=os.getenv('STT_TRANSPORT', 'udp')
)
```

## Testing and Debugging

### Enable Debug Logging

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Now STT logs everything
node = STTNode(...)
```

**Output:**

```
2024-01-15 10:30:45 - STTNode - DEBUG - Starting node on port 8080
2024-01-15 10:30:45 - HandshakeManager - DEBUG - Sending HELLO to 127.0.0.1:8080
2024-01-15 10:30:45 - HandshakeManager - DEBUG - Received CHALLENGE
...
```

### Network Diagnostics

**Test UDP connectivity:**

```bash
# Server
nc -u -l 8080

# Client
echo "test" | nc -u server_ip 8080
```

**Test WebSocket connectivity:**

```bash
# Server
websocat ws-l:127.0.0.1:8080

# Client
echo "test" | websocat ws://127.0.0.1:8080
```

### Common Startup Issues

**Problem: `Address already in use`**

```python
# Solution: Use different port or enable port reuse
node = STTNode(port=8081, reuse_port=True)
```

**Problem: `Permission denied` (port < 1024)**

```bash
# Solution: Use port >= 1024 or run as root (not recommended)
sudo python3 server.py  # Not recommended
# Better:
python3 server.py  # Change port to 8080 in code
```

**Problem: `Connection refused`**

- Check server is running (`netstat -tulpn | grep 8080`)
- Check firewall rules (`sudo ufw status`)
- Verify IP address (use `ifconfig` or `ip addr`)

## Next Steps

Now that you have STT working:

**Learn more:**

- **Chapter 10**: Common Usage Patterns (real-world examples)
- **Chapter 11**: Error Handling (robust applications)
- **Chapter 12**: Performance and Optimization (production tuning)

**Build something:**

- Secure chat application
- P2P file sharing
- Real-time data streaming
- Distributed sensor network

**Explore advanced features:**

- Multiple concurrent sessions
- Stream multiplexing (video + audio + chat)
- DHT integration for peer/content discovery
- Adaptive priority and probabilistic streams
- Crypto session continuity and affinity pooling

**Join the community:**

- GitHub: github.com/Seigr-lab/SeigrToolsetTransmissions
- Issues: Report bugs, request features
- Discussions: Ask questions, share projects

## Quick Reference

**Installation:**

```bash
pip3 install seigr-toolset-transmissions
```

**Generate seed:**

```python
import secrets
seed = secrets.token_bytes(32)
```

**Basic server:**

```python
node = STTNode(node_id=b"Server", port=8080, shared_seed=seed)
node.on_session_established(handle_client)
await node.start()
```

**Basic client:**

```python
node = STTNode(node_id=b"Client", shared_seed=seed)
await node.start()
session = await node.connect(('server_ip', 8080), b"Server")
```

**Send/receive:**

```python
stream = session.open_stream()
await stream.send(b"data")
data = await stream.receive()
```

**Cleanup:**

```python
await stream.close()
await session.close()
await node.stop()
```

## Key Takeaways

- Install with pip: `pip3 install seigr-toolset-transmissions`
- Generate secure seeds: `secrets.token_bytes(32)`
- Both peers need identical seeds
- Server calls `node.start()` and waits
- Client calls `node.connect()` to peer
- Use streams for data transfer
- All encryption automatic (STC)
- Async/await for non-blocking I/O
- Debug with logging (set DEBUG level)
- Test connectivity with nc/websocat tools

**You're ready to build with STT!**
