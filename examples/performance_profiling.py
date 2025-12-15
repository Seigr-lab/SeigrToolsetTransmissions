"""
Performance profiling example for STT.

Shows how to measure and analyze STT performance:
- Latency tracking
- Throughput measurement
- Encryption overhead analysis
- Bottleneck identification
"""

import asyncio
from seigr_toolset_transmissions import (
    STTNode,
    PerformanceProfiler,
)


async def profile_session():
    """Profile a simple STT session."""
    
    # Create profiler
    profiler = PerformanceProfiler()
    
    # Create nodes
    print("Creating STT nodes...")
    alice_seed = b"alice_seed_32_bytes_long_12345678"
    bob_seed = b"bob_seed_32_bytes_long_1234567890"
    shared_seed = b"shared_seed_32_bytes_long_123456"
    
    with profiler.measure('node_creation'):
        alice = STTNode(alice_seed, shared_seed, host="127.0.0.1", port=8001)
        bob = STTNode(bob_seed, shared_seed, host="127.0.0.1", port=8002)
    
    try:
        # Start nodes
        print("Starting nodes...")
        with profiler.measure('node_startup'):
            await alice.start()
            await bob.start()
        
        # Connect (measure handshake)
        print("Performing handshake...")
        with profiler.measure('handshake'):
            session = await alice.connect_udp("127.0.0.1", 8002)
        
        # Send messages and measure performance
        print("\nSending messages for performance measurement...")
        
        for i in range(100):
            data = f"Message {i}".encode() * 100  # ~1KB messages
            
            # Measure send operation
            with profiler.measure('send'):
                await session.send(data)
            
            # Simulate some processing
            await asyncio.sleep(0.01)
            
            # Record throughput
            if i % 10 == 0:
                snapshot = profiler.take_snapshot(alice)
                print(f"  Snapshot {i//10}: {snapshot.throughput_mbps:.2f} Mbps")
        
        # Wait for all data to be processed
        await asyncio.sleep(1)
        
        # Take final snapshot (updates profiler internal state for report)
        profiler.take_snapshot(alice)
        
        # Get comprehensive report
        print("\n" + "="*60)
        print("PERFORMANCE REPORT")
        print("="*60)
        
        report = profiler.get_report()
        
        print(f"\nProfiled Duration: {report['profiling_duration']:.2f}s")
        print(f"Operations Measured: {', '.join(report['operations_measured'])}")
        
        # Show operation timings
        print("\nOperation Timings:")
        for op in ['node_creation', 'node_startup', 'handshake', 'send']:
            if op in report:
                stats = report[op]
                print(f"  {op}:")
                print(f"    Count: {stats['count']}")
                print(f"    Avg: {stats['avg_ms']:.3f}ms")
                print(f"    Min: {stats['min_ms']:.3f}ms")
                print(f"    Max: {stats['max_ms']:.3f}ms")
                if 'p95_ms' in stats:
                    print(f"    P95: {stats['p95_ms']:.3f}ms")
                    print(f"    P99: {stats['p99_ms']:.3f}ms")
        
        # Show latest metrics
        if 'latest_snapshot' in report:
            latest = report['latest_snapshot']
            print("\nLatest Metrics:")
            print(f"  Average RTT: {latest['avg_rtt_ms']} ms")
            print(f"  Throughput: {latest['throughput_mbps']:.2f} Mbps")
            print(f"  Avg Encryption: {latest['avg_encryption_ms']:.3f} ms")
            print(f"  Avg Decryption: {latest['avg_decryption_ms']:.3f} ms")
        
        # Identify bottlenecks
        print("\nBottleneck Analysis:")
        bottlenecks = profiler.identify_bottlenecks()
        for bottleneck in bottlenecks:
            print(f"  - {bottleneck}")
        
        # Show session stats
        print("\n" + "="*60)
        print("SESSION STATISTICS")
        print("="*60)
        
        session_stats = session.get_stats()
        print(f"\nSession ID: {session_stats['session_id']}")
        print(f"Uptime: {session_stats['uptime']:.2f}s")
        print(f"Frames Sent: {session_stats['frames_sent']}")
        print(f"Frames Received: {session_stats['frames_received']}")
        print(f"Bytes Sent: {session_stats['bytes_sent']:,}")
        print(f"Bytes Received: {session_stats['bytes_received']:,}")
        
        if session_stats['average_rtt_ms']:
            print(f"\nRTT Metrics:")
            print(f"  Average: {session_stats['average_rtt_ms']:.2f}ms")
            print(f"  Min: {session_stats['min_rtt_ms']:.2f}ms")
            print(f"  Max: {session_stats['max_rtt_ms']:.2f}ms")
            print(f"  Samples: {session_stats['rtt_samples_count']}")
        
        print(f"\nThroughput:")
        print(f"  Current: {session_stats['current_throughput_mbps']:.2f} Mbps")
        
        print(f"\nEncryption Performance:")
        print(f"  Avg Encryption Time: {session_stats['avg_encryption_time_ms']:.3f}ms")
        print(f"  Avg Decryption Time: {session_stats['avg_decryption_time_ms']:.3f}ms")
        print(f"  Encryption Ops: {session_stats['encryption_ops']}")
        print(f"  Decryption Ops: {session_stats['decryption_ops']}")
        
    finally:
        # Cleanup
        await alice.stop()
        await bob.stop()


if __name__ == "__main__":
    asyncio.run(profile_session())
