"""
sqlfy.layout
============
ERD layout engine using hierarchical positioning.

Computes x,y coordinates for tables based on FK relationships.
"""

from __future__ import annotations

from ..domain.models import Table, Edge


def compute_layout(
    tables: dict[str, Table],
    edges: list[Edge],
    width: float = 580,
    height: float = 220,
) -> dict[str, dict]:
    """Compute hierarchical layout for ERD visualization.
    
    Uses FK relationships to determine levels: tables with no outgoing FKs
    are roots, tables that reference others are placed at higher levels.
    
    Args:
        tables: Dictionary of table ID → Table
        edges: List of FK relationships
        width: Canvas width
        height: Canvas height
    
    Returns:
        Dictionary mapping table ID → {x, y} coordinates
    """
    # Initialize all tables at level 0
    levels: dict[str, int] = {k: 0 for k in tables}
    
    # Iteratively adjust levels based on FK relationships
    # If A → B (A references B), then A should be at a higher level than B
    for _ in range(10):  # Max 10 iterations to prevent infinite loops
        changed = False
        for e in edges:
            fl = levels.get(e.from_table, 0)
            tl = levels.get(e.to_table, 0)
            if fl <= tl:
                levels[e.from_table] = tl + 1
                changed = True
        if not changed:
            break
    
    # Group tables by level
    by_level: dict[int, list[str]] = {}
    for t, l in levels.items():
        by_level.setdefault(l, []).append(t)
    
    # Compute positions
    max_l = max(levels.values(), default=0)
    pos: dict[str, dict] = {}
    
    for level, tbls in by_level.items():
        # Y coordinate based on level (top to bottom)
        if max_l == 0:
            y = height / 2
        else:
            y = (level / max_l) * (height - 80) + 40
        
        # X coordinate evenly spaced within level
        for i, t in enumerate(tbls):
            x = ((i + 1) / (len(tbls) + 1)) * width
            pos[t] = {'x': x, 'y': y}
    
    return pos
