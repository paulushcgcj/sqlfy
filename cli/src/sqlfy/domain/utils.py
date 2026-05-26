"""
sqlfy.domain.utils
==================
Utility functions for domain model processing.
"""

from __future__ import annotations

from .models import Column


def type_str(col: Column) -> str:
    """Render column data type back to a display string."""
    if col.precision is not None and col.scale is not None:
        return f'{col.type}({col.precision},{col.scale})'
    if col.precision is not None:
        return f'{col.type}({col.precision})'
    return col.type


__all__ = ['type_str']
