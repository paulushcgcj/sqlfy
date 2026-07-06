"""Backward-compat shim. Use sqlfy.intelligence.asker directly."""
from __future__ import annotations

from ..intelligence.asker import Asker, AskResult, ChatSession

__all__ = ["Asker", "AskResult", "ChatSession"]
