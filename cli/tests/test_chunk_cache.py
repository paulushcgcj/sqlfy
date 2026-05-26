"""Tests for chunk caching."""

import json
from pathlib import Path

import pytest

from sqlfy.analysis.chunk_cache import ChunkCache, compute_schema_fingerprint
from sqlfy.domain.models import VectorChunk


def test_compute_schema_fingerprint_basic():
    """Test basic schema fingerprint computation."""
    files = [
        {"filename": "V1__create_users.sql", "sql": "CREATE TABLE users (id NUMBER);"},
        {"filename": "V2__add_orders.sql", "sql": "CREATE TABLE orders (id NUMBER);"},
    ]
    
    fp1 = compute_schema_fingerprint(files)
    assert len(fp1) == 64  # SHA256 hex digest
    
    # Same files should produce same fingerprint
    fp2 = compute_schema_fingerprint(files)
    assert fp1 == fp2


def test_compute_schema_fingerprint_order_independent():
    """Test that fingerprint is deterministic (files are sorted internally)."""
    files1 = [
        {"filename": "V1__create_users.sql", "sql": "CREATE TABLE users (id NUMBER);"},
        {"filename": "V2__add_orders.sql", "sql": "CREATE TABLE orders (id NUMBER);"},
    ]
    
    files2 = [
        {"filename": "V2__add_orders.sql", "sql": "CREATE TABLE orders (id NUMBER);"},
        {"filename": "V1__create_users.sql", "sql": "CREATE TABLE users (id NUMBER);"},
    ]
    
    fp1 = compute_schema_fingerprint(files1)
    fp2 = compute_schema_fingerprint(files2)
    
    assert fp1 == fp2


def test_compute_schema_fingerprint_changes_on_modification():
    """Test that fingerprint changes when migrations are modified."""
    files1 = [
        {"filename": "V1__create_users.sql", "sql": "CREATE TABLE users (id NUMBER);"},
    ]
    
    files2 = [
        {"filename": "V1__create_users.sql", "sql": "CREATE TABLE users (id NUMBER PRIMARY KEY);"},
    ]
    
    fp1 = compute_schema_fingerprint(files1)
    fp2 = compute_schema_fingerprint(files2)
    
    assert fp1 != fp2


def test_chunk_cache_save_and_load(tmp_path, monkeypatch):
    """Test saving and loading chunks from cache."""
    # Use tmp_path as cache root
    monkeypatch.setattr("sqlfy.analysis.chunk_cache._CHUNK_CACHE_ROOT", tmp_path)
    
    cache = ChunkCache()
    fingerprint = "test123"
    
    chunks = [
        VectorChunk(
            id="chunk1",
            title="Table: USERS",
            type="table",
            content="CREATE TABLE users (id NUMBER);",
            hint="Primary key on ID",
            meta={"schema": "public"},
        ),
        VectorChunk(
            id="chunk2",
            title="Table: ORDERS",
            type="table",
            content="CREATE TABLE orders (id NUMBER);",
            hint="Foreign key to users",
            meta={"schema": "public"},
        ),
    ]
    
    # Save to cache
    cache.put(fingerprint, chunks)
    
    # Load from cache
    loaded = cache.get(fingerprint)
    assert loaded is not None
    
    loaded_chunks, loaded_embeddings = loaded
    assert len(loaded_chunks) == 2
    assert loaded_chunks[0].id == "chunk1"
    assert loaded_chunks[0].title == "Table: USERS"
    assert loaded_chunks[1].id == "chunk2"
    assert loaded_embeddings is None  # No numpy available


def test_chunk_cache_miss(tmp_path, monkeypatch):
    """Test cache miss when fingerprint doesn't exist."""
    # Use tmp_path as cache root
    monkeypatch.setattr("sqlfy.analysis.chunk_cache._CHUNK_CACHE_ROOT", tmp_path)
    
    cache = ChunkCache()
    result = cache.get("nonexistent_fingerprint")
    
    assert result is None


def test_chunk_cache_clear(tmp_path, monkeypatch):
    """Test clearing cache."""
    # Use tmp_path as cache root
    monkeypatch.setattr("sqlfy.analysis.chunk_cache._CHUNK_CACHE_ROOT", tmp_path)
    
    cache = ChunkCache()
    fingerprint = "test456"
    
    chunks = [
        VectorChunk(
            id="chunk1",
            title="Test",
            type="table",
            content="...",
            hint="",
            meta={},
        )
    ]
    
    cache.put(fingerprint, chunks)
    
    # Verify cache exists
    assert cache.get(fingerprint) is not None
    
    # Clear cache
    cache.clear()
    
    # Verify cache is cleared
    assert cache.get(fingerprint) is None


def test_chunk_cache_gc(tmp_path, monkeypatch):
    """Test garbage collection of old cache entries."""
    # Use tmp_path as cache root
    monkeypatch.setattr("sqlfy.analysis.chunk_cache._CHUNK_CACHE_ROOT", tmp_path)
    
    cache = ChunkCache()
    
    chunks = [
        VectorChunk(
            id="chunk1",
            title="Test",
            type="table",
            content="...",
            hint="",
            meta={},
        )
    ]
    
    # Create 10 cache entries
    for i in range(10):
        cache.put(f"fingerprint_{i}", chunks)
    
    # Run GC, keep only 5 most recent
    cache.gc(keep_latest=5)
    
    # Verify only 5 entries remain
    info = cache.info()
    assert info["entry_count"] == 5


def test_chunk_cache_info(tmp_path, monkeypatch):
    """Test cache info statistics."""
    # Use tmp_path as cache root
    monkeypatch.setattr("sqlfy.analysis.chunk_cache._CHUNK_CACHE_ROOT", tmp_path)
    
    cache = ChunkCache()
    
    # Empty cache
    info = cache.info()
    assert info["entry_count"] == 0
    assert info["total_size_mb"] == 0.0
    
    # Add some entries
    chunks = [
        VectorChunk(
            id="chunk1",
            title="Test",
            type="table",
            content="CREATE TABLE users (id NUMBER, name VARCHAR2(100));",
            hint="",
            meta={},
        )
    ]
    
    for i in range(3):
        cache.put(f"fingerprint_{i}", chunks)
    
    # Check info
    info = cache.info()
    assert info["entry_count"] == 3
    assert info["total_size_mb"] > 0.0


def test_chunk_cache_metadata(tmp_path, monkeypatch):
    """Test that cache stores metadata."""
    # Use tmp_path as cache root
    monkeypatch.setattr("sqlfy.analysis.chunk_cache._CHUNK_CACHE_ROOT", tmp_path)
    
    cache = ChunkCache()
    fingerprint = "test789"
    
    chunks = [
        VectorChunk(
            id="chunk1",
            title="Test",
            type="table",
            content="...",
            hint="",
            meta={},
        )
    ]
    
    metadata = {"dialect": "oracle", "version": "3"}
    cache.put(fingerprint, chunks, metadata=metadata)
    
    # Read manifest directly
    manifest_file = tmp_path / fingerprint / "manifest.json"
    assert manifest_file.exists()
    
    manifest = json.loads(manifest_file.read_text())
    assert manifest["schema_fingerprint"] == fingerprint
    assert manifest["chunks_count"] == 1
    assert manifest["dialect"] == "oracle"
    assert manifest["version"] == "3"
    assert "created_at" in manifest


def test_chunk_cache_corrupted_manifest(tmp_path, monkeypatch):
    """Test handling of corrupted manifest file."""
    # Use tmp_path as cache root
    monkeypatch.setattr("sqlfy.analysis.chunk_cache._CHUNK_CACHE_ROOT", tmp_path)
    
    cache = ChunkCache()
    fingerprint = "corrupted"
    
    # Create cache directory with corrupted manifest
    cache_dir = tmp_path / fingerprint
    cache_dir.mkdir()
    (cache_dir / "manifest.json").write_text("not valid json{")
    
    # Should return None for corrupted cache
    result = cache.get(fingerprint)
    assert result is None


def test_chunk_cache_atomic_write(tmp_path, monkeypatch):
    """Test that cache writes are atomic (no .tmp files left behind)."""
    # Use tmp_path as cache root
    monkeypatch.setattr("sqlfy.analysis.chunk_cache._CHUNK_CACHE_ROOT", tmp_path)
    
    cache = ChunkCache()
    fingerprint = "atomic"
    
    chunks = [
        VectorChunk(
            id="chunk1",
            title="Test",
            type="table",
            content="...",
            hint="",
            meta={},
        )
    ]
    
    cache.put(fingerprint, chunks)
    
    # Verify no .tmp files left behind
    cache_dir = tmp_path / fingerprint
    tmp_files = list(cache_dir.glob("*.tmp"))
    assert len(tmp_files) == 0
