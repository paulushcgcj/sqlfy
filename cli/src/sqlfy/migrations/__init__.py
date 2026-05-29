"""
sqlfy.migrations
================
Migration domain — Flyway file discovery, version parsing, caching.

Packages:
  - loader     File discovery and loading (from filesystem)
  - parser     Flyway filename/version parsing
  - cache      Parsed schema caching
"""

from .parser import parse_flyway_ver
from .loader import load_files

__all__ = [
    "parse_flyway_ver",
    "load_files",
]
