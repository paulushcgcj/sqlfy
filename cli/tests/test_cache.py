"""Tests for file-based caching."""

import json
from pathlib import Path

import pytest

from sqlfy.cache import (
    _CACHE_ROOT,
    _save_stat_index,
    _stat_index,
    clear_cache,
    file_hash,
    load_cached,
    save_cached,
)


def test_file_hash_basic(tmp_path):
    """Test basic file hash computation."""
    f = tmp_path / "test.sql"
    f.write_text("SELECT * FROM users;")
    
    hash1 = file_hash(f)
    assert len(hash1) == 64  # SHA256 hex digest
    
    # Same file should produce same hash
    hash2 = file_hash(f)
    assert hash1 == hash2


def test_file_hash_different_content(tmp_path):
    """Test that different content produces different hash."""
    f1 = tmp_path / "test1.sql"
    f2 = tmp_path / "test2.sql"
    
    f1.write_text("SELECT * FROM users;")
    f2.write_text("SELECT * FROM orders;")
    
    hash1 = file_hash(f1)
    hash2 = file_hash(f2)
    
    assert hash1 != hash2


def test_file_hash_different_filename(tmp_path):
    """Test that different filename produces different hash."""
    f1 = tmp_path / "test1.sql"
    f2 = tmp_path / "test2.sql"
    
    # Same content
    content = "SELECT * FROM users;"
    f1.write_text(content)
    f2.write_text(content)
    
    hash1 = file_hash(f1)
    hash2 = file_hash(f2)
    
    # Different filenames should produce different hashes
    assert hash1 != hash2


def test_file_hash_stat_fastpath(tmp_path):
    """Test stat-based fastpath optimization."""
    f = tmp_path / "test.sql"
    f.write_text("SELECT * FROM users;")
    
    # First call computes full hash
    hash1 = file_hash(f)
    
    # Stat entry should be cached
    abs_key = str(f.resolve())
    assert abs_key in _stat_index
    assert _stat_index[abs_key]["hash"] == hash1
    
    # Second call should use stat fastpath (no file read)
    hash2 = file_hash(f)
    assert hash1 == hash2


def test_file_hash_invalidates_on_modification(tmp_path):
    """Test that hash changes when file is modified."""
    f = tmp_path / "test.sql"
    f.write_text("SELECT * FROM users;")
    
    hash1 = file_hash(f)
    
    # Modify file
    f.write_text("SELECT * FROM orders;")
    
    hash2 = file_hash(f)
    
    # Hash should change
    assert hash1 != hash2


def test_save_and_load_cached(tmp_path, monkeypatch):
    """Test caching and retrieving parse results."""
    # Use tmp_path as cache root
    monkeypatch.setattr("sqlfy.cache._CACHE_ROOT", tmp_path)
    
    f = tmp_path / "V1__test.sql"
    f.write_text("CREATE TABLE users (id NUMBER);")
    
    # Cache a result
    result = {"filename": "V1__test.sql", "sql": "CREATE TABLE users (id NUMBER);"}
    save_cached(f, result)
    
    # Load it back
    loaded = load_cached(f)
    assert loaded is not None
    assert loaded["filename"] == "V1__test.sql"
    assert loaded["sql"] == "CREATE TABLE users (id NUMBER);"


def test_load_cached_missing_file(tmp_path, monkeypatch):
    """Test loading cache when file doesn't exist in cache."""
    # Use tmp_path as cache root
    monkeypatch.setattr("sqlfy.cache._CACHE_ROOT", tmp_path)
    
    f = tmp_path / "V1__test.sql"
    f.write_text("CREATE TABLE users (id NUMBER);")
    
    # No cache entry exists
    loaded = load_cached(f)
    assert loaded is None


def test_load_cached_corrupted_cache(tmp_path, monkeypatch):
    """Test loading cache when cache file is corrupted."""
    # Use tmp_path as cache root
    monkeypatch.setattr("sqlfy.cache._CACHE_ROOT", tmp_path)
    
    f = tmp_path / "V1__test.sql"
    f.write_text("CREATE TABLE users (id NUMBER);")
    
    # Save valid cache
    result = {"filename": "V1__test.sql", "sql": "CREATE TABLE users (id NUMBER);"}
    save_cached(f, result)
    
    # Corrupt the cache file
    h = file_hash(f)
    cache_file = tmp_path / "migrations" / f"{h}.json"
    cache_file.write_text("not valid json{")
    
    # Should return None for corrupted cache
    loaded = load_cached(f)
    assert loaded is None


def test_clear_cache(tmp_path, monkeypatch):
    """Test clearing all cache entries."""
    # Use tmp_path as cache root
    monkeypatch.setattr("sqlfy.cache._CACHE_ROOT", tmp_path)
    
    # Create some cache entries
    f1 = tmp_path / "V1__test.sql"
    f2 = tmp_path / "V2__test.sql"
    f1.write_text("CREATE TABLE users (id NUMBER);")
    f2.write_text("CREATE TABLE orders (id NUMBER);")
    
    save_cached(f1, {"filename": "V1__test.sql", "sql": "..."})
    save_cached(f2, {"filename": "V2__test.sql", "sql": "..."})
    
    # Save stat index
    _save_stat_index()
    
    # Verify cache exists
    cache_dir = tmp_path / "migrations"
    assert cache_dir.exists()
    assert len(list(cache_dir.glob("*.json"))) == 2
    
    stat_index = tmp_path / "stat-index.json"
    assert stat_index.exists()
    
    # Clear cache
    clear_cache()
    
    # Verify cache is empty
    assert len(list(cache_dir.glob("*.json"))) == 0
    assert not stat_index.exists()


def test_cache_atomic_write(tmp_path, monkeypatch):
    """Test that cache writes are atomic (temp file + replace)."""
    # Use tmp_path as cache root
    monkeypatch.setattr("sqlfy.cache._CACHE_ROOT", tmp_path)
    
    f = tmp_path / "V1__test.sql"
    f.write_text("CREATE TABLE users (id NUMBER);")
    
    result = {"filename": "V1__test.sql", "sql": "CREATE TABLE users (id NUMBER);"}
    save_cached(f, result)
    
    # Verify no .tmp files left behind
    cache_dir = tmp_path / "migrations"
    tmp_files = list(cache_dir.glob("*.tmp"))
    assert len(tmp_files) == 0


def test_cache_invalidation_on_content_change(tmp_path, monkeypatch):
    """Test that cache is invalidated when file content changes."""
    # Use tmp_path as cache root
    monkeypatch.setattr("sqlfy.cache._CACHE_ROOT", tmp_path)
    
    f = tmp_path / "V1__test.sql"
    f.write_text("CREATE TABLE users (id NUMBER);")
    
    # Cache original
    result1 = {"filename": "V1__test.sql", "sql": "CREATE TABLE users (id NUMBER);"}
    save_cached(f, result1)
    
    # Verify cached
    loaded1 = load_cached(f)
    assert loaded1 is not None
    
    # Modify file
    f.write_text("CREATE TABLE users (id NUMBER PRIMARY KEY);")
    
    # Cache should be invalidated (load returns None)
    loaded2 = load_cached(f)
    assert loaded2 is None


def test_multiple_cache_entries(tmp_path, monkeypatch):
    """Test caching multiple files."""
    # Use tmp_path as cache root
    monkeypatch.setattr("sqlfy.cache._CACHE_ROOT", tmp_path)
    
    files = []
    for i in range(5):
        f = tmp_path / f"V{i}__test.sql"
        f.write_text(f"CREATE TABLE table{i} (id NUMBER);")
        result = {"filename": f"V{i}__test.sql", "sql": f"CREATE TABLE table{i} (id NUMBER);"}
        save_cached(f, result)
        files.append(f)
    
    # Verify all are cached
    for f in files:
        loaded = load_cached(f)
        assert loaded is not None
    
    # Verify cache directory has 5 entries
    cache_dir = tmp_path / "migrations"
    assert len(list(cache_dir.glob("*.json"))) == 5
