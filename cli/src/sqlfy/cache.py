"""File-based caching for migration parsing using SHA256 hashes.

Provides stat-based fast path to avoid re-parsing unchanged migrations.
Cache entries are stored in sqlfy-out/cache/ by default.
"""

import atexit
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

# Global cache configuration
_CACHE_ROOT = Path(os.environ.get("SQLFY_CACHE_DIR", "sqlfy-out/cache"))

# Stat index: maps absolute path to {size, mtime_ns, hash}
_stat_index: dict[str, dict] = {}
_stat_index_dirty: bool = False


def _load_stat_index() -> None:
    """Load stat index from disk once at module initialization."""
    global _stat_index
    index_file = _CACHE_ROOT / "stat-index.json"
    if index_file.exists():
        try:
            _stat_index = json.loads(index_file.read_text())
        except (json.JSONDecodeError, OSError):
            _stat_index = {}
    atexit.register(_save_stat_index)


def _save_stat_index() -> None:
    """Flush stat index to disk atomically on exit."""
    if not _stat_index_dirty:
        return
    index_file = _CACHE_ROOT / "stat-index.json"
    index_file.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=index_file.parent, suffix=".tmp")
    try:
        os.write(fd, json.dumps(_stat_index).encode())
        os.close(fd)
        os.replace(tmp, index_file)
    except Exception:
        try:
            os.close(fd)
        except:
            pass
        try:
            os.unlink(tmp)
        except:
            pass


def file_hash(path: Path) -> str:
    """Compute SHA256(content + filename).
    
    Uses stat-based fastpath: if size and mtime_ns match cached entry,
    return cached hash without reading file content.
    
    Args:
        path: Path to the file.
    
    Returns:
        SHA256 hex digest of file content + filename.
    """
    global _stat_index_dirty
    
    p = Path(path).resolve()
    abs_key = str(p)
    
    # Stat fastpath
    st = None
    try:
        st = p.stat()
        entry = _stat_index.get(abs_key)
        if entry and entry["size"] == st.st_size and entry["mtime_ns"] == st.st_mtime_ns:
            return entry["hash"]
    except OSError:
        pass
    
    # Cache miss — compute full SHA256
    content = p.read_bytes()
    h = hashlib.sha256()
    h.update(content)
    h.update(b"\x00")
    h.update(p.name.encode())  # Include filename for uniqueness
    digest = h.hexdigest()
    
    # Update stat index
    if st:
        _stat_index[abs_key] = {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "hash": digest}
        _stat_index_dirty = True
    
    return digest


def load_cached(path: Path) -> dict | None:
    """Load cached migration parse result.
    
    Args:
        path: Path to the migration file.
    
    Returns:
        Cached dict with {filename, sql} if found, else None.
    """
    h = file_hash(path)
    cache_file = _CACHE_ROOT / "migrations" / f"{h}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_cached(path: Path, result: dict) -> None:
    """Save migration parse result atomically.
    
    Args:
        path: Path to the migration file.
        result: Dict with {filename, sql} to cache.
    """
    h = file_hash(path)
    cache_dir = _CACHE_ROOT / "migrations"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{h}.json"
    
    fd, tmp = tempfile.mkstemp(dir=cache_dir, suffix=".tmp")
    try:
        os.write(fd, json.dumps(result).encode())
        os.close(fd)
        os.replace(tmp, cache_file)
    except Exception:
        try:
            os.close(fd)
        except:
            pass
        try:
            os.unlink(tmp)
        except:
            pass


def clear_cache() -> None:
    """Delete all cache entries and stat index."""
    cache_dir = _CACHE_ROOT / "migrations"
    if cache_dir.exists():
        for f in cache_dir.glob("*.json"):
            try:
                f.unlink()
            except OSError:
                pass
    stat_index = _CACHE_ROOT / "stat-index.json"
    if stat_index.exists():
        try:
            stat_index.unlink()
        except OSError:
            pass


# Load stat index once on import
_load_stat_index()
