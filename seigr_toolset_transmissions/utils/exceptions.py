"""
Custom exceptions for Seigr Toolset Transmissions.
"""


class STTException(Exception):
    """Base exception for all STT errors."""
    pass


class STTProtocolError(STTException):
    """Raised when protocol violations occur."""
    pass


class STTCryptoError(STTException):
    """Raised when cryptographic operations fail."""
    pass


class STTSessionError(STTException):
    """Raised when session-related errors occur."""
    pass


class STTStreamError(STTException):
    """Raised when stream-related errors occur."""
    pass


class STTFrameError(STTException):
    """Raised when frame parsing/encoding fails."""
    pass


class STTHandshakeError(STTException):
    """Raised when handshake fails."""
    pass


class STTTransportError(STTException):
    """Raised when transport-layer errors occur."""
    pass


class STTFlowControlError(STTException):
    """Raised when flow control violations occur."""
    pass


class STTChamberError(STTException):
    """Raised when chamber operations fail."""
    pass


class STTTimeoutError(STTException):
    """Raised when operations timeout."""
    pass


class STTConfigError(STTException):
    """Raised when configuration is invalid."""
    pass


class STTVersionError(STTProtocolError):
    """Raised when protocol version mismatch occurs."""
    pass


class STTInvalidStateError(STTException):
    """Raised when operations are attempted in invalid state."""
    pass


class STTSerializationError(STTException):
    """Raised when serialization/deserialization fails."""
    pass


class STTStreamingError(STTException):
    """Raised when streaming operations fail."""
    pass
