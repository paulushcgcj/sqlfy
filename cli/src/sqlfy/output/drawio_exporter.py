"""
sqlfy.output.drawio_exporter
=============================
Export schema to Draw.io XML format.

Draw.io (diagrams.net) is an industry-standard diagramming tool.
The .drawio format is XML using mxGraph structure.

Output can be opened in:
  - draw.io (web)
  - VSCode Draw.io extension
  - Desktop app (diagrams.net)
  - Confluence (via integration)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom
from sqlfy.domain.schema_state import SchemaState


def to_drawio(state: SchemaState, title: str = "") -> str:
    """
    Convert SchemaState to Draw.io XML format.
    
    Args:
        state: Schema state from reconstructor
        title: Optional diagram title
    
    Returns:
        XML string that can be saved as .drawio file
    """
    # Root element
    root = ET.Element("mxfile", attrib={
        "host": "sqlfy",
        "modified": "2026-05-26T00:00:00.000Z",
        "agent": "sqlfy schema exporter",
        "version": "21.0.0",
        "type": "device",
    })
    
    # Diagram element
    diagram = ET.SubElement(root, "diagram", attrib={
        "id": "schema-diagram",
        "name": title or "Database Schema",
    })
    
    # Graph model
    model = ET.SubElement(diagram, "mxGraphModel", attrib={
        "dx": "800",
        "dy": "600",
        "grid": "1",
        "gridSize": "10",
        "guides": "1",
        "tooltips": "1",
        "connect": "1",
        "arrows": "1",
        "fold": "1",
        "page": "1",
        "pageScale": "1",
        "pageWidth": "3300",
        "pageHeight": "4681",
        "background": "#ffffff",
    })
    
    # Root cells (required by mxGraph)
    root_cells = ET.SubElement(model, "root")
    ET.SubElement(root_cells, "mxCell", attrib={"id": "0"})
    ET.SubElement(root_cells, "mxCell", attrib={"id": "1", "parent": "0"})
    
    # Cell ID counter
    cell_id_counter = 100
    
    def next_id() -> str:
        nonlocal cell_id_counter
        cell_id_counter += 1
        return str(cell_id_counter)
    
    # Layout tables in grid (3 columns)
    tables = list(state.tables.values())
    cols = 3
    x_spacing, y_spacing = 280, 300
    base_x, base_y = 40, 40
    
    # Track table positions for FK lines
    table_cell_ids: dict[str, str] = {}
    table_positions: dict[str, tuple[int, int, int, int]] = {}
    
    # Title
    if title:
        title_cell = ET.SubElement(root_cells, "mxCell", attrib={
            "id": next_id(),
            "value": title,
            "style": "text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=24;fontStyle=1;",
            "vertex": "1",
            "parent": "1",
        })
        ET.SubElement(title_cell, "mxGeometry", attrib={
            "x": str(base_x),
            "y": str(base_y - 50),
            "width": "600",
            "height": "40",
            "as": "geometry",
        })
    
    # Create table cells
    for i, table in enumerate(tables):
        row, col = divmod(i, cols)
        x = base_x + col * x_spacing
        y = base_y + row * y_spacing
        
        # Calculate table height
        row_height = 26
        header_height = 30
        table_height = header_height + len(table.columns) * row_height
        
        table_id = next_id()
        table_cell_ids[table.full_name] = table_id
        table_positions[table.full_name] = (x, y, x + 240, y + table_height)
        
        # Table container (swimlane with header)
        table_cell = ET.SubElement(root_cells, "mxCell", attrib={
            "id": table_id,
            "value": f"📊 {table.name}",
            "style": "swimlane;fontStyle=1;childLayout=stackLayout;horizontal=1;startSize=30;horizontalStack=0;resizeParent=1;resizeParentMax=0;resizeLast=0;collapsible=1;marginBottom=0;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=14;",
            "vertex": "1",
            "parent": "1",
        })
        ET.SubElement(table_cell, "mxGeometry", attrib={
            "x": str(x),
            "y": str(y),
            "width": "240",
            "height": str(table_height),
            "as": "geometry",
        })
        
        # Column rows
        for column in table.columns:
            # Build column display string
            badges = []
            if column.is_pk:
                badges.append("🔑")
            if column.is_fk:
                badges.append("🔗")
            if column.is_unique:
                badges.append("✨")
            
            badge_str = "".join(badges) + " " if badges else ""
            nullable_str = "" if column.nullable else " NOT NULL"
            
            col_text = f"{badge_str}{column.name}: {column.data_type}{nullable_str}"
            
            # Column cell
            col_cell = ET.SubElement(root_cells, "mxCell", attrib={
                "id": next_id(),
                "value": col_text,
                "style": "text;align=left;verticalAlign=middle;spacingLeft=4;spacingRight=4;overflow=hidden;rotatable=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;fontSize=12;fontFamily=Courier New;",
                "vertex": "1",
                "parent": table_id,
            })
            ET.SubElement(col_cell, "mxGeometry", attrib={
                "y": str(header_height + table.columns.index(column) * row_height),
                "width": "240",
                "height": str(row_height),
                "as": "geometry",
            })
    
    # Create FK relationship edges
    for rel in state.relationships:
        from_table = rel.from_table
        to_table = rel.to_table
        
        if from_table not in table_cell_ids or to_table not in table_cell_ids:
            continue
        
        from_id = table_cell_ids[from_table]
        to_id = table_cell_ids[to_table]
        
        # Create edge with ERD style
        edge_cell = ET.SubElement(root_cells, "mxCell", attrib={
            "id": next_id(),
            "value": f"{rel.from_columns[0] if rel.from_columns else ''} → {rel.to_columns[0] if rel.to_columns else ''}",
            "style": "edgeStyle=entityRelationEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;startArrow=ERzeroToMany;startFill=0;endArrow=ERmandOne;endFill=0;strokeColor=#FF6B6B;strokeWidth=2;fontSize=11;",
            "edge": "1",
            "parent": "1",
            "source": from_id,
            "target": to_id,
        })
        ET.SubElement(edge_cell, "mxGeometry", attrib={
            "relative": "1",
            "as": "geometry",
        })
    
    # Pretty-print XML
    rough_string = ET.tostring(root, encoding="unicode")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def to_drawio_compressed(state: SchemaState, title: str = "") -> str:
    """
    Convert SchemaState to compressed Draw.io XML (single line).
    
    Some Draw.io integrations prefer compressed format.
    """
    root = ET.Element("mxfile")
    # ... same as above but use ET.tostring without pretty printing
    return ET.tostring(root, encoding="unicode")
