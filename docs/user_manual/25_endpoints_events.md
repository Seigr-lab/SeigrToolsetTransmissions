# Chapter 25: Endpoints & Events

**Version**: 0.2.0a0 (unreleased)  
**Components**: `EndpointManager`, `EventEmitter`  
**Test Coverage**: 100%

---

## Overview

**EndpointManager** - Manages connections to multiple endpoints  
**EventEmitter** - Event system for user-defined hooks

**Agnostic Design**: STT doesn't define what endpoints or events mean - you decide.

---

## EndpointManager

### What are Endpoints?

In STT, an **endpoint** is any addressable entity you want to communicate with:

- Peer nodes
- Relay servers
- IoT devices
- Load balancers
- Whatever you define

STT provides endpoint lifecycle management - you define endpoint semantics.

### Creating EndpointManager

```python
from seigr_toolset_transmissions.endpoints import EndpointManager

# Create manager
endpoints = EndpointManager(
    transport_send_callback=send_callback  # Your transport send function
)

# send_callback signature:
async def send_callback(endpoint_id: bytes, data: bytes):
    # Send data to endpoint
    await transport.send(data, get_address(endpoint_id))
```

### Adding Endpoints

```python
# Add endpoint
await endpoints.add_endpoint(
    endpoint_id=node_id,  # Unique ID (you define)
    address=("192.168.1.100", 9000),  # Network address
    metadata={  # Optional user-defined metadata
        'type': 'relay',
        'trust_score': 0.95,
        'capabilities': ['video', 'storage']
    }
)

# Endpoint is now tracked
```

### Sending to Endpoints

```python
# Send to specific endpoint
await endpoints.send_to_endpoint(
    endpoint_id=peer_node_id,
    data=b"Hello peer"
)

# Broadcast to all endpoints
await endpoints.broadcast(b"Announcement")

# Send to multiple specific endpoints
await endpoints.send_to_many(
    [endpoint_id1, endpoint_id2, endpoint_id3],
    b"Group message"
)
```

### Receiving from Endpoints

```python
# Receive from specific endpoint
data, endpoint_id = await endpoints.receive_from(endpoint_id)

# Receive from any endpoint
data, endpoint_id = await endpoints.receive_any()

print(f"Received from {endpoint_id.hex()}: {data}")
```

### Managing Endpoints

```python
# Get endpoint info
info = endpoints.get_endpoint(endpoint_id)
# Returns: {'address': ..., 'metadata': ..., 'connected_at': ...}

# List all endpoints
all_endpoints = endpoints.list_endpoints()
# Returns: [endpoint_id1, endpoint_id2, ...]

# Remove endpoint
await endpoints.remove_endpoint(endpoint_id)
```

### Endpoint Metadata

Store custom metadata per endpoint:

```python
await endpoints.add_endpoint(
    endpoint_id=peer_id,
    address=("10.0.0.1", 8080),
    metadata={
        'node_type': 'storage',
        'capacity_gb': 1000,
        'region': 'us-west',
        'last_health_check': time.time()
    }
)

# Query metadata
info = endpoints.get_endpoint(peer_id)
if info['metadata']['capacity_gb'] > 500:
    print("High-capacity node")
```

---

## EventEmitter

### What are Events?

Events are user-defined notifications. STT provides the event infrastructure - you define event semantics.

### Creating EventEmitter

```python
from seigr_toolset_transmissions.events import EventEmitter

# Create emitter
events = EventEmitter()
```

### Registering Event Handlers

#### Decorator Style

```python
@events.on('bytes_received')
async def handle_bytes(data: bytes, endpoint_id: bytes):
    """Handle received bytes"""
    print(f"Got {len(data)} bytes from {endpoint_id.hex()}")

@events.on('connection_established')
async def handle_connection(endpoint_id: bytes):
    """Handle new connection"""
    print(f"Connected to {endpoint_id.hex()}")

@events.on('custom_event')
async def handle_custom(user_data: dict):
    """Handle custom event - you define structure"""
    print(f"Custom event: {user_data}")
```

#### Programmatic Style

```python
async def my_handler(data):
    print(f"Event data: {data}")

# Register
events.register('my_event', my_handler)
```

### Emitting Events

```python
# Emit event
await events.emit('bytes_received', data=b"Hello", endpoint_id=peer_id)

# Emit custom event
await events.emit('custom_event', user_data={'key': 'value'})

# All registered handlers for that event are called
```

### Removing Handlers

```python
# Remove specific handler
events.remove_handler('bytes_received', handle_bytes)

# Remove all handlers for event
events.clear_event('bytes_received')

# Remove all events
events.clear_all()
```

---

## Complete Example: Endpoint Management

```python
import asyncio
from seigr_toolset_transmissions import STTNode
from seigr_toolset_transmissions.endpoints import EndpointManager
from seigr_toolset_transmissions.events import EventEmitter

async def endpoint_example():
    shared_seed = b"shared_secret_32bytes_minimum!"
    
    # Create node
    node = STTNode(
        node_seed=b"node" * 8,
        shared_seed=shared_seed,
        port=8080
    )
    await node.start(server_mode=True)
    
    # Create endpoint manager
    async def send_via_node(endpoint_id, data):
        # Find session for endpoint
        session = get_session_for_endpoint(endpoint_id)
        if session:
            await node.send_to_sessions([session.session_id], data)
    
    endpoints = EndpointManager(transport_send_callback=send_via_node)
    
    # Create event system
    events = EventEmitter()
    
    # Register handlers
    @events.on('peer_connected')
    async def handle_peer_connected(endpoint_id):
        print(f"New peer: {endpoint_id.hex()[:16]}...")
        
        # Add to endpoint manager
        await endpoints.add_endpoint(
            endpoint_id=endpoint_id,
            address=("unknown", 0),  # Will be updated
            metadata={'connected_at': time.time()}
        )
    
    @events.on('peer_message')
    async def handle_message(endpoint_id, message):
        print(f"Message from {endpoint_id.hex()[:16]}: {message}")
    
    # Simulate peer connecting
    peer_id = b"peer_node_id_32bytes!!!!!!!!"
    await events.emit('peer_connected', endpoint_id=peer_id)
    
    # Send to peer
    await endpoints.send_to_endpoint(peer_id, b"Hello peer!")
    
    # Simulate receiving message
    await events.emit('peer_message', endpoint_id=peer_id, message=b"Hello back!")
    
    # List endpoints
    print(f"\nActive endpoints: {len(endpoints.list_endpoints())}")
    for ep_id in endpoints.list_endpoints():
        info = endpoints.get_endpoint(ep_id)
        print(f"  {ep_id.hex()[:16]}: {info['metadata']}")
    
    await node.stop()

asyncio.run(endpoint_example())
```

---

## Common Patterns

### Broadcasting to Multiple Endpoints

```python
class EndpointBroadcaster:
    def __init__(self, endpoint_manager, event_emitter):
        self.endpoints = endpoint_manager
        self.events = event_emitter
        
        # Register broadcast completion handler
        self.events.on('broadcast_complete')(self.handle_broadcast_done)
    
    async def send_to_all(self, message):
        """Send message to all registered endpoints"""
        endpoint_ids = self.endpoints.list_endpoints()
        for endpoint_id in endpoint_ids:
            await self.endpoints.send_to_endpoint(endpoint_id, message)
        
        await self.events.emit('broadcast_complete', len(endpoint_ids))
    
    async def handle_broadcast_done(self, count):
        """Handle broadcast completion"""
        print(f"Message sent to {count} endpoints")
```

### Health Monitoring

```python
class HealthMonitor:
    def __init__(self, endpoint_manager):
        self.endpoints = endpoint_manager
        self.health_status = {}
    
    async def monitor(self):
        """Periodic health checks"""
        while True:
            for endpoint_id in self.endpoints.list_endpoints():
                # Send ping
                await self.endpoints.send_to_endpoint(
                    endpoint_id,
                    b"PING"
                )
                
                # Wait for pong (with timeout)
                try:
                    response, _ = await asyncio.wait_for(
                        self.endpoints.receive_from(endpoint_id),
                        timeout=5.0
                    )
                    
                    if response == b"PONG":
                        self.health_status[endpoint_id] = 'healthy'
                except asyncio.TimeoutError:
                    self.health_status[endpoint_id] = 'unhealthy'
            
            await asyncio.sleep(30)  # Check every 30s
```

### Event Metrics

```python
class EventMetrics:
    def __init__(self, event_emitter):
        self.events = event_emitter
        self.counters = {}
        
        # Intercept all events
        original_emit = self.events.emit
        
        async def emit_with_metrics(event_name, **kwargs):
            # Count event
            self.counters[event_name] = self.counters.get(event_name, 0) + 1
            
            # Call original emit
            return await original_emit(event_name, **kwargs)
        
        self.events.emit = emit_with_metrics
    
    def get_stats(self):
        return self.counters

# Usage
metrics = EventMetrics(events)

await events.emit('my_event', data=123)
await events.emit('my_event', data=456)

print(metrics.get_stats())  # {'my_event': 2}
```

---

## STT Built-in Events

STTNode emits these events automatically:

```python
# Session events
@events.on('session_created')
async def handle_session_created(session_id):
    pass

@events.on('session_closed')
async def handle_session_closed(session_id):
    pass

# Connection events
@events.on('peer_connected')
async def handle_peer_connected(peer_node_id):
    pass

@events.on('peer_disconnected')
async def handle_peer_disconnected(peer_node_id):
    pass

# Data events
@events.on('data_received')
async def handle_data_received(session_id, data):
    pass

# Error events
@events.on('error')
async def handle_error(error_type, details):
    pass
```

---

## Troubleshooting

### Event Handlers Not Called

**Problem**: Registered handler not invoked

**Causes**:
- Wrong event name (typo)
- Handler not async
- Event never emitted

**Solution**: Verify registration:

```python
# Check registered events
print(events._handlers)  # Dict of event_name -> [handlers]

# Ensure handler is async
@events.on('my_event')
async def handler(data):  # ✓ Must be async
    pass
```

### Endpoint Not Found

**Problem**: `send_to_endpoint()` fails

**Cause**: Endpoint not added

**Solution**: Check endpoint exists:

```python
if endpoint_id in endpoints.list_endpoints():
    await endpoints.send_to_endpoint(endpoint_id, data)
else:
    print("Endpoint not registered!")
    await endpoints.add_endpoint(endpoint_id, address, metadata)
```

---

## Performance Considerations

**EndpointManager**:
- Memory: ~1 KB per endpoint
- Lookup: O(1) by endpoint_id
- Broadcast: O(N) for N endpoints

**EventEmitter**:
- Registration: O(1)
- Emission: O(H) for H handlers
- Memory: ~100 bytes per handler

**Scalability**:
- Tested with 1000+ endpoints
- Tested with 100+ handlers per event
- Async design: Non-blocking

---

## Related Documentation

- **[Chapter 16: STTNode](16_sttnode.md)** - Uses endpoints for peer management
- **[Chapter 17: Sessions](17_sessions.md)** - Sessions map to endpoints
- **[API Reference](../api/API.md#endpoints)** - Complete API

---

**Document Version**: 0.2.0a0 (unreleased)  
**Last Updated**: November 25, 2025
