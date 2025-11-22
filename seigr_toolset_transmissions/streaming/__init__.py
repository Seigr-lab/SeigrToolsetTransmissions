"""
Agnostic streaming primitives - Binary stream encoding/decoding.

NO assumptions about data semantics. Live or bounded modes.
"""

from .encoder import BinaryStreamEncoder
from .decoder import BinaryStreamDecoder

# Aliases for compatibility
StreamEncoder = BinaryStreamEncoder
StreamDecoder = BinaryStreamDecoder

__all__ = [
    'BinaryStreamEncoder',
    'BinaryStreamDecoder',
    'StreamEncoder',  # Alias
    'StreamDecoder',  # Alias
]
