"""
Compatibility shim for legacy imports.

The active implementation now lives under `runtime.services.transforms`.
"""

from runtime.services.transforms.contract_normalization import (
    apply_contract_transformations,
    preserve_public_api_names,
)

__all__ = [
    "apply_contract_transformations",
    "preserve_public_api_names",
]
