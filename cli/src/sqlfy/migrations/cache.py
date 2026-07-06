"""
sqlfy.migrations.cache
======================
Re-exports from sqlfy.cache (canonical location, kept there for test monkeypatching).
"""
from __future__ import annotations

from ..cache import _CACHE_ROOT, clear_cache, load_cached, save_cached

__all__ = ["load_cached", "save_cached", "clear_cache", "_CACHE_ROOT"]
