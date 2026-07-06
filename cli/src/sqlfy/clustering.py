"""
sqlfy.clustering
================
Backward-compatibility shim. Implementation moved to sqlfy.graph.clustering.

New code should import from sqlfy.graph.clustering directly.
"""
from __future__ import annotations

from .graph.clustering import (
    _DEFAULT_MIN_COHESION,
    _DEFAULT_RESOLUTION,
    _MAX_COMMUNITY_FRACTION,
    _MIN_SPLIT_SIZE,
    CommunityResult,
    _cohesion_score,
    _filter_low_cohesion,
    _run_community_detection,
    _split_oversized_communities,
    detect_communities,
    label_communities,
)

__all__ = [
    "detect_communities",
    "label_communities",
    "CommunityResult",
    "_cohesion_score",
    "_run_community_detection",
    "_split_oversized_communities",
    "_filter_low_cohesion",
    "_MAX_COMMUNITY_FRACTION",
    "_MIN_SPLIT_SIZE",
    "_DEFAULT_RESOLUTION",
    "_DEFAULT_MIN_COHESION",
]
