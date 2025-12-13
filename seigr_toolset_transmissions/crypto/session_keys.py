"""
Session key derivation and rotation.

Ephemeral keys only - no personal data, no IP addresses.
Keys are derived from handshake data and rotated for forward secrecy.
"""

from typing import Dict, Union

from . import context as stc_context


def derive_session_key(handshake_data: Union[Dict, bytes]) -> bytes:
    """
    Derive session key from ephemeral handshake data.
    
    Uses only ephemeral parameters:
    - session_id (random, ephemeral)
    - peer_id (node identifier, not personal)
    - nonces (random)
    
    NO personal data: no IP, no user info, no identifying data.
    
    Args:
        handshake_data: Ephemeral handshake parameters or seed bytes
        
    Returns:
        32-byte session key
    """
    ctx = stc_context.get_context()
    
    if isinstance(handshake_data, bytes):
        handshake_data = {'seed': handshake_data.hex()}
    
    return ctx.derive_key(length=32, context_data=handshake_data)


def rotate_session_key(current_key: bytes, rotation_nonce: bytes) -> bytes:
    """
    Rotate session key for forward secrecy.
    
    Args:
        current_key: Current session key
        rotation_nonce: Fresh random nonce (32 bytes recommended)
        
    Returns:
        New 32-byte session key
    """
    ctx = stc_context.get_context()
    
    return ctx.derive_key(
        length=32,
        context_data={
            'current_key': current_key.hex(),
            'nonce': rotation_nonce.hex(),
            'purpose': 'rotation'
        }
    )
