"""Tests for migration file integrity checking."""

import json
from pathlib import Path

import pytest

from sqlfy.analysis.integrity import (
    IntegrityReport,
    MigrationHash,
    check_integrity,
    compute_file_hash,
    load_manifest,
    save_manifest,
    update_manifest,
)


def test_compute_file_hash(tmp_path):
    """Test SHA256 hash computation with line ending normalization."""
    f = tmp_path / "test.sql"
    f.write_text("SELECT * FROM users;\n")
    hash1 = compute_file_hash(f)
    
    # Same content should produce same hash
    hash2 = compute_file_hash(f)
    assert hash1 == hash2
    
    # Different content should produce different hash
    f.write_text("SELECT * FROM orders;\n")
    hash3 = compute_file_hash(f)
    assert hash1 != hash3


def test_compute_file_hash_normalizes_line_endings(tmp_path):
    """Test that CRLF and LF produce the same hash."""
    f1 = tmp_path / "unix.sql"
    f2 = tmp_path / "windows.sql"
    
    f1.write_bytes(b"SELECT * FROM users;\n")
    f2.write_bytes(b"SELECT * FROM users;\r\n")
    
    hash1 = compute_file_hash(f1)
    hash2 = compute_file_hash(f2)
    
    assert hash1 == hash2


def test_save_and_load_manifest(tmp_path):
    """Test manifest serialization and deserialization."""
    manifest_path = tmp_path / ".sqlfy-manifest.json"
    
    manifest = {
        "V1__create_users.sql": MigrationHash(
            filename="V1__create_users.sql",
            version="1",
            hash="abc123",
            first_seen="2026-05-26T10:00:00Z",
        ),
        "V2__add_orders.sql": MigrationHash(
            filename="V2__add_orders.sql",
            version="2",
            hash="def456",
            first_seen="2026-05-26T10:01:00Z",
            last_modified="2026-05-26T10:05:00Z",
        ),
    }
    
    save_manifest(manifest, manifest_path)
    assert manifest_path.exists()
    
    loaded = load_manifest(manifest_path)
    assert len(loaded) == 2
    assert loaded["V1__create_users.sql"].hash == "abc123"
    assert loaded["V2__add_orders.sql"].last_modified == "2026-05-26T10:05:00Z"


def test_load_manifest_missing_file(tmp_path):
    """Test loading manifest when file doesn't exist."""
    manifest_path = tmp_path / ".sqlfy-manifest.json"
    loaded = load_manifest(manifest_path)
    assert loaded == {}


def test_load_manifest_corrupted_file(tmp_path):
    """Test loading manifest with corrupted JSON."""
    manifest_path = tmp_path / ".sqlfy-manifest.json"
    manifest_path.write_text("not valid json{")
    
    loaded = load_manifest(manifest_path)
    assert loaded == {}


def test_check_integrity_clean(tmp_path):
    """Test integrity check with no changes."""
    # Create migrations
    (tmp_path / "V1__create_users.sql").write_text("CREATE TABLE users (id NUMBER);")
    (tmp_path / "V2__add_orders.sql").write_text("CREATE TABLE orders (id NUMBER);")
    
    # Initialize manifest
    update_manifest(tmp_path)
    
    # Check integrity
    report = check_integrity(tmp_path)
    
    assert report.status == "clean"
    assert report.total_migrations == 2
    assert len(report.modified) == 0
    assert len(report.missing) == 0
    assert len(report.new) == 0


def test_check_integrity_modified(tmp_path):
    """Test integrity check with modified file."""
    # Create migration and manifest
    f = tmp_path / "V1__create_users.sql"
    f.write_text("CREATE TABLE users (id NUMBER);")
    update_manifest(tmp_path)
    
    # Modify the file
    f.write_text("CREATE TABLE users (id NUMBER PRIMARY KEY);")
    
    # Check integrity
    report = check_integrity(tmp_path)
    
    assert report.status == "modified"
    assert report.total_migrations == 1
    assert len(report.modified) == 1
    assert report.modified[0]["filename"] == "V1__create_users.sql"
    assert report.modified[0]["version"] == "1"
    assert "old_hash" in report.modified[0]
    assert "new_hash" in report.modified[0]
    assert report.modified[0]["old_hash"] != report.modified[0]["new_hash"]


def test_check_integrity_missing(tmp_path):
    """Test integrity check with missing file."""
    # Create migration and manifest
    f = tmp_path / "V1__create_users.sql"
    f.write_text("CREATE TABLE users (id NUMBER);")
    update_manifest(tmp_path)
    
    # Delete the file
    f.unlink()
    
    # Check integrity
    report = check_integrity(tmp_path)
    
    assert report.status == "missing"
    assert report.total_migrations == 0
    assert len(report.missing) == 1
    assert report.missing[0]["filename"] == "V1__create_users.sql"
    assert report.missing[0]["version"] == "1"


def test_check_integrity_new(tmp_path):
    """Test integrity check with new file."""
    # Create first migration and manifest
    (tmp_path / "V1__create_users.sql").write_text("CREATE TABLE users (id NUMBER);")
    update_manifest(tmp_path)
    
    # Add new migration
    (tmp_path / "V2__add_orders.sql").write_text("CREATE TABLE orders (id NUMBER);")
    
    # Check integrity
    report = check_integrity(tmp_path)
    
    assert report.status == "clean"  # New files don't cause "modified" status
    assert report.total_migrations == 2
    assert len(report.new) == 1
    assert report.new[0]["filename"] == "V2__add_orders.sql"
    assert report.new[0]["version"] == "2"


def test_check_integrity_no_manifest(tmp_path):
    """Test integrity check with no existing manifest."""
    # Create migrations
    (tmp_path / "V1__create_users.sql").write_text("CREATE TABLE users (id NUMBER);")
    (tmp_path / "V2__add_orders.sql").write_text("CREATE TABLE orders (id NUMBER);")
    
    # Check integrity without manifest
    report = check_integrity(tmp_path)
    
    assert report.status == "clean"
    assert report.total_migrations == 2
    assert len(report.new) == 2


def test_update_manifest_new_files(tmp_path):
    """Test updating manifest with new files."""
    # Create migrations
    (tmp_path / "V1__create_users.sql").write_text("CREATE TABLE users (id NUMBER);")
    (tmp_path / "V2__add_orders.sql").write_text("CREATE TABLE orders (id NUMBER);")
    
    # Update manifest
    update_manifest(tmp_path)
    
    # Load and verify
    manifest = load_manifest(tmp_path / ".sqlfy-manifest.json")
    assert len(manifest) == 2
    assert "V1__create_users.sql" in manifest
    assert "V2__add_orders.sql" in manifest
    assert manifest["V1__create_users.sql"].version == "1"
    assert manifest["V2__add_orders.sql"].version == "2"


def test_update_manifest_modified_file(tmp_path):
    """Test updating manifest after file modification."""
    # Create migration and manifest
    f = tmp_path / "V1__create_users.sql"
    f.write_text("CREATE TABLE users (id NUMBER);")
    update_manifest(tmp_path)
    
    manifest1 = load_manifest(tmp_path / ".sqlfy-manifest.json")
    old_hash = manifest1["V1__create_users.sql"].hash
    
    # Modify file
    f.write_text("CREATE TABLE users (id NUMBER PRIMARY KEY);")
    update_manifest(tmp_path)
    
    # Verify hash changed and last_modified set
    manifest2 = load_manifest(tmp_path / ".sqlfy-manifest.json")
    assert manifest2["V1__create_users.sql"].hash != old_hash
    assert manifest2["V1__create_users.sql"].last_modified is not None


def test_update_manifest_removed_file(tmp_path):
    """Test that removed files are deleted from manifest."""
    # Create migrations and manifest
    (tmp_path / "V1__create_users.sql").write_text("CREATE TABLE users (id NUMBER);")
    (tmp_path / "V2__add_orders.sql").write_text("CREATE TABLE orders (id NUMBER);")
    update_manifest(tmp_path)
    
    # Remove one migration
    (tmp_path / "V2__add_orders.sql").unlink()
    update_manifest(tmp_path)
    
    # Verify removed from manifest
    manifest = load_manifest(tmp_path / ".sqlfy-manifest.json")
    assert len(manifest) == 1
    assert "V1__create_users.sql" in manifest
    assert "V2__add_orders.sql" not in manifest


def test_manifest_atomic_write(tmp_path):
    """Test that manifest writes are atomic (temp file + replace)."""
    manifest_path = tmp_path / ".sqlfy-manifest.json"
    
    manifest = {
        "V1__create_users.sql": MigrationHash(
            filename="V1__create_users.sql",
            version="1",
            hash="abc123",
            first_seen="2026-05-26T10:00:00Z",
        )
    }
    
    save_manifest(manifest, manifest_path)
    
    # Verify no .tmp files left behind
    assert manifest_path.exists()
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0


def test_version_extraction_from_filename(tmp_path):
    """Test version extraction from different filename patterns."""
    # Standard pattern
    (tmp_path / "V1__create_users.sql").write_text("CREATE TABLE users (id NUMBER);")
    # With leading zeros
    (tmp_path / "V002__add_orders.sql").write_text("CREATE TABLE orders (id NUMBER);")
    # No description
    (tmp_path / "V3.sql").write_text("CREATE TABLE products (id NUMBER);")
    
    report = check_integrity(tmp_path)
    
    versions = {item["version"] for item in report.new}
    assert "1" in versions
    assert "002" in versions
    assert "?" in versions  # V3.sql doesn't have __ separator


def test_ignores_non_versioned_files(tmp_path):
    """Test that non-V*.sql files are ignored."""
    (tmp_path / "V1__create_users.sql").write_text("CREATE TABLE users (id NUMBER);")
    (tmp_path / "README.md").write_text("# Migrations")
    (tmp_path / "seed_data.sql").write_text("INSERT INTO users VALUES (1);")
    (tmp_path / "U1__undo.sql").write_text("DROP TABLE users;")
    
    report = check_integrity(tmp_path)
    
    assert report.total_migrations == 1
    assert len(report.new) == 1
    assert report.new[0]["filename"] == "V1__create_users.sql"
