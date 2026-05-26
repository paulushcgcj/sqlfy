"""Tests for manifest/metadata generation."""

from sqlfy.domain.schema_state import MigrationStep, SchemaState


def test_to_manifest_basic():
    """Test basic manifest generation."""
    state = SchemaState(
        version="3",
        generated_at="2026-05-26T10:00:00Z",
        fingerprint="abc123",
        dialect="oracle",
        tables={},
        sequences={},
        relationships=[],
        migration_history=[
            MigrationStep(version="1", description="create core tables"),
            MigrationStep(version="2", description="add orders"),
            MigrationStep(version="3", description="add audit"),
        ],
        stats={
            "table_count": 5,
            "column_count": 25,
            "sequence_count": 2,
            "relationship_count": 8,
            "index_count": 12,
            "tables_without_pk": 0,
            "migration_count": 3,
        },
    )
    
    manifest = state.to_manifest()
    
    assert manifest["schema_version"] == "3"
    assert manifest["fingerprint"] == "abc123"
    assert manifest["dialect"] == "oracle"
    assert manifest["generated_at"] == "2026-05-26T10:00:00Z"
    assert "sqlfy_version" in manifest
    assert manifest["node_count"] == 7  # tables + sequences
    assert manifest["edge_count"] == 8  # relationships
    assert manifest["table_count"] == 5
    assert manifest["column_count"] == 25
    assert manifest["sequence_count"] == 2
    assert manifest["relationship_count"] == 8
    assert manifest["index_count"] == 12
    assert manifest["tables_without_pk"] == 0
    assert manifest["migration_count"] == 3


def test_to_manifest_includes_migration_history():
    """Test that manifest includes migration history."""
    state = SchemaState(
        version="2",
        generated_at="2026-05-26T10:00:00Z",
        fingerprint="xyz789",
        dialect="postgres",
        tables={},
        sequences={},
        relationships=[],
        migration_history=[
            MigrationStep(version="1", description="create users"),
            MigrationStep(version="2", description="add email"),
        ],
        stats={
            "table_count": 1,
            "column_count": 3,
            "sequence_count": 0,
            "relationship_count": 0,
            "index_count": 0,
            "tables_without_pk": 0,
            "migration_count": 2,
        },
    )
    
    manifest = state.to_manifest()
    
    assert len(manifest["migration_history"]) == 2
    assert manifest["migration_history"][0] == {"version": "1", "description": "create users"}
    assert manifest["migration_history"][1] == {"version": "2", "description": "add email"}


def test_to_manifest_empty_state():
    """Test manifest generation for empty schema state."""
    state = SchemaState(
        version="0",
        generated_at="2026-05-26T10:00:00Z",
        fingerprint="",
        dialect="oracle",
        tables={},
        sequences={},
        relationships=[],
        migration_history=[],
        stats={},
    )
    
    manifest = state.to_manifest()
    
    assert manifest["schema_version"] == "0"
    assert manifest["node_count"] == 0
    assert manifest["edge_count"] == 0
    assert manifest["table_count"] == 0
    assert manifest["column_count"] == 0
    assert manifest["migration_count"] == 0
    assert manifest["migration_history"] == []


def test_to_manifest_structure():
    """Test that manifest has expected structure."""
    state = SchemaState(
        version="1",
        generated_at="2026-05-26T10:00:00Z",
        fingerprint="test",
        dialect="oracle",
        tables={},
        sequences={},
        relationships=[],
        migration_history=[],
        stats={
            "table_count": 1,
            "column_count": 5,
            "sequence_count": 0,
            "relationship_count": 0,
            "index_count": 0,
            "tables_without_pk": 0,
            "migration_count": 1,
        },
    )
    
    manifest = state.to_manifest()
    
    # Required fields
    required_fields = [
        "schema_version",
        "fingerprint",
        "dialect",
        "generated_at",
        "sqlfy_version",
        "node_count",
        "edge_count",
        "table_count",
        "column_count",
        "sequence_count",
        "relationship_count",
        "index_count",
        "tables_without_pk",
        "migration_count",
        "migration_history",
    ]
    
    for field in required_fields:
        assert field in manifest, f"Missing required field: {field}"
