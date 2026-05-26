"""
sqlfy.output.excalidraw_exporter
=================================
Export schema to Excalidraw JSON format.

Excalidraw is a collaborative whiteboarding tool with a hand-drawn aesthetic.
The .excalidraw format is JSON containing element definitions (rectangles,
text, arrows).

Output can be opened in:
  - excalidraw.com (web)
  - VSCode Excalidraw extension
  - Obsidian Excalidraw plugin
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional
from sqlfy.domain.schema_state import SchemaState


@dataclass
class ExcalidrawElement:
    """Single element in Excalidraw diagram."""
    type: str                    # "rectangle", "text", "arrow", "line"
    id: str
    x: float
    y: float
    width: float = 200
    height: float = 30
    angle: float = 0
    strokeColor: str = "#000000"
    backgroundColor: str = "transparent"
    fillStyle: str = "hachure"
    strokeWidth: int = 1
    strokeStyle: str = "solid"
    roughness: int = 1           # 0=precise, 1=hand-drawn, 2=very rough
    opacity: int = 100
    groupIds: list[str] = field(default_factory=list)
    roundness: Optional[dict] = None
    seed: int = 1234567
    version: int = 1
    versionNonce: int = 1
    isDeleted: bool = False
    boundElements: Optional[list[dict]] = None
    updated: int = 1
    link: Optional[str] = None
    locked: bool = False
    
    # Text-specific
    text: str = ""
    fontSize: int = 16
    fontFamily: int = 1          # 1=Virgil, 2=Helvetica, 3=Cascadia
    textAlign: str = "left"
    verticalAlign: str = "top"
    baseline: int = 14
    
    # Arrow-specific
    startBinding: Optional[dict] = None
    endBinding: Optional[dict] = None
    startArrowhead: Optional[str] = None
    endArrowhead: str = "arrow"
    points: list[list[float]] = field(default_factory=list)


def to_excalidraw(state: SchemaState, title: str = "") -> dict:
    """
    Convert SchemaState to Excalidraw JSON format.
    
    Args:
        state: Schema state from reconstructor
        title: Optional diagram title
    
    Returns:
        Dict representing .excalidraw file structure
    """
    elements: list[dict] = []
    element_id_counter = 1000
    
    def next_id() -> str:
        nonlocal element_id_counter
        element_id_counter += 1
        return f"elem-{element_id_counter}"
    
    # Layout tables in grid (3 columns)
    tables = list(state.tables.values())
    cols = 3
    x_spacing, y_spacing = 350, 300
    base_x, base_y = 100, 100
    
    # Track table positions for FK arrows
    table_positions: dict[str, tuple[float, float, float, float]] = {}
    
    # Title
    if title:
        elements.append(asdict(ExcalidrawElement(
            type="text",
            id=next_id(),
            x=base_x,
            y=base_y - 50,
            width=600,
            height=40,
            text=title,
            fontSize=28,
            fontFamily=2,  # Helvetica
        )))
    
    # Create table elements
    for i, table in enumerate(tables):
        row, col = divmod(i, cols)
        x = base_x + col * x_spacing
        y = base_y + row * y_spacing
        
        # Calculate table height based on number of columns
        table_height = 50 + len(table.columns) * 25
        table_id = next_id()
        
        # Store position for FK arrows
        table_positions[table.full_name] = (x, y, x + 280, y + table_height)
        
        # Table rectangle (outer box)
        elements.append(asdict(ExcalidrawElement(
            type="rectangle",
            id=table_id,
            x=x,
            y=y,
            width=280,
            height=table_height,
            strokeColor="#1864ab",
            strokeWidth=2,
            backgroundColor="#e7f5ff",
            fillStyle="solid",
            roughness=1,
        )))
        
        # Table name (bold, larger)
        elements.append(asdict(ExcalidrawElement(
            type="text",
            id=next_id(),
            x=x + 10,
            y=y + 10,
            width=260,
            height=30,
            text=f"📊 {table.name}",
            fontSize=20,
            fontFamily=2,
            strokeColor="#1864ab",
        )))
        
        # Columns (one per line)
        for j, column in enumerate(table.columns):
            # Build column display string
            badges = []
            if column.is_pk:
                badges.append("🔑")
            if column.is_fk:
                badges.append("🔗")
            if column.is_unique:
                badges.append("✨")
            
            badge_str = " ".join(badges) + " " if badges else ""
            nullable_str = "" if column.nullable else " NOT NULL"
            
            col_text = f"{badge_str}{column.name}: {column.data_type}{nullable_str}"
            
            elements.append(asdict(ExcalidrawElement(
                type="text",
                id=next_id(),
                x=x + 15,
                y=y + 50 + j * 25,
                width=250,
                height=20,
                text=col_text,
                fontSize=14,
                fontFamily=3,  # Cascadia (monospace)
                textAlign="left",
            )))
    
    # Create FK relationship arrows
    for rel in state.relationships:
        from_table = rel.from_table
        to_table = rel.to_table
        
        if from_table not in table_positions or to_table not in table_positions:
            continue
        
        # Get table positions
        from_x1, from_y1, from_x2, from_y2 = table_positions[from_table]
        to_x1, to_y1, to_x2, to_y2 = table_positions[to_table]
        
        # Calculate midpoints
        from_mid_x, from_mid_y = (from_x1 + from_x2) / 2, (from_y1 + from_y2) / 2
        to_mid_x, to_mid_y = (to_x1 + to_x2) / 2, (to_y1 + to_y2) / 2
        
        # Create arrow from source to target
        arrow_id = next_id()
        elements.append(asdict(ExcalidrawElement(
            type="arrow",
            id=arrow_id,
            x=from_mid_x,
            y=from_mid_y,
            width=abs(to_mid_x - from_mid_x),
            height=abs(to_mid_y - from_mid_y),
            strokeColor="#fa5252",
            strokeWidth=2,
            roughness=1,
            startArrowhead=None,
            endArrowhead="arrow",
            points=[
                [0, 0],
                [to_mid_x - from_mid_x, to_mid_y - from_mid_y]
            ],
        )))
        
        # Arrow label (FK column names)
        label_x = (from_mid_x + to_mid_x) / 2
        label_y = (from_mid_y + to_mid_y) / 2 - 10
        label_text = f"{rel.from_columns[0] if rel.from_columns else '?'} → {rel.to_columns[0] if rel.to_columns else '?'}"
        
        elements.append(asdict(ExcalidrawElement(
            type="text",
            id=next_id(),
            x=label_x,
            y=label_y,
            width=150,
            height=20,
            text=label_text,
            fontSize=12,
            fontFamily=1,
            strokeColor="#fa5252",
            backgroundColor="#fff5f5",
            fillStyle="solid",
        )))
    
    # Build final Excalidraw document
    return {
        "type": "excalidraw",
        "version": 2,
        "source": "sqlfy",
        "elements": elements,
        "appState": {
            "gridSize": None,
            "viewBackgroundColor": "#ffffff"
        },
        "files": {}
    }
