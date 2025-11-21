#!/usr/bin/env python
"""
Run node tests in small batches to work around coverage deadlock.
Coverage + pytest-asyncio has known deadlock issues with many async tests.
"""

import subprocess
import sys
from pathlib import Path

# Split tests into smaller batches
TEST_BATCHES = [
    # Batch 1: Simple tests
    [
        "tests/test_core_node.py::TestSTTNode::test_create_node",
        "tests/test_core_node.py::TestSTTNode::test_node_id_generation",
        "tests/test_core_node.py::TestSTTNode::test_received_packet_dataclass",
        "tests/test_core_node.py::TestSTTNode::test_default_chamber_path",
        "tests/test_core_node.py::TestSTTNode::test_connect_udp_without_start",
        "tests/test_core_node.py::TestSTTNode::test_node_stop_when_not_running",
    ],
    # Batch 2: Start/stop tests
    [
        "tests/test_core_node.py::TestSTTNode::test_node_start_stop",
        "tests/test_core_node.py::TestSTTNode::test_node_double_start",
    ],
    # Batch 3: Integration tests (part 1)
    [
        "tests/test_core_node.py::TestSTTNodeIntegration::test_node_chamber_initialization",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_node_session_manager_initialization",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_node_handshake_manager_initialization",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_node_receive_queue_initialization",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_node_host_port_configuration",
    ],
    # Batch 4: Integration tests (part 2)
    [
        "tests/test_core_node.py::TestSTTNodeIntegration::test_node_ws_connections_empty",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_node_tasks_empty_initially",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_node_get_stats",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_node_receive_queue",
    ],
    # Batch 5: Frame handling
    [
        "tests/test_core_node.py::TestSTTNodeIntegration::test_handle_handshake_frame",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_handle_data_frame_no_session",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_handle_data_frame_with_session",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_handle_unknown_frame_type",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_handle_frame_exception",
    ],
    # Batch 6: Communication tests
    [
        "tests/test_core_node.py::TestSTTNodeIntegration::test_two_nodes_communication",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_node_lifecycle",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_receive_generator",
    ],
    # Batch 7: Connect tests
    [
        "tests/test_core_node.py::TestSTTNodeIntegration::test_connect_udp_handshake_flow",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_connect_udp_incomplete_handshake",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_connect_udp_no_peer_id",
    ],
    # Batch 8: Error handling
    [
        "tests/test_core_node.py::TestSTTNodeIntegration::test_connect_udp_exception_handling",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_handle_handshake_frame_error",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_handle_data_frame_error",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_receive_timeout",
    ],
    # Batch 9: Remaining tests
    [
        "tests/test_core_node.py::TestSTTNodeIntegration::test_node_with_background_tasks",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_node_double_start",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_connect_udp_not_started",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_node_stop_when_not_running",
        "tests/test_core_node.py::TestSTTNodeIntegration::test_node_stop_with_websockets",
    ],
]

def run_batch(batch_num, tests):
    """Run a batch of tests with coverage."""
    print(f"\n[Batch {batch_num}/{len(TEST_BATCHES)}] Running {len(tests)} tests...")
    
    cmd = [
        sys.executable, "-m", "pytest",
        *tests,
        "--cov=seigr_toolset_transmissions",
        "--cov-append",  # ALWAYS append
        "-q", "--tb=no"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,  # 60 second timeout per batch
            cwd=Path(__file__).parent
        )
        
        if result.returncode == 0:
            # Count passed
            for line in result.stdout.split('\n'):
                if 'passed' in line:
                    print(f"  ✓ {line.strip()}")
                    return True
            print("  ✓ Passed")
            return True
        else:
            print(f"  ✗ Exit code {result.returncode}")
            if result.stderr:
                print(f"  Error: {result.stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"  ✗ TIMEOUT")
        return False
    except Exception as e:
        print(f"  ✗ {e}")
        return False

def main():
    print("Running node tests in batches to avoid coverage deadlock")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for i, batch in enumerate(TEST_BATCHES, 1):
        if run_batch(i, batch):
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Batches: {passed} passed, {failed} failed/timeout")
    print("=" * 60)
    
    # Show final coverage
    print("\nGenerating coverage report...\n")
    subprocess.run([sys.executable, "-m", "coverage", "report", "|", "grep", "node.py"])

if __name__ == "__main__":
    main()
