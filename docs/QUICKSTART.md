# Quick Start Guide - STT v0.2.0-alpha

**Status**: Pre-release - Functional core protocol with 90.03% test coverage

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
**Shared Seed**: Pre-shared secret for peer authentication (required for handshake - must be distributed out-of-band)  
**Session**: Encrypted connection to a peer (established via 4-message HELLO/RESPONSE/AUTH_PROOF/FINAL handshake)  
**Stream**: Multiplexed channel within a session (99.24% coverage - well tested)  
**Handshake**: 4-message flow using STC encrypt/decrypt for mutual authentication (87.36% coverage)

## Protocol Features

- 4-message handshake: Full mutual authentication using STC encrypt/decrypt  
- Session management: 100% test coverage with key rotation support  
- Stream multiplexing: 99.24% coverage with ordering and flow control  
- Transport: UDP (89.86%) and WebSocket (84.17%) implementations  
- Binary serialization: Custom STT format (100% coverage), no third-party dependencies  

## Next Steps

1. Read `docs/api_reference.md`
2. Check `docs/examples.md`
3. Review `docs/protocol_spec.md`
4. Build your application!

## Development

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=seigr_toolset_transmissions

# Generate coverage report
python -m coverage html

# Format code
black seigr_toolset_transmissions/

# Type check
mypy seigr_toolset_transmissions/
```

## Current Coverage: 90.03%

- session.py: **100%**
- serialization.py: **100%**
- session_manager.py: **100%**
- stream.py: **99.24%**
- stc_wrapper.py: **98.78%**
- frame.py: **98.26%**
- handshake.py: **87.36%**

Happy coding with STT! 🚀
