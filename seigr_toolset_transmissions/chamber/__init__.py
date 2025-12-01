"""
Chamber module - DEPRECATED.

STT is a transmission protocol - it doesn't require storage.
Applications should implement StorageProvider for their own storage needs.

Chamber will be removed in a future version.
Use seigr_toolset_transmissions.storage.StorageProvider instead.
"""

import warnings

def _get_chamber():
    """Lazy import for deprecated Chamber."""
    warnings.warn(
        "Chamber is deprecated. STT is a transmission protocol - "
        "applications should implement StorageProvider for their own storage needs. "
        "Chamber will be removed in a future version.",
        DeprecationWarning,
        stacklevel=3
    )
    from .chamber import Chamber as _Chamber, ChamberMetadata as _ChamberMetadata
    return _Chamber, _ChamberMetadata

class _DeprecatedChamberImport:
    """Wrapper to show deprecation warning on import."""
    def __getattr__(self, name):
        Chamber, _ = _get_chamber()
        return getattr(Chamber, name)
    
    def __call__(self, *args, **kwargs):
        Chamber, _ = _get_chamber()
        return Chamber(*args, **kwargs)

class _DeprecatedChamberMetadataImport:
    """Wrapper to show deprecation warning on import."""
    def __getattr__(self, name):
        _, ChamberMetadata = _get_chamber()
        return getattr(ChamberMetadata, name)
    
    def __call__(self, *args, **kwargs):
        _, ChamberMetadata = _get_chamber()
        return ChamberMetadata(*args, **kwargs)

Chamber = _DeprecatedChamberImport()
ChamberMetadata = _DeprecatedChamberMetadataImport()

__all__ = ['Chamber', 'ChamberMetadata']  # DEPRECATED
