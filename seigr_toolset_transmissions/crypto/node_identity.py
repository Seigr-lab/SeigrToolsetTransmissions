"""
Node identity generation.

Generates deterministic node IDs for transmission nodes.
No personal data - derived from node identity (e.g., public key).
"""


from . import context as stc_context


def generate_node_id(identity: bytes) -> bytes:
    """
    Generate deterministic node ID for transmission node.
    
    Args:
        identity: Node identity (e.g., public key, unique identifier)
                 NOT personal data - cryptographic identity only
        
    Returns:
        32-byte node ID for node identification
    """
    ctx = stc_context.get_context()
    
    return ctx.derive_key(
        length=32,
        context_data={
            'identity': identity.hex(),
            'purpose': 'node_id'
        }
    )
