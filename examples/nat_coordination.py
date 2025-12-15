"""
NAT coordination example for STT.

Shows how to use different NAT traversal strategies:
- Manual coordination (default)
- Relay-based coordination
- Custom coordination
"""

import asyncio
from seigr_toolset_transmissions import (
    ManualNATCoordinator,
    RelayNATCoordinator,
)


async def manual_coordination_example():
    """Example using manual NAT coordination (current behavior)."""
    
    print("="*60)
    print("MANUAL NAT COORDINATION")
    print("="*60)
    
    # Create nodes
    alice_seed = b"alice_seed_32_bytes_long_12345678"
    bob_seed = b"bob_seed_32_bytes_long_1234567890"
    _shared_seed = b"shared_seed_32_bytes_long_123456"  # Available for future use
    
    alice_node_id = alice_seed[:32]
    bob_node_id = bob_seed[:32]
    
    # Create manual coordinators
    alice_coordinator = ManualNATCoordinator(alice_node_id)
    bob_coordinator = ManualNATCoordinator(bob_node_id)
    
    # Manually configure peer endpoints (simulate out-of-band coordination)
    print("\nConfiguring peer endpoints manually...")
    alice_coordinator.configure_peer(bob_node_id, "127.0.0.1", 8002)
    bob_coordinator.configure_peer(alice_node_id, "127.0.0.1", 8001)
    
    # Register local endpoints
    await alice_coordinator.register_local_endpoint("127.0.0.1", 8001)
    await bob_coordinator.register_local_endpoint("127.0.0.1", 8002)
    
    # Get peer endpoints
    bob_endpoint = await alice_coordinator.get_peer_endpoint(bob_node_id)
    alice_endpoint = await bob_coordinator.get_peer_endpoint(alice_node_id)
    
    print(f"Alice -> Bob endpoint: {bob_endpoint}")
    print(f"Bob -> Alice endpoint: {alice_endpoint}")
    
    # Show coordinator stats
    print("\nAlice's coordinator stats:")
    print(alice_coordinator.get_stats())
    
    print("\n✓ Manual coordination complete")


async def relay_coordination_example():
    """Example using relay-based NAT coordination."""
    
    print("\n" + "="*60)
    print("RELAY NAT COORDINATION")
    print("="*60)
    
    alice_seed = b"alice_seed_32_bytes_long_12345678"
    bob_seed = b"bob_seed_32_bytes_long_1234567890"
    
    alice_node_id = alice_seed[:32]
    bob_node_id = bob_seed[:32]
    
    # Create relay coordinators pointing to same relay server
    relay_host = "relay.example.com"
    relay_port = 9000
    
    print(f"\nUsing relay server: {relay_host}:{relay_port}")
    
    alice_coordinator = RelayNATCoordinator(
        alice_node_id,
        relay_host,
        relay_port,
        fallback_to_direct=True  # Try direct first, use relay if fails
    )
    
    bob_coordinator = RelayNATCoordinator(
        bob_node_id,
        relay_host,
        relay_port,
        fallback_to_direct=True
    )
    
    # Register with relay
    print("\nRegistering nodes with relay...")
    await alice_coordinator.register_local_endpoint("10.0.1.100", 8001)
    await bob_coordinator.register_local_endpoint("10.0.2.200", 8002)
    
    # Try to get peer endpoint (will return relay since no direct info)
    print("\nAttempting to connect to Bob (no direct address)...")
    bob_endpoint = await alice_coordinator.get_peer_endpoint(bob_node_id)
    print(f"Alice -> Bob endpoint: {bob_endpoint} (via relay)")
    
    # Simulate direct connection attempt with metadata
    print("\nAttempting direct connection with metadata...")
    bob_endpoint_direct = await alice_coordinator.get_peer_endpoint(
        bob_node_id,
        metadata={'direct_host': '10.0.2.200', 'direct_port': 8002}
    )
    print(f"Alice -> Bob endpoint: {bob_endpoint_direct} (direct attempt)")
    
    # Mark relay as needed (simulate failed direct connection)
    alice_coordinator.mark_relay_required(bob_node_id)
    
    # Next attempt will use relay
    bob_endpoint_relay = await alice_coordinator.get_peer_endpoint(bob_node_id)
    print(f"Alice -> Bob endpoint: {bob_endpoint_relay} (cached relay)")
    
    # Show coordinator stats
    print("\nAlice's relay coordinator stats:")
    stats = alice_coordinator.get_stats()
    print(f"  Strategy: {stats['strategy']}")
    print(f"  Relay endpoint: {stats['relay_endpoint']}")
    print(f"  Fallback to direct: {stats['fallback_to_direct']}")
    print(f"  Relayed peers: {stats['relayed_peers']}")
    print(f"  Direct peers: {stats['direct_peers']}")
    print(f"  Relay attempts: {stats['relay_attempts']}")
    print(f"  Direct attempts: {stats['direct_attempts']}")
    
    print("\n✓ Relay coordination complete")


async def integrated_example():
    """Show how NAT coordinator would integrate with STTNode (future)."""
    
    print("\n" + "="*60)
    print("INTEGRATED NAT COORDINATION (FUTURE)")
    print("="*60)
    
    print("\nFuture STTNode API (illustrative):")
    print("""
    # Create node with NAT coordinator
    coordinator = RelayNATCoordinator(
        node_id,
        relay_host='relay.example.com',
        relay_port=9000
    )
    
    node = STTNode(
        node_seed,
        shared_seed,
        nat_coordinator=coordinator  # Pluggable!
    )
    
    # Node uses coordinator to resolve peer addresses
    session = await node.connect_peer(peer_node_id)
    # Behind the scenes:
    # 1. Coordinator resolves peer address (direct, relay, STUN, etc.)
    # 2. Node uses returned (host, port) to connect
    # 3. Application doesn't care HOW address was resolved
    """)
    
    print("\n✓ This demonstrates the pluggable architecture design")


if __name__ == "__main__":
    async def main():
        await manual_coordination_example()
        await relay_coordination_example()
        await integrated_example()
        
        print("\n" + "="*60)
        print("KEY TAKEAWAYS")
        print("="*60)
        print("""
1. NAT coordination is PLUGGABLE - choose your strategy
2. ManualNATCoordinator = current behavior (explicit configuration)
3. RelayNATCoordinator = simple relay through third node
4. Easy to add STUN, TURN, or custom strategies
5. STT core doesn't care HOW connections are made
6. Applications can switch strategies without changing STT code
        """)
    
    asyncio.run(main())
