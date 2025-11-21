"""
Session module for STT protocol.
"""

from .session import STTSession
from .session_manager import SessionManager
from .continuity import CryptoSessionContinuity, SessionResumptionError, SessionState
from .affinity_pool import ContentAffinityPool, PoolMissError, xor_distance

__all__ = [
    'STTSession',
    'SessionManager',
    'CryptoSessionContinuity',
    'SessionResumptionError',
    'SessionState',
    'ContentAffinityPool',
    'PoolMissError',
    'xor_distance',
]
