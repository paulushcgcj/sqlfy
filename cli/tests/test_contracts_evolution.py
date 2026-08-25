"""Contract tests for evolution command JSON outputs.

Validates that JSON outputs match the registered Pydantic contracts.
"""

from __future__ import annotations

import pytest

from sqlfy.contracts import CONTRACTS, get_contract
from sqlfy.contracts.evolution.v1 import DiffV1, RollbackV1, SimulateV1


class TestContractRegistry:
    """Verify contracts are properly registered."""

    def test_diff_contract_registered(self):
        entry = get_contract("diff@v1")
        assert entry.name == "diff"
        assert entry.version == "v1"
        assert entry.command == "diff-versions"
        assert entry.model_class.__name__ == "DiffV1"

    def test_simulate_contract_registered(self):
        entry = get_contract("simulate@v1")
        assert entry.name == "simulate"
        assert entry.version == "v1"
        assert entry.command == "simulate"
        assert entry.model_class.__name__ == "SimulateV1"

    def test_rollback_contract_registered(self):
        entry = get_contract("rollback@v1")
        assert entry.name == "rollback"
        assert entry.version == "v1"
        assert entry.command == "rollback-analysis"
        assert entry.model_class.__name__ == "RollbackV1"


class TestDiffContract:
    """Tests for DiffV1 contract shape and validation."""

    def test_diff_minimal_valid(self):
        """Minimal valid diff output validates."""
        data = {
            "versionA": "1",
            "versionB": "2",
            "fingerprintA": "abc123",
            "fingerprintB": "def456",
            "stats": {
                "tablesAdded": 0,
                "tablesRemoved": 0,
                "tablesModified": 0,
                "columnsAdded": 0,
                "columnsRemoved": 0,
                "columnsModified": 0,
                "sequencesAdded": 0,
                "sequencesRemoved": 0,
                "relationshipsAdded": 0,
                "relationshipsRemoved": 0,
                "isBreaking": False,
            },
            "tableChanges": [],
            "sequenceChanges": [],
            "relationshipChanges": [],
        }
        model = DiffV1.model_validate(data)
        assert model.version_a == "1"
        assert model.version_b == "2"
        assert model.contract_version == "v1"

    def test_diff_with_changes(self):
        """Diff with table and column changes validates."""
        data = {
            "versionA": "1",
            "versionB": "2",
            "fingerprintA": "abc123",
            "fingerprintB": "def456",
            "stats": {
                "tablesAdded": 1,
                "tablesRemoved": 0,
                "tablesModified": 1,
                "columnsAdded": 2,
                "columnsRemoved": 1,
                "columnsModified": 0,
                "sequencesAdded": 0,
                "sequencesRemoved": 0,
                "relationshipsAdded": 1,
                "relationshipsRemoved": 0,
                "isBreaking": True,
            },
            "tableChanges": [
                {
                    "fullName": "APP.ORDERS",
                    "change": "added",
                    "breaking": False,
                    "columnChanges": [
                        {
                            "name": "ID",
                            "change": "added",
                            "before": None,
                            "after": {"dataType": "NUMBER", "nullable": False},
                            "diffs": [],
                            "breaking": False,
                        },
                        {
                            "name": "USER_ID",
                            "change": "added",
                            "before": None,
                            "after": {"dataType": "NUMBER", "nullable": False},
                            "diffs": [],
                            "breaking": False,
                        },
                    ],
                    "constraintChanges": [
                        {
                            "name": "FK_ORDERS_USER",
                            "change": "added",
                            "type": "foreign_key",
                            "columns": ["USER_ID"],
                        }
                    ],
                    "indexChanges": [],
                },
                {
                    "fullName": "APP.USERS",
                    "change": "modified",
                    "breaking": True,
                    "columnChanges": [
                        {
                            "name": "EMAIL",
                            "change": "modified",
                            "before": {"dataType": "VARCHAR2(100)", "nullable": True},
                            "after": {"dataType": "VARCHAR2(255)", "nullable": False},
                            "diffs": ["data type changed", "nullable changed"],
                            "breaking": True,
                        }
                    ],
                    "constraintChanges": None,
                    "indexChanges": None,
                },
            ],
            "sequenceChanges": [],
            "relationshipChanges": [
                {
                    "change": "added",
                    "from": "APP.ORDERS",
                    "fromCols": ["USER_ID"],
                    "to": "APP.USERS",
                    "toCols": ["ID"],
                    "onDelete": "CASCADE",
                }
            ],
        }
        model = DiffV1.model_validate(data)
        assert len(model.table_changes) == 2
        assert model.table_changes[0].full_name == "APP.ORDERS"
        assert model.table_changes[0].change == "added"
        assert model.table_changes[1].change == "modified"
        assert model.table_changes[1].breaking is True
        assert len(model.relationship_changes) == 1
        assert model.stats.tables_added == 1
        assert model.stats.is_breaking is True

    def test_diff_missing_required_field_fails(self):
        data = {
            "versionA": "1",
            "versionB": "2",
            # missing fingerprintA, fingerprintB, stats, tableChanges, etc.
        }
        with pytest.raises(Exception):
            DiffV1.model_validate(data)

    def test_diff_extra_field_fails(self):
        data = {
            "versionA": "1",
            "versionB": "2",
            "fingerprintA": "abc",
            "fingerprintB": "def",
            "stats": {
                "tablesAdded": 0,
                "tablesRemoved": 0,
                "tablesModified": 0,
                "columnsAdded": 0,
                "columnsRemoved": 0,
                "columnsModified": 0,
                "sequencesAdded": 0,
                "sequencesRemoved": 0,
                "relationshipsAdded": 0,
                "relationshipsRemoved": 0,
                "isBreaking": False,
            },
            "tableChanges": [],
            "sequenceChanges": [],
            "relationshipChanges": [],
            "extra_field": "not allowed",
        }
        with pytest.raises(Exception):
            DiffV1.model_validate(data)

    def test_diff_contract_version_serializes(self):
        data = {
            "versionA": "1",
            "versionB": "2",
            "fingerprintA": "abc",
            "fingerprintB": "def",
            "stats": {
                "tablesAdded": 0,
                "tablesRemoved": 0,
                "tablesModified": 0,
                "columnsAdded": 0,
                "columnsRemoved": 0,
                "columnsModified": 0,
                "sequencesAdded": 0,
                "sequencesRemoved": 0,
                "relationshipsAdded": 0,
                "relationshipsRemoved": 0,
                "isBreaking": False,
            },
            "tableChanges": [],
            "sequenceChanges": [],
            "relationshipChanges": [],
        }
        model = DiffV1.model_validate(data)
        json_output = model.model_dump_json(by_alias=True)
        assert '"contractVersion":"v1"' in json_output


class TestSimulateContract:
    """Tests for SimulateV1 contract shape and validation."""

    def test_simulate_minimal_valid(self):
        data = {
            "timestamp": "2024-01-01T00:00:00Z",
            "baseVersion": "1",
            "sql": "ALTER TABLE app.users ADD (status VARCHAR2(20));",
            "success": True,
            "isSafe": True,
            "isBreaking": False,
            "errors": [],
            "warnings": [],
            "diff": {
                "stats": {
                    "tablesAdded": 0,
                    "tablesRemoved": 0,
                    "tablesModified": 1,
                    "columnsAdded": 1,
                    "columnsRemoved": 0,
                    "columnsModified": 0,
                    "sequencesAdded": 0,
                    "sequencesRemoved": 0,
                    "relationshipsAdded": 0,
                    "relationshipsRemoved": 0,
                    "isBreaking": False,
                },
                "isBreaking": False,
            },
            "health": {
                "score": 95,
                "grade": "good",
                "errors": 0,
                "warnings": 0,
            },
        }
        model = SimulateV1.model_validate(data)
        assert model.base_version == "1"
        assert model.success is True
        assert model.is_safe is True
        assert model.contract_version == "v1"

    def test_simulate_unsafe(self):
        data = {
            "timestamp": "2024-01-01T00:00:00Z",
            "baseVersion": "1",
            "sql": "DROP TABLE app.users;",
            "success": True,
            "isSafe": False,
            "isBreaking": True,
            "errors": [],
            "warnings": ["Destructive operation: DROP TABLE"],
            "diff": {
                "stats": {
                    "tablesAdded": 0,
                    "tablesRemoved": 1,
                    "tablesModified": 0,
                    "columnsAdded": 0,
                    "columnsRemoved": 5,
                    "columnsModified": 0,
                    "sequencesAdded": 0,
                    "sequencesRemoved": 0,
                    "relationshipsAdded": 0,
                    "relationshipsRemoved": 2,
                    "isBreaking": True,
                },
                "isBreaking": True,
            },
            "health": {
                "score": 10,
                "grade": "critical",
                "errors": 1,
                "warnings": 1,
            },
        }
        model = SimulateV1.model_validate(data)
        assert model.is_safe is False
        assert model.is_breaking is True
        assert model.diff.stats.is_breaking is True

    def test_simulate_contract_version_serializes(self):
        data = {
            "timestamp": "2024-01-01T00:00:00Z",
            "baseVersion": "1",
            "sql": "SELECT 1;",
            "success": True,
            "isSafe": True,
            "isBreaking": False,
            "errors": [],
            "warnings": [],
            "diff": {
                "stats": {
                    "tablesAdded": 0,
                    "tablesRemoved": 0,
                    "tablesModified": 0,
                    "columnsAdded": 0,
                    "columnsRemoved": 0,
                    "columnsModified": 0,
                    "sequencesAdded": 0,
                    "sequencesRemoved": 0,
                    "relationshipsAdded": 0,
                    "relationshipsRemoved": 0,
                    "isBreaking": False,
                },
                "isBreaking": False,
            },
            "health": {"score": 100, "grade": "excellent", "errors": 0, "warnings": 0},
        }
        model = SimulateV1.model_validate(data)
        json_output = model.model_dump_json(by_alias=True)
        assert '"contractVersion":"v1"' in json_output


class TestRollbackContract:
    """Tests for RollbackV1 contract shape and validation."""

    def test_rollback_minimal_valid(self):
        data = {
            "summary": {
                "total": 5,
                "reversible": 3,
                "partial": 1,
                "irreversible": 1,
            },
            "migrations": [
                {
                    "migration": "V1__create.sql",
                    "feasibility": "reversible",
                    "score": 90,
                    "rollbackScript": "-- rollback sql",
                    "warnings": [],
                    "recommendations": ["Safe to rollback"],
                    "operations": ["CREATE TABLE"],
                },
                {
                    "migration": "V2__add_column.sql",
                    "feasibility": "partial",
                    "score": 50,
                    "rollbackScript": "-- partial rollback",
                    "warnings": ["Data loss possible"],
                    "recommendations": ["Backup first"],
                    "operations": ["ALTER TABLE ADD COLUMN"],
                },
                {
                    "migration": "V3__drop.sql",
                    "feasibility": "irreversible",
                    "score": 0,
                    "rollbackScript": None,
                    "warnings": ["DROP TABLE is irreversible"],
                    "recommendations": ["Cannot rollback"],
                    "operations": ["DROP TABLE"],
                },
            ],
        }
        model = RollbackV1.model_validate(data)
        assert model.summary.total == 5
        assert model.summary.reversible == 3
        assert len(model.migrations) == 3
        assert model.migrations[0].feasibility == "reversible"
        assert model.migrations[2].feasibility == "irreversible"
        assert model.migrations[2].rollback_script is None
        assert model.contract_version == "v1"

    def test_rollback_contract_version_serializes(self):
        data = {
            "summary": {"total": 0, "reversible": 0, "partial": 0, "irreversible": 0},
            "migrations": [],
        }
        model = RollbackV1.model_validate(data)
        json_output = model.model_dump_json(by_alias=True)
        assert '"contractVersion":"v1"' in json_output


class TestContractSchemaGeneration:
    """Verify JSON Schema generation for evolution contracts."""

    def test_diff_schema_generates(self):
        entry = get_contract("diff@v1")
        schema = entry.generate_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "contractVersion" in schema["properties"]

    def test_simulate_schema_generates(self):
        entry = get_contract("simulate@v1")
        schema = entry.generate_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "contractVersion" in schema["properties"]

    def test_rollback_schema_generates(self):
        entry = get_contract("rollback@v1")
        schema = entry.generate_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "contractVersion" in schema["properties"]
