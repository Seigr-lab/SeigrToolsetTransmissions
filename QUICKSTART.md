# Quick Start Guide

## Installation

```bash
cd "e:\SEIGR DEV\SeigrToolsetTransmissions"
pip install -e .
```

## Verify

```bash
pytest  # Run tests
```

## Basic Usage

```python
import asyncio
from seigr_toolset_transmissions import STTNode
from seigr_toolset_transmissions.crypto import STCWrapper

async def main():
    # Initialize STC
    node_seed = b"my_node_seed_32_bytes_minimum!!"
    shared_seed = b"shared_secret_with_peer_32bytes"
    
    # Create node
    node = STTNode(
        node_seed=node_seed,
        shared_seed=shared_seed
    )
    
    # Start node
    local_addr = await node.start()
    print(f"Node started on {local_addr}")
    
    # Keep running
    await asyncio.sleep(60)
    
    # Stop
    await node.stop()

asyncio.run(main())
```

## Two Nodes

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

## Key Concepts

**Node Seed**: Initializes your STC context and generates node ID  
**Shared Seed**: Pre-shared secret for peer authentication  
**Session**: Encrypted connection to a peer  
**Stream**: Multiplexed channel within a session  

## Next Steps

1. Read `docs/api_reference.md`
2. Check `docs/examples.md`
3. Review `docs/protocol_spec.md`
4. Build your application!

## Development

```bash
# Run tests
pytest

# Format code
black seigr_toolset_transmissions/

# Type check
mypy seigr_toolset_transmissions/
```

Happy coding with STT! 🚀
