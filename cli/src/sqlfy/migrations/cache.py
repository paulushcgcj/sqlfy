"""
sqlfy.migrations.cache
======================
Re-exports from sqlfy.cache (canonical location, kept there for test monkeypatching).
"""
from ..cache import load_cached, save_cached, clear_cache, _CACHE_ROOT

__all__ = ["load_cached", "save_cached", "clear_cache", "_CACHE_ROOT"]
