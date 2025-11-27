"""
Complete Relay NAT Traversal Example.

Shows end-to-end relay coordination:
1. Start relay server
2. Nodes register with relay
3. Nodes discover each other via relay
4. Optional: Direct connection attempts with fallback

Run this to see the full relay system in action.
"""

import asyncio
import logging
from seigr_toolset_transmissions.nat import RelayNATCoordinator
from seigr_toolset_transmissions.nat.relay_server import RelayServer


async def run_relay_server_background():
    """Run relay server in background."""
    server = RelayServer(
        host="127.0.0.1",
        port=9000,
        enable_forwarding=True
    )
    
    await server.start()
    
    print("="*60)
    print("RELAY SERVER STARTED")
    print(f"Listening on 127.0.0.1:9000")
    print("="*60)
    
    return server


async def node_scenario():
    """Simulate two nodes using relay coordination."""
    
    print("\n" + "="*60)
    print("NODE SCENARIO: Two nodes behind NAT")
    print("="*60)
    
    # Node identities
    alice_seed = b"alice_seed_32_bytes_long_12345678"
    bob_seed = b"bob_seed_32_bytes_long_1234567890"
    
    alice_node_id = alice_seed[:32]
    bob_node_id = bob_seed[:32]
    
    # Create relay coordinators
    print("\nCreating relay coordinators...")
    
    alice_coordinator = RelayNATCoordinator(
        alice_node_id,
        relay_host="127.0.0.1",
        relay_port=9000,
        fallback_to_direct=True
    )
    
    bob_coordinator = RelayNATCoordinator(
        bob_node_id,
        relay_host="127.0.0.1",
        relay_port=9000,
        fallback_to_direct=True
    )
    
    # Register with relay
    print("\nRegistering nodes with relay server...")
    
    try:
        await alice_coordinator.register_local_endpoint("10.0.1.100", 8001)
        print(f"✓ Alice registered at 10.0.1.100:8001")
    except Exception as e:
        print(f"✗ Alice registration failed: {e}")
        return
    
    try:
        await bob_coordinator.register_local_endpoint("10.0.2.200", 8002)
        print(f"✓ Bob registered at 10.0.2.200:8002")
    except Exception as e:
        print(f"✗ Bob registration failed: {e}")
        return
    
    # Wait for registrations to propagate
    await asyncio.sleep(0.5)
    
    # Alice tries to find Bob
    print("\n" + "-"*60)
    print("SCENARIO 1: Peer discovery via relay")
    print("-"*60)
    
    print("\nAlice looking up Bob's endpoint...")
    bob_endpoint = await alice_coordinator.get_peer_endpoint(bob_node_id)
    print(f"Alice -> Bob endpoint: {bob_endpoint}")
    
    # Bob tries to find Alice
    print("\nBob looking up Alice's endpoint...")
    alice_endpoint = await bob_coordinator.get_peer_endpoint(alice_node_id)
    print(f"Bob -> Alice endpoint: {alice_endpoint}")
    
    # Simulate connection attempt
    print("\n" + "-"*60)
    print("SCENARIO 2: Connection attempt with metadata")
    print("-"*60)
    
    print("\nAlice tries direct connection to Bob (with metadata)...")
    bob_endpoint_direct = await alice_coordinator.get_peer_endpoint(
        bob_node_id,
        metadata={'direct_host': '10.0.2.200', 'direct_port': 8002}
    )
    print(f"Alice -> Bob endpoint (direct attempt): {bob_endpoint_direct}")
    
    # Simulate failed direct connection
    print("\nSimulating failed direct connection (Bob behind NAT)...")
    alice_coordinator.mark_relay_required(bob_node_id)
    print("✓ Marked Bob as relay-required")
    
    # Next lookup should use relay
    print("\nAlice tries again (should use relay now)...")
    bob_endpoint_relay = await alice_coordinator.get_peer_endpoint(bob_node_id)
    print(f"Alice -> Bob endpoint (relay): {bob_endpoint_relay}")
    
    # Show statistics
    print("\n" + "="*60)
    print("COORDINATOR STATISTICS")
    print("="*60)
    
    alice_stats = alice_coordinator.get_stats()
    print("\nAlice's coordinator:")
    print(f"  Strategy: {alice_stats['strategy']}")
    print(f"  Relay endpoint: {alice_stats['relay_endpoint']}")
    print(f"  Total attempts: {alice_stats['total_attempts']}")
    print(f"  Direct attempts: {alice_stats['direct_attempts']}")
    print(f"  Relay attempts: {alice_stats['relay_attempts']}")
    print(f"  Relayed peers: {alice_stats['relayed_peers']}")
    print(f"  Direct peers: {alice_stats['direct_peers']}")
    
    bob_stats = bob_coordinator.get_stats()
    print("\nBob's coordinator:")
    print(f"  Strategy: {bob_stats['strategy']}")
    print(f"  Relay endpoint: {bob_stats['relay_endpoint']}")
    print(f"  Total attempts: {bob_stats['total_attempts']}")
    print(f"  Direct attempts: {bob_stats['direct_attempts']}")
    print(f"  Relay attempts: {bob_stats['relay_attempts']}")
    
    # Cleanup
    print("\n" + "="*60)
    print("CLEANUP")
    print("="*60)
    
    print("\nUnregistering nodes...")
    await alice_coordinator.unregister_endpoint()
    print("✓ Alice unregistered")
    
    await bob_coordinator.unregister_endpoint()
    print("✓ Bob unregistered")


async def direct_fallback_scenario(server: RelayServer):
    """Show direct connection with relay fallback."""
    
    print("\n" + "="*60)
    print("SCENARIO 3: Direct connection with relay fallback")
    print("="*60)
    
    alice_seed = b"alice_seed_32_bytes_long_12345678"
    charlie_seed = b"charlie_seed_32_bytes_long_123456"
    
    alice_node_id = alice_seed[:32]
    charlie_node_id = charlie_seed[:32]
    
    # Alice uses relay with fallback
    alice_coordinator = RelayNATCoordinator(
        alice_node_id,
        relay_host="127.0.0.1",
        relay_port=9000,
        fallback_to_direct=True
    )
    
    # Charlie is publicly accessible (no NAT)
    charlie_coordinator = RelayNATCoordinator(
        charlie_node_id,
        relay_host="127.0.0.1",
        relay_port=9000,
        fallback_to_direct=True
    )
    
    # Register both
    print("\nRegistering nodes...")
    await alice_coordinator.register_local_endpoint("10.0.1.100", 8001)
    await charlie_coordinator.register_local_endpoint("203.0.113.50", 8003)
    print("✓ Both nodes registered")
    
    await asyncio.sleep(0.5)
    
    # Alice looks up Charlie (should get direct address from relay)
    print("\nAlice looking up Charlie (public IP)...")
    charlie_endpoint = await alice_coordinator.get_peer_endpoint(charlie_node_id)
    print(f"Alice -> Charlie endpoint: {charlie_endpoint}")
    
    # Simulate successful direct connection
    print("\nSimulating successful direct connection...")
    alice_coordinator.mark_direct_success(charlie_node_id)
    print("✓ Direct connection succeeded")
    
    # Show that Charlie is cached as direct peer
    print("\nAlice's stats after direct success:")
    stats = alice_coordinator.get_stats()
    print(f"  Direct peers: {stats['direct_peers']}")
    print(f"  Relayed peers: {stats['relayed_peers']}")
    print(f"  Direct success rate: {stats['direct_success_rate']:.1f}%")
    
    # Cleanup
    await alice_coordinator.unregister_endpoint()
    await charlie_coordinator.unregister_endpoint()


async def show_server_status(server: RelayServer):
    """Display relay server status."""
    
    print("\n" + "="*60)
    print("RELAY SERVER STATUS")
    print("="*60)
    
    status = server.get_status()
    
    print(f"\nServer: {status['listening']}")
    print(f"Running: {status['running']}")
    print(f"Active nodes: {status['active_nodes']}")
    
    print("\nStatistics:")
    for key, value in status['statistics'].items():
        print(f"  {key}: {value}")
    
    if status['nodes']:
        print("\nRegistered nodes:")
        for node in status['nodes']:
            print(f"  {node['node_id']}: {node['endpoint']} "
                  f"(age: {node['age']:.1f}s)")


async def main():
    """Run complete relay coordination example."""
    
    print("="*60)
    print("COMPLETE RELAY NAT COORDINATION DEMO")
    print("="*60)
    
    # Start relay server
    server = await run_relay_server_background()
    
    try:
        # Run scenarios
        await node_scenario()
        await direct_fallback_scenario(server)
        await show_server_status(server)
        
        print("\n" + "="*60)
        print("KEY TAKEAWAYS")
        print("="*60)
        print("""
1. Relay server handles node registration and discovery
2. Nodes can find each other through relay lookup
3. Direct connections attempted first (when enabled)
4. Automatic fallback to relay if direct fails
5. Keep-alive maintains registrations
6. Statistics track connection patterns
7. Pluggable architecture - easy to swap strategies

This enables STT to work behind NAT without port forwarding!
        """)
        
    finally:
        # Cleanup
        print("\nShutting down relay server...")
        await server.stop()
        print("✓ Relay server stopped")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Run demo
    asyncio.run(main())
