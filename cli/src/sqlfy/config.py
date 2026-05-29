"""
sqlfy.config
============
Central configuration for the sqlfy tool.

Settings are resolved in priority order (highest wins):
  1. Environment variables (``SQLFY_*`` prefix)
  2. ``sqlfy.toml`` in the current working directory
  3. ``~/.config/sqlfy/config.toml`` (user-level)
  4. Built-in defaults

Example ``sqlfy.toml``::

    [sqlfy]
    dialect = "postgres"
    cache_dir = ".cache/sqlfy"
    log_level = "DEBUG"

Import the singleton::

    from sqlfy.config import settings
    print(settings.dialect)
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


_TOML_KEYS = {
    "dialect", "cache_dir", "chunk_cache_dir", "log_level", "api_key", "max_chunks"
}


def _load_toml_config() -> dict:
    """Load config from sqlfy.toml files (cwd first, then ~/.config/sqlfy)."""
    candidates = [
        Path.cwd() / "sqlfy.toml",
        Path.home() / ".config" / "sqlfy" / "config.toml",
    ]
    for path in candidates:
        if path.exists():
            try:
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                return {k: v for k, v in data.get("sqlfy", {}).items() if k in _TOML_KEYS}
            except Exception:
                pass
    return {}


@dataclass(frozen=True)
class SqlfySettings:
    """Runtime settings for sqlfy.

    Attributes:
        dialect: Default SQL dialect (oracle/postgres/mysql/sqlite).
        cache_dir: Directory for .sql file parse cache.
        chunk_cache_dir: Directory for vector chunk cache.
        log_level: Logging level (DEBUG/INFO/WARNING/ERROR).
        api_key: Anthropic API key for LLM features.
        max_chunks: Maximum number of chunks for RAG retrieval.
    """

    dialect: str = "oracle"
    cache_dir: str = "sqlfy-out/cache"
    chunk_cache_dir: str = ".sqlfy-cache"
    log_level: str = "WARNING"
    api_key: str = ""
    max_chunks: int = 6

    @classmethod
    def from_env(cls) -> "SqlfySettings":
        """Create settings from TOML files and environment variables.

        Environment variables take precedence over TOML config files.
        """
        toml = _load_toml_config()
        return cls(
            dialect=os.environ.get("SQLFY_DIALECT", toml.get("dialect", "oracle")),
            cache_dir=os.environ.get("SQLFY_CACHE_DIR", toml.get("cache_dir", "sqlfy-out/cache")),
            chunk_cache_dir=os.environ.get(
                "SQLFY_CHUNK_CACHE_DIR", toml.get("chunk_cache_dir", ".sqlfy-cache")
            ),
            log_level=os.environ.get("SQLFY_LOG_LEVEL", toml.get("log_level", "WARNING")),
            api_key=os.environ.get(
                "SQLFY_API_KEY",
                toml.get("api_key", os.environ.get("ANTHROPIC_API_KEY", "")),
            ),
            max_chunks=int(os.environ.get(
                "SQLFY_MAX_CHUNKS", toml.get("max_chunks", 6)
            )),
        )


# Module-level singleton — lazily initialized from env + TOML
settings: SqlfySettings = SqlfySettings.from_env()

__all__ = ["SqlfySettings", "settings"]
