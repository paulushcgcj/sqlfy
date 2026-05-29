"""
sqlfy.config
============
Central configuration for the sqlfy tool via environment variables.

All settings have ``SQLFY_`` prefix and can be overridden at runtime.
Example::

    export SQLFY_DIALECT=postgres
    export SQLFY_CACHE_DIR=.cache/sqlfy
    export SQLFY_LOG_LEVEL=DEBUG

Settings are loaded lazily — import ``settings`` to access them:

    from sqlfy.config import settings
    print(settings.dialect)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SqlfySettings:
    """Runtime settings for sqlfy, populated from environment variables.

    All env-var names are the field names uppercased with SQLFY_ prefix.

    Attributes:
        dialect: Default SQL dialect (oracle/postgres/mysql/sqlite).
        cache_dir: Directory for .sql file parse cache.
        chunk_cache_dir: Directory for vector chunk cache.
        log_level: Logging level (DEBUG/INFO/WARNING/ERROR).
        api_key: Anthropic API key for LLM features.
        max_chunks: Maximum number of chunks for RAG retrieval.
    """

    dialect: str = "oracle"
    cache_dir: str = ".sqlfy-cache"
    chunk_cache_dir: str = ".sqlfy-chunk-cache"
    log_level: str = "WARNING"
    api_key: str = ""
    max_chunks: int = 6

    @classmethod
    def from_env(cls) -> "SqlfySettings":
        """Create settings from environment variables with SQLFY_ prefix."""
        return cls(
            dialect=os.environ.get("SQLFY_DIALECT", "oracle"),
            cache_dir=os.environ.get("SQLFY_CACHE_DIR", ".sqlfy-cache"),
            chunk_cache_dir=os.environ.get("SQLFY_CHUNK_CACHE_DIR", ".sqlfy-chunk-cache"),
            log_level=os.environ.get("SQLFY_LOG_LEVEL", "WARNING"),
            api_key=os.environ.get("SQLFY_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "")),
            max_chunks=int(os.environ.get("SQLFY_MAX_CHUNKS", "6")),
        )


# Module-level singleton — lazily initialized
settings: SqlfySettings = SqlfySettings.from_env()

__all__ = ["SqlfySettings", "settings"]
