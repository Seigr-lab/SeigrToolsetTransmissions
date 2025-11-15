"""
Node identity generation.

Generates deterministic node IDs for DHT routing.
No personal data - derived from node identity (e.g., public key).
"""

from typing import Union
import sys

from . import context as stc_context


def generate_node_id(identity: bytes) -> bytes:
    """
    Generate deterministic node ID for DHT.
    
    Args:
        identity: Node identity (e.g., public key, unique identifier)
                 NOT personal data - cryptographic identity only
        
    Returns:
        32-byte node ID for DHT XOR distance calculations
    """
    ctx = stc_context.get_context()
    
    return ctx.derive_key(
        length=32,
        context_data={
            'identity': identity.hex(),
            'purpose': 'node_id'
        }
    )
