"""
Shared STC context for all crypto operations.

Initialized once at node startup, shared across all crypto functions.
"""

from typing import Union
import sys

try:
    from interfaces.api import stc_api
except ImportError:
    import site
    sys.path.extend(site.getsitepackages())
    from interfaces.api import stc_api


# Global STC context - initialized once per node
_context = None


def initialize(node_seed: Union[str, bytes, int]):
    """
    Initialize node-level STC context.
    
    Call once at node startup with node-unique seed (no personal data).
    
    Args:
        node_seed: Node-unique seed for crypto operations
    """
    global _context
    _context = stc_api.initialize(
        seed=node_seed,
        lattice_size=128,
        depth=6,
        morph_interval=100,
        adaptive_difficulty='balanced',
        adaptive_morphing=True
    )
    return _context


def get_context():
    """
    Get the initialized STC context.
    
    Returns:
        STC context
        
    Raises:
        RuntimeError: If context not initialized
    """
    if _context is None:
        raise RuntimeError("STC context not initialized. Call crypto.context.initialize() first")
    return _context
