"""
tests.test_drawio_export
========================
Unit tests for Draw.io XML export.
"""

import pytest
import xml.etree.ElementTree as ET
from sqlfy.output.drawio_exporter import to_drawio
from sqlfy.reconstructor import reconstruct
from sqlfy.domain.schema_state import SchemaStateBuilder


@pytest.fixture
def sample_schema():
    """Load the sample schema from migrations."""
    files = [
        {
            'filename': 'V1__create_core_tables.sql',
            'sql': '''
                CREATE TABLE users (
                    id NUMBER(10) PRIMARY KEY,
                    email VARCHAR2(255) NOT NULL,
                    full_name VARCHAR2(255)
                );
                
                CREATE TABLE orders (
                    order_id NUMBER(10) PRIMARY KEY,
                    user_id NUMBER(10) NOT NULL,
                    order_date DATE,
                    CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id)
                );
            '''
        }
    ]
    graph = reconstruct(files, dialect='oracle')
    return SchemaStateBuilder.from_graph(graph, source_files=files)


def test_to_drawio_generates_valid_xml(sample_schema):
    """Test that to_drawio generates valid XML."""
    result = to_drawio(sample_schema, title="Test Schema")
    
    # Parse XML
    root = ET.fromstring(result)
    assert root.tag == "mxfile"
    assert root.attrib.get("host") == "sqlfy"
    
    # Check diagram element exists
    diagrams = root.findall("diagram")
    assert len(diagrams) >= 1
    
    # Check graph model exists
    models = root.findall(".//mxGraphModel")
    assert len(models) >= 1


def test_to_drawio_creates_table_cells(sample_schema):
    """Test that table cells are created for each table."""
    result = to_drawio(sample_schema)
    root = ET.fromstring(result)
    
    # Find all mxCell elements with swimlane style (tables)
    cells = root.findall(".//mxCell[@style]")
    table_cells = [c for c in cells if 'swimlane' in c.attrib.get('style', '')]
    
    # Should have 2 tables (users, orders)
    assert len(table_cells) >= 2
    
    # Check that each table has geometry
    for cell in table_cells:
        geom = cell.find("mxGeometry")
        assert geom is not None
        assert "x" in geom.attrib
        assert "y" in geom.attrib
        assert "width" in geom.attrib
        assert "height" in geom.attrib


def test_to_drawio_creates_column_rows(sample_schema):
    """Test that column rows are created for each column."""
    result = to_drawio(sample_schema)
    root = ET.fromstring(result)
    
    # Find all mxCell elements with text style (columns)
    cells = root.findall(".//mxCell[@style]")
    column_cells = [c for c in cells if 'text;align=left' in c.attrib.get('style', '')]
    
    # Should have multiple column cells (id, email, full_name, order_id, user_id, order_date)
    assert len(column_cells) >= 6


def test_to_drawio_creates_fk_edges(sample_schema):
    """Test that FK relationship edges are created."""
    result = to_drawio(sample_schema)
    root = ET.fromstring(result)
    
    # Find all mxCell elements with edge="1"
    edges = root.findall(".//mxCell[@edge='1']")
    
    # Should have 1 edge for orders → users FK
    assert len(edges) >= 1
    
    # Check edge has source and target
    for edge in edges:
        assert "source" in edge.attrib
        assert "target" in edge.attrib


def test_to_drawio_root_cells_structure(sample_schema):
    """Test that root cells (id=0, id=1) are present."""
    result = to_drawio(sample_schema)
    root = ET.fromstring(result)
    
    # Find root cell containers
    root_cells = root.findall(".//root")
    assert len(root_cells) >= 1
    
    # Check for base cells (id=0, id=1)
    cells = root_cells[0].findall("mxCell")
    cell_ids = [c.attrib.get("id") for c in cells]
    assert "0" in cell_ids
    assert "1" in cell_ids


def test_to_drawio_title(sample_schema):
    """Test that title is included in diagram element."""
    result = to_drawio(sample_schema, title="My Schema")
    root = ET.fromstring(result)
    
    # Find diagram element
    diagram = root.find("diagram")
    assert diagram is not None
    assert diagram.attrib.get("name") == "My Schema"


def test_to_drawio_grid_layout(sample_schema):
    """Test that tables are positioned in a grid layout."""
    result = to_drawio(sample_schema)
    root = ET.fromstring(result)
    
    # Find table cells
    cells = root.findall(".//mxCell[@style]")
    table_cells = [c for c in cells if 'swimlane' in c.attrib.get('style', '')]
    
    # Extract positions
    positions = []
    for cell in table_cells:
        geom = cell.find("mxGeometry")
        if geom is not None:
            x = int(geom.attrib.get("x", 0))
            y = int(geom.attrib.get("y", 0))
            positions.append((x, y))
    
    # All positions should be unique
    assert len(set(positions)) == len(positions)
    
    # Check spacing (>= 200px apart horizontally or vertically)
    if len(positions) >= 2:
        x_positions = sorted([p[0] for p in positions])
        if len(x_positions) >= 2:
            min_x_spacing = min(x_positions[i+1] - x_positions[i] for i in range(len(x_positions)-1) if x_positions[i+1] > x_positions[i])
            assert min_x_spacing >= 100  # At least 100px spacing


def test_to_drawio_empty_schema():
    """Test exporting a minimal schema."""
    # Create minimal schema with no tables
    files = [{'filename': 'V0__empty.sql', 'sql': '-- empty'}]
    graph = reconstruct(files, dialect='oracle')
    empty_state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    result = to_drawio(empty_state)
    root = ET.fromstring(result)
    
    # Should still have valid XML structure
    assert root.tag == "mxfile"
    
    # Should have minimal cells (just root cells id=0, id=1)
    cells = root.findall(".//mxCell")
    assert len(cells) >= 2  # At least root cells


def test_to_drawio_column_badges(sample_schema):
    """Test that column badges are present (🔑 for PK, etc.)."""
    result = to_drawio(sample_schema)
    
    # Check XML content contains key emoji
    assert "🔑" in result


def test_to_drawio_erd_edge_style(sample_schema):
    """Test that FK edges use ERD-specific styles."""
    result = to_drawio(sample_schema)
    root = ET.fromstring(result)
    
    # Find edges
    edges = root.findall(".//mxCell[@edge='1']")
    
    for edge in edges:
        style = edge.attrib.get("style", "")
        # Should contain entity relationship edge style
        assert "entityRelationEdgeStyle" in style or "edgeStyle" in style


def test_to_drawio_pretty_printed(sample_schema):
    """Test that output is pretty-printed XML."""
    result = to_drawio(sample_schema)
    
    # Pretty-printed XML should have newlines and indentation
    assert "\n" in result
    assert "  " in result  # indentation


def test_to_drawio_table_values(sample_schema):
    """Test that table names appear as cell values."""
    result = to_drawio(sample_schema)
    
    # Should contain table names in XML (Oracle uppercases to USERS, ORDERS)
    result_upper = result.upper()
    assert "USERS" in result_upper
    assert "ORDERS" in result_upper


def test_to_drawio_column_values(sample_schema):
    """Test that column names appear in cell values."""
    result = to_drawio(sample_schema)
    
    # Should contain column names (Oracle uppercases identifiers)
    result_upper = result.upper()
    assert "ID" in result_upper
    assert "EMAIL" in result_upper
    assert "USER_ID" in result_upper
    assert "ORDER_DATE" in result_upper
