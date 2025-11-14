"""
Cryptographic operations wrapper for STC integration.

This module provides the single source of truth for all cryptographic
operations in STT, exclusively using Seigr Toolset Crypto (STC).
"""

from .stc_wrapper import STCWrapper, StreamContext

__all__ = ['STCWrapper', 'StreamContext']
