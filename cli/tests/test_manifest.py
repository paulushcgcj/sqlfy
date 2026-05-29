"""Tests for manifest/metadata generation."""

import json
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

    manifest = json.loads(state.to_manifest())

    assert manifest["schemaVersion"] == "3"
    assert manifest["fingerprint"] == "abc123"
    assert manifest["dialect"] == "oracle"
    assert manifest["generatedAt"] == "2026-05-26T10:00:00Z"
    assert "sqlfyVersion" in manifest
    assert manifest["nodeCount"] == 7  # tables + sequences
    assert manifest["edgeCount"] == 8  # relationships
    assert manifest["tableCount"] == 5
    assert manifest["columnCount"] == 25
    assert manifest["sequenceCount"] == 2
    assert manifest["relationshipCount"] == 8
    assert manifest["indexCount"] == 12
    assert manifest["tablesWithoutPk"] == 0
    assert manifest["migrationCount"] == 3


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

    manifest = json.loads(state.to_manifest())

    assert len(manifest["migrationHistory"]) == 2
    assert manifest["migrationHistory"][0] == {"version": "1", "description": "create users"}
    assert manifest["migrationHistory"][1] == {"version": "2", "description": "add email"}


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

    manifest = json.loads(state.to_manifest())

    assert manifest["schemaVersion"] == "0"
    assert manifest["nodeCount"] == 0
    assert manifest["edgeCount"] == 0
    assert manifest["tableCount"] == 0
    assert manifest["columnCount"] == 0
    assert manifest["migrationCount"] == 0
    assert manifest["migrationHistory"] == []


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

    manifest = json.loads(state.to_manifest())

    # Required fields (camelCase)
    required_fields = [
        "schemaVersion",
        "fingerprint",
        "dialect",
        "generatedAt",
        "sqlfyVersion",
        "nodeCount",
        "edgeCount",
        "tableCount",
        "columnCount",
        "sequenceCount",
        "relationshipCount",
        "indexCount",
        "tablesWithoutPk",
        "migrationCount",
        "migrationHistory",
    ]

    for field in required_fields:
        assert field in manifest, f"Missing required field: {field}"
