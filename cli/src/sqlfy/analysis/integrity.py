"""Migration file integrity checking using SHA256 hashes.

Detects tampering or edits to migration files by maintaining a manifest
of file hashes and comparing current state against recorded state.
"""

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


@dataclass
class MigrationHash:
    """Hash record for a migration file."""

    filename: str
    version: str
    hash: str
    first_seen: str
    last_modified: str | None = None


@dataclass
class IntegrityReport:
    """Result of integrity check."""

    status: Literal["clean", "modified", "missing"]
    total_migrations: int
    modified: list[dict]
    missing: list[dict]
    new: list[dict]


def compute_file_hash(path: Path) -> str:
    """Compute SHA256 of file contents (normalized line endings).

    Args:
        path: Path to the file.

    Returns:
        SHA256 hex digest of file contents.
    """
    content = path.read_bytes()
    # Normalize CRLF -> LF to prevent hash changes on Windows/Unix
    content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def load_manifest(manifest_path: Path) -> dict[str, MigrationHash]:
    """Load migration hash manifest.

    Args:
        manifest_path: Path to .sqlfy-manifest.json file.

    Returns:
        Dictionary mapping filename to MigrationHash.
    """
    if not manifest_path.exists():
        return {}

    try:
        data = json.loads(manifest_path.read_text())
        return {
            entry["filename"]: MigrationHash(
                filename=entry["filename"],
                version=entry["version"],
                hash=entry["hash"],
                first_seen=entry["first_seen"],
                last_modified=entry.get("last_modified"),
            )
            for entry in data.get("migrations", [])
        }
    except (json.JSONDecodeError, KeyError, OSError):
        return {}


def save_manifest(manifest: dict[str, MigrationHash], manifest_path: Path) -> None:
    """Save migration hash manifest atomically.

    Args:
        manifest: Dictionary of migration hashes.
        manifest_path: Path to .sqlfy-manifest.json file.
    """
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "version": "1.0",
        "migrations": [
            {
                "filename": m.filename,
                "version": m.version,
                "hash": m.hash,
                "first_seen": m.first_seen,
                "last_modified": m.last_modified,
            }
            for m in manifest.values()
        ],
    }

    fd, tmp = tempfile.mkstemp(dir=manifest_path.parent, suffix=".tmp")
    try:
        os.write(fd, json.dumps(data, indent=2).encode())
        os.close(fd)
        os.replace(tmp, manifest_path)
    except Exception:
        try:
            os.close(fd)
        except:
            pass
        try:
            os.unlink(tmp)
        except:
            pass
        raise


def check_integrity(migrations_dir: Path) -> IntegrityReport:
    """Check migration file integrity against manifest.

    Args:
        migrations_dir: Path to directory containing migration files.

    Returns:
        IntegrityReport with status and lists of modified/missing/new files.
    """
    manifest_path = migrations_dir / ".sqlfy-manifest.json"
    manifest = load_manifest(manifest_path)

    sql_files = sorted(
        f for f in migrations_dir.iterdir() if f.suffix.lower() == ".sql" and f.name.startswith("V")
    )

    modified = []
    missing = []
    new = []

    current_files = {f.name: f for f in sql_files}

    # Check for modified/missing files
    for filename, entry in manifest.items():
        if filename not in current_files:
            missing.append(
                {
                    "filename": filename,
                    "version": entry.version,
                    "hash": entry.hash,
                }
            )
        else:
            current_hash = compute_file_hash(current_files[filename])
            if current_hash != entry.hash:
                modified.append(
                    {
                        "filename": filename,
                        "version": entry.version,
                        "old_hash": entry.hash,
                        "new_hash": current_hash,
                    }
                )

    # Check for new files
    for filename, filepath in current_files.items():
        if filename not in manifest:
            # Extract version from filename (V1__name.sql -> 1)
            version = filename.split("__")[0][1:] if "__" in filename else "?"
            current_hash = compute_file_hash(filepath)
            new.append(
                {
                    "filename": filename,
                    "version": version,
                    "hash": current_hash,
                }
            )

    status: Literal["clean", "modified", "missing"] = "clean"
    if modified:
        status = "modified"
    elif missing:
        status = "missing"

    return IntegrityReport(
        status=status,
        total_migrations=len(current_files),
        modified=modified,
        missing=missing,
        new=new,
    )


def update_manifest(migrations_dir: Path) -> None:
    """Update manifest with current file hashes.

    Args:
        migrations_dir: Path to directory containing migration files.
    """
    manifest_path = migrations_dir / ".sqlfy-manifest.json"
    manifest = load_manifest(manifest_path)

    sql_files = sorted(
        f for f in migrations_dir.iterdir() if f.suffix.lower() == ".sql" and f.name.startswith("V")
    )

    now = datetime.now(timezone.utc).isoformat()

    for f in sql_files:
        current_hash = compute_file_hash(f)
        version = f.name.split("__")[0][1:] if "__" in f.name else "?"

        if f.name in manifest:
            # Update existing entry if hash changed
            if manifest[f.name].hash != current_hash:
                manifest[f.name].hash = current_hash
                manifest[f.name].last_modified = now
        else:
            # New migration
            manifest[f.name] = MigrationHash(
                filename=f.name,
                version=version,
                hash=current_hash,
                first_seen=now,
            )

    # Remove deleted files from manifest
    current_filenames = {f.name for f in sql_files}
    manifest = {k: v for k, v in manifest.items() if k in current_filenames}

    save_manifest(manifest, manifest_path)
