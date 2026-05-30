"""Chunk and embedding caching for RAG pipeline.

Caches built chunks and their embeddings keyed by schema fingerprint.
After the first run, sqlfy ask becomes instant instead of re-building chunks.
"""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..domain.models import VectorChunk

# Try to import numpy for embedding cache support
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]
    HAS_NUMPY = False

# Cache root directory
_CHUNK_CACHE_ROOT = Path(os.environ.get("SQLFY_CHUNK_CACHE_DIR", ".sqlfy-cache"))


def compute_schema_fingerprint(files: list[dict]) -> str:
    """Compute deterministic fingerprint of all migrations.
    
    Returns SHA256(concat(filename, sql) for each file).
    
    Args:
        files: List of dicts with {filename, sql} for each migration.
    
    Returns:
        SHA256 hex digest representing the entire migration set.
    """
    hasher = hashlib.sha256()
    
    for f in sorted(files, key=lambda x: x["filename"]):
        hasher.update(f["filename"].encode())
        hasher.update(b"\x00")
        hasher.update(f["sql"].encode())
        hasher.update(b"\x00")
    
    return hasher.hexdigest()


class ChunkCache:
    """Cache for LLM chunks and embeddings keyed by schema fingerprint."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize chunk cache.
        
        Args:
            cache_dir: Custom cache directory (defaults to .sqlfy-cache).
        """
        self.cache_dir = cache_dir or _CHUNK_CACHE_ROOT
        self.cache_dir.mkdir(exist_ok=True, parents=True)
    
    def get(self, fingerprint: str) -> Optional[tuple[list[VectorChunk], Optional[Any]]]:
        """Load cached chunks and embeddings.
        
        Args:
            fingerprint: Schema fingerprint from compute_schema_fingerprint().
        
        Returns:
            Tuple of (chunks, embeddings) if found, else None.
            embeddings will be None if numpy is not available or if no embeddings were cached.
        """
        cache_path = self.cache_dir / fingerprint
        
        if not cache_path.exists():
            return None
        
        # Load manifest
        manifest_file = cache_path / "manifest.json"
        if not manifest_file.exists():
            return None
        
        try:
            manifest = json.loads(manifest_file.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        
        # Load chunks
        chunks_file = cache_path / "chunks.json"
        if not chunks_file.exists():
            return None
        
        try:
            chunks_data = json.loads(chunks_file.read_text())
            chunks = [
                VectorChunk(
                    id=c["id"],
                    title=c["title"],
                    type=c["type"],
                    content=c["content"],
                    hint=c.get("hint", ""),
                    meta=c.get("meta", {}),
                )
                for c in chunks_data
            ]
        except (json.JSONDecodeError, KeyError, OSError):
            return None
        
        # Load embeddings if available
        embeddings = None
        embeddings_file = cache_path / "embeddings.npy"
        if HAS_NUMPY and embeddings_file.exists():
            assert np is not None
            try:
                embeddings = np.load(embeddings_file)
            except (OSError, ValueError):
                pass
        
        return chunks, embeddings
    
    def put(
        self,
        fingerprint: str,
        chunks: list[VectorChunk],
        embeddings: Optional[Any] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Save chunks and embeddings to cache.
        
        Args:
            fingerprint: Schema fingerprint from compute_schema_fingerprint().
            chunks: List of VectorChunk objects to cache.
            embeddings: Optional numpy array of embeddings (requires numpy).
            metadata: Optional metadata dict to store in manifest.
        """
        cache_path = self.cache_dir / fingerprint
        cache_path.mkdir(parents=True, exist_ok=True)
        
        # Serialize chunks
        chunks_data = [
            {
                "id": c.id,
                "title": c.title,
                "type": c.type,
                "content": c.content,
                "hint": c.hint,
                "meta": c.meta,
            }
            for c in chunks
        ]
        
        # Write chunks atomically
        chunks_file = cache_path / "chunks.json"
        fd, tmp = tempfile.mkstemp(dir=cache_path, suffix=".tmp")
        try:
            os.write(fd, json.dumps(chunks_data, indent=2, default=str).encode())
            os.close(fd)
            os.replace(tmp, chunks_file)
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
        
        # Write embeddings if available
        if HAS_NUMPY and embeddings is not None:
            assert np is not None
            embeddings_file = cache_path / "embeddings.npy"
            try:
                np.save(embeddings_file, embeddings)
            except Exception:
                pass  # Non-fatal if embeddings can't be saved
        
        # Write manifest
        manifest = {
            "schema_fingerprint": fingerprint,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "chunks_count": len(chunks),
            "has_embeddings": HAS_NUMPY and embeddings is not None,
            **(metadata or {}),
        }
        
        if HAS_NUMPY and embeddings is not None:
            manifest["embedding_dim"] = embeddings.shape[1]
        
        manifest_file = cache_path / "manifest.json"
        fd, tmp = tempfile.mkstemp(dir=cache_path, suffix=".tmp")
        try:
            os.write(fd, json.dumps(manifest, indent=2).encode())
            os.close(fd)
            os.replace(tmp, manifest_file)
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
    
    def clear(self) -> None:
        """Delete all cached entries."""
        if self.cache_dir.exists():
            for cache_entry in self.cache_dir.iterdir():
                if cache_entry.is_dir():
                    # Delete all files in the cache entry
                    for f in cache_entry.iterdir():
                        try:
                            f.unlink()
                        except OSError:
                            pass
                    # Delete the directory
                    try:
                        cache_entry.rmdir()
                    except OSError:
                        pass
    
    def gc(self, keep_latest: int = 5) -> None:
        """Garbage collect old cache entries, keep N most recent.
        
        Args:
            keep_latest: Number of most recent cache entries to keep.
        """
        if not self.cache_dir.exists():
            return
        
        # Get all cache entries with their timestamps
        entries = []
        for cache_entry in self.cache_dir.iterdir():
            if not cache_entry.is_dir():
                continue
            
            manifest_file = cache_entry / "manifest.json"
            if manifest_file.exists():
                try:
                    manifest = json.loads(manifest_file.read_text())
                    created_at = manifest.get("created_at", "")
                    entries.append((cache_entry, created_at))
                except (json.JSONDecodeError, OSError):
                    # Invalid entry, mark for deletion
                    entries.append((cache_entry, ""))
        
        # Sort by timestamp (newest first)
        entries.sort(key=lambda x: x[1], reverse=True)
        
        # Delete old entries
        for cache_entry, _ in entries[keep_latest:]:
            for f in cache_entry.iterdir():
                try:
                    f.unlink()
                except OSError:
                    pass
            try:
                cache_entry.rmdir()
            except OSError:
                pass
    
    def info(self) -> dict:
        """Get cache statistics.
        
        Returns:
            Dict with cache_location, entry_count, total_size_mb.
        """
        if not self.cache_dir.exists():
            return {
                "cache_location": str(self.cache_dir),
                "entry_count": 0,
                "total_size_mb": 0.0,
            }
        
        entry_count = 0
        total_size = 0
        
        for cache_entry in self.cache_dir.iterdir():
            if cache_entry.is_dir():
                entry_count += 1
                for f in cache_entry.iterdir():
                    try:
                        total_size += f.stat().st_size
                    except OSError:
                        pass
        
        return {
            "cache_location": str(self.cache_dir),
            "entry_count": entry_count,
            "total_size_mb": total_size / (1024 * 1024),
        }
