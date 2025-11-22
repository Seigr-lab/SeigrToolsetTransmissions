"""
Frame module for STT protocol.
"""

from .frame import (
    STTFrame,
    FrameDispatcher,
    FRAME_TYPE_STT_MIN,
    FRAME_TYPE_STT_MAX,
    FRAME_TYPE_CUSTOM_MIN,
    FRAME_TYPE_CUSTOM_MAX,
)

__all__ = [
    'STTFrame',
    'FrameDispatcher',
    'FRAME_TYPE_STT_MIN',
    'FRAME_TYPE_STT_MAX',
    'FRAME_TYPE_CUSTOM_MIN',
    'FRAME_TYPE_CUSTOM_MAX',
]
