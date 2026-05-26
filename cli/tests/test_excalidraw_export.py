"""
tests.test_excalidraw_export
=============================
Unit tests for Excalidraw JSON export.
"""

import json
import pytest
from sqlfy.output.excalidraw_exporter import to_excalidraw, ExcalidrawElement
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


def test_excalidraw_element_creation():
    """Test creating an ExcalidrawElement."""
    elem = ExcalidrawElement(
        type="rectangle",
        id="test-1",
        x=100.0,
        y=200.0,
        width=250,
        height=150,
    )
    assert elem.type == "rectangle"
    assert elem.id == "test-1"
    assert elem.x == 100.0
    assert elem.y == 200.0
    assert elem.width == 250
    assert elem.height == 150


def test_to_excalidraw_generates_valid_json(sample_schema):
    """Test that to_excalidraw generates valid JSON structure."""
    result = to_excalidraw(sample_schema, title="Test Schema")
    
    assert isinstance(result, dict)
    assert result["type"] == "excalidraw"
    assert result["version"] == 2
    assert result["source"] == "sqlfy"
    assert "elements" in result
    assert "appState" in result
    assert isinstance(result["elements"], list)
    
    # Should be JSON-serializable
    json_str = json.dumps(result)
    assert len(json_str) > 0


def test_to_excalidraw_creates_table_rectangles(sample_schema):
    """Test that table rectangles are created for each table."""
    result = to_excalidraw(sample_schema)
    
    # Filter rectangle elements (not text or arrows)
    rectangles = [e for e in result["elements"] if e["type"] == "rectangle"]
    
    # Should have 2 table rectangles (users, orders)
    assert len(rectangles) >= 2
    
    # Check that rectangle has required fields
    for rect in rectangles:
        assert "id" in rect
        assert "x" in rect
        assert "y" in rect
        assert "width" in rect
        assert "height" in rect
        assert rect["width"] > 0
        assert rect["height"] > 0


def test_to_excalidraw_creates_text_elements(sample_schema):
    """Test that text elements are created for table names and columns."""
    result = to_excalidraw(sample_schema)
    
    # Filter text elements
    texts = [e for e in result["elements"] if e["type"] == "text"]
    
    # Should have text elements for:
    # - table names (users, orders)
    # - columns (id, email, full_name, order_id, user_id, order_date)
    assert len(texts) >= 8
    
    # Check that text has required fields
    for text in texts:
        assert "id" in text
        assert "text" in text
        assert "fontSize" in text
        assert len(text["text"]) > 0


def test_to_excalidraw_creates_fk_arrows(sample_schema):
    """Test that FK relationship arrows are created."""
    result = to_excalidraw(sample_schema)
    
    # Filter arrow elements
    arrows = [e for e in result["elements"] if e["type"] == "arrow"]
    
    # Should have 1 arrow for orders → users FK
    assert len(arrows) >= 1
    
    # Check arrow structure
    for arrow in arrows:
        assert "id" in arrow
        assert "points" in arrow
        assert isinstance(arrow["points"], list)
        assert len(arrow["points"]) >= 2


def test_to_excalidraw_title(sample_schema):
    """Test that title is included when provided."""
    result = to_excalidraw(sample_schema, title="My Schema")
    
    # Find title text element (should be first or near first)
    texts = [e for e in result["elements"] if e["type"] == "text"]
    title_texts = [t for t in texts if "My Schema" in t.get("text", "")]
    
    assert len(title_texts) > 0
    title_elem = title_texts[0]
    assert title_elem["fontSize"] >= 20  # Titles should be larger


def test_to_excalidraw_grid_layout(sample_schema):
    """Test that tables are laid out in a grid pattern."""
    result = to_excalidraw(sample_schema)
    
    rectangles = [e for e in result["elements"] if e["type"] == "rectangle"]
    
    # Check that tables have different positions
    positions = [(r["x"], r["y"]) for r in rectangles]
    assert len(set(positions)) == len(positions)  # All unique positions
    
    # Check that spacing is reasonable (> 250 pixels apart)
    if len(rectangles) >= 2:
        x_positions = sorted([r["x"] for r in rectangles])
        if len(x_positions) >= 2:
            min_x_spacing = min(x_positions[i+1] - x_positions[i] for i in range(len(x_positions)-1))
            assert min_x_spacing >= 200  # At least 200px spacing


def test_to_excalidraw_empty_schema():
    """Test exporting a minimal schema."""
    # Create minimal schema with no tables
    files = [{'filename': 'V0__empty.sql', 'sql': '-- empty'}]
    graph = reconstruct(files, dialect='oracle')
    empty_state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    result = to_excalidraw(empty_state)
    
    assert result["type"] == "excalidraw"
    # May have 0 or few elements (just title if provided)
    assert isinstance(result["elements"], list)


def test_to_excalidraw_column_badges(sample_schema):
    """Test that column badges are present (🔑 for PK, etc.)."""
    result = to_excalidraw(sample_schema)
    
    texts = [e for e in result["elements"] if e["type"] == "text"]
    text_contents = [t.get("text", "") for t in texts]
    all_text = " ".join(text_contents)
    
    # Should contain key emoji for PKs
    assert "🔑" in all_text


def test_to_excalidraw_without_title(sample_schema):
    """Test exporting without a title."""
    result = to_excalidraw(sample_schema)
    
    assert result["type"] == "excalidraw"
    assert len(result["elements"]) > 0
    
    # Title should not appear (no text with empty string check)
    texts = [e for e in result["elements"] if e["type"] == "text"]
    # Just verify we have text elements (table names and columns)
    assert len(texts) > 0
