"""
Performance profiling utilities for STT.

Provides tools to measure and analyze STT performance:
- Latency tracking
- Throughput measurement
- Bottleneck identification
- Encryption overhead analysis
"""

import time
import statistics
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class PerformanceSnapshot:
    """Snapshot of performance metrics at a point in time."""
    timestamp: float
    
    # Session metrics
    active_sessions: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    
    # Latency metrics
    avg_rtt_ms: Optional[float] = None
    min_rtt_ms: Optional[float] = None
    max_rtt_ms: Optional[float] = None
    p95_rtt_ms: Optional[float] = None
    p99_rtt_ms: Optional[float] = None
    
    # Throughput metrics
    throughput_bps: float = 0
    throughput_mbps: float = 0
    
    # Encryption metrics
    avg_encryption_ms: float = 0
    avg_decryption_ms: float = 0
    encryption_ops: int = 0
    decryption_ops: int = 0
    
    # Resource metrics
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None


class PerformanceProfiler:
    """
    Profile STT performance over time.
    
    Usage:
        profiler = PerformanceProfiler()
        
        # Measure operation
        with profiler.measure('encryption'):
            encrypted = stc.encrypt(data)
        
        # Record metrics
        profiler.record_latency(rtt)
        profiler.record_throughput(bytes_sent, duration)
        
        # Get report
        report = profiler.get_report()
    """
    
    def __init__(self):
        """Initialize profiler."""
        self.measurements: Dict[str, List[float]] = {}
        self.snapshots: List[PerformanceSnapshot] = []
        self.start_time = time.time()
    
    @contextmanager
    def measure(self, operation: str):
        """
        Context manager to measure operation duration.
        
        Args:
            operation: Name of operation being measured
            
        Example:
            with profiler.measure('encryption'):
                encrypted = stc.encrypt(data)
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.record_measurement(operation, duration)
    
    def record_measurement(self, operation: str, duration: float) -> None:
        """
        Record a timed measurement.
        
        Args:
            operation: Operation name
            duration: Duration in seconds
        """
        if operation not in self.measurements:
            self.measurements[operation] = []
        self.measurements[operation].append(duration)
    
    def record_latency(self, rtt: float) -> None:
        """Record RTT measurement."""
        self.record_measurement('rtt', rtt)
    
    def record_throughput(self, bytes_transferred: int, duration: float) -> None:
        """
        Record throughput measurement.
        
        Args:
            bytes_transferred: Bytes sent/received
            duration: Time period in seconds
        """
        if duration > 0:
            bps = bytes_transferred / duration
            self.record_measurement('throughput_bps', bps)
    
    def take_snapshot(self, node: Optional[Any] = None) -> PerformanceSnapshot:
        """
        Take snapshot of current performance metrics.
        
        Args:
            node: Optional STTNode to get metrics from
            
        Returns:
            PerformanceSnapshot
        """
        snapshot = PerformanceSnapshot(timestamp=time.time())
        
        # Get RTT statistics
        if 'rtt' in self.measurements and self.measurements['rtt']:
            rtts_ms = [r * 1000 for r in self.measurements['rtt']]
            snapshot.avg_rtt_ms = statistics.mean(rtts_ms)
            snapshot.min_rtt_ms = min(rtts_ms)
            snapshot.max_rtt_ms = max(rtts_ms)
            
            if len(rtts_ms) >= 20:  # Need enough samples for percentiles
                snapshot.p95_rtt_ms = statistics.quantiles(rtts_ms, n=100)[94]
                snapshot.p99_rtt_ms = statistics.quantiles(rtts_ms, n=100)[98]
        
        # Get throughput
        if 'throughput_bps' in self.measurements and self.measurements['throughput_bps']:
            recent_throughput = self.measurements['throughput_bps'][-10:]  # Last 10 samples
            snapshot.throughput_bps = statistics.mean(recent_throughput)
            snapshot.throughput_mbps = snapshot.throughput_bps / 1_000_000
        
        # Get encryption metrics
        if 'encryption' in self.measurements:
            snapshot.avg_encryption_ms = statistics.mean(
                [d * 1000 for d in self.measurements['encryption']]
            )
            snapshot.encryption_ops = len(self.measurements['encryption'])
        
        if 'decryption' in self.measurements:
            snapshot.avg_decryption_ms = statistics.mean(
                [d * 1000 for d in self.measurements['decryption']]
            )
            snapshot.decryption_ops = len(self.measurements['decryption'])
        
        # Get node metrics if provided
        if node:
            stats = node.get_stats()
            snapshot.active_sessions = stats.get('active_sessions', 0)
            
            # Aggregate bytes from all sessions
            if 'sessions' in stats and 'sessions' in stats['sessions']:
                for session in stats['sessions']['sessions']:
                    snapshot.total_bytes_sent += session.get('bytes_sent', 0)
                    snapshot.total_bytes_received += session.get('bytes_received', 0)
        
        self.snapshots.append(snapshot)
        return snapshot
    
    def get_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive performance report.
        
        Returns:
            Dictionary with performance analysis
        """
        report = {
            'profiling_duration': time.time() - self.start_time,
            'snapshots_taken': len(self.snapshots),
            'operations_measured': list(self.measurements.keys()),
        }
        
        # Analyze each operation
        for operation, durations in self.measurements.items():
            if not durations:
                continue
            
            durations_ms = [d * 1000 for d in durations]
            
            report[operation] = {
                'count': len(durations),
                'avg_ms': round(statistics.mean(durations_ms), 3),
                'min_ms': round(min(durations_ms), 3),
                'max_ms': round(max(durations_ms), 3),
                'stddev_ms': round(statistics.stdev(durations_ms), 3) if len(durations) > 1 else 0,
            }
            
            # Add percentiles if enough samples
            if len(durations_ms) >= 20:
                quantiles = statistics.quantiles(durations_ms, n=100)
                report[operation].update({
                    'p50_ms': round(quantiles[49], 3),
                    'p95_ms': round(quantiles[94], 3),
                    'p99_ms': round(quantiles[98], 3),
                })
        
        # Add summary statistics
        if self.snapshots:
            latest = self.snapshots[-1]
            report['latest_snapshot'] = {
                'avg_rtt_ms': latest.avg_rtt_ms,
                'throughput_mbps': latest.throughput_mbps,
                'avg_encryption_ms': latest.avg_encryption_ms,
                'avg_decryption_ms': latest.avg_decryption_ms,
            }
        
        return report
    
    def identify_bottlenecks(self) -> List[str]:
        """
        Identify performance bottlenecks.
        
        Returns:
            List of bottleneck descriptions
        """
        bottlenecks = []
        
        # Check encryption overhead
        if 'encryption' in self.measurements:
            avg_enc = statistics.mean(self.measurements['encryption']) * 1000
            if avg_enc > 10:  # >10ms average
                bottlenecks.append(
                    f"High encryption overhead: {avg_enc:.1f}ms average. "
                    f"Consider STC optimization or hardware acceleration."
                )
        
        # Check RTT
        if 'rtt' in self.measurements and self.measurements['rtt']:
            avg_rtt = statistics.mean(self.measurements['rtt']) * 1000
            if avg_rtt > 100:  # >100ms
                bottlenecks.append(
                    f"High network latency: {avg_rtt:.1f}ms average RTT. "
                    f"Check network path and consider using closer peers."
                )
        
        # Check throughput
        if 'throughput_bps' in self.measurements and self.measurements['throughput_bps']:
            avg_throughput = statistics.mean(self.measurements['throughput_bps'])
            if avg_throughput < 10_000_000:  # <10 Mbps
                bottlenecks.append(
                    f"Low throughput: {avg_throughput/1_000_000:.1f} Mbps. "
                    f"Consider increasing frame size or buffer sizes."
                )
        
        return bottlenecks if bottlenecks else ["No significant bottlenecks detected"]
    
    def clear(self) -> None:
        """Clear all measurements and snapshots."""
        self.measurements.clear()
        self.snapshots.clear()
        self.start_time = time.time()
