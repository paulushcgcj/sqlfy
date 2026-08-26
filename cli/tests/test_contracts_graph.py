"""Contract tests for graph command JSON outputs.

Validates that JSON outputs match the registered Pydantic contracts.
"""

from __future__ import annotations

from sqlfy.contracts import get_contract
from sqlfy.contracts.graph.v1 import GraphManifestV1, GraphOutputV1


class TestContractRegistry:
    """Verify contracts are properly registered."""

    def test_manifest_contract_registered(self):
        entry = get_contract("manifest@v1")
        assert entry.name == "manifest"
        assert entry.version == "v1"
        assert entry.command == "manifest"
        assert entry.model_class.__name__ == "GraphManifestV1"

    def test_graph_output_contract_registered(self):
        entry = get_contract("graph_output@v1")
        assert entry.name == "graph_output"
        assert entry.version == "v1"
        assert entry.command == "graph"
        assert entry.model_class.__name__ == "GraphOutputV1"


class TestGraphManifestContract:
    """Tests for GraphManifestV1 contract shape and validation."""

    def test_manifest_minimal_valid(self):
        """Minimal valid manifest output validates."""
        data = {
            "schemaVersion": "1",
            "fingerprint": "abc123",
            "dialect": "oracle",
            "generatedAt": "2024-01-01T00:00:00Z",
            "sqlfyVersion": "0.20.0",
            "nodeCount": 5,
            "edgeCount": 3,
            "tableCount": 3,
            "columnCount": 15,
            "sequenceCount": 2,
            "relationshipCount": 3,
            "indexCount": 5,
            "tablesWithoutPk": 0,
            "migrationCount": 1,
            "migrationHistory": [{"version": "1", "description": "create tables"}],
        }
        model = GraphManifestV1.model_validate(data)
        assert model.schema_version == "1"
        assert model.table_count == 3
        assert model.contract_version == "v1"

    def test_manifest_with_all_fields(self):
        data = {
            "schemaVersion": "5",
            "fingerprint": "deadbeef",
            "dialect": "postgres",
            "generatedAt": "2024-06-15T12:30:00Z",
            "sqlfyVersion": "0.20.0",
            "nodeCount": 25,
            "edgeCount": 18,
            "tableCount": 15,
            "columnCount": 120,
            "sequenceCount": 3,
            "relationshipCount": 18,
            "indexCount": 42,
            "tablesWithoutPk": 2,
            "migrationCount": 5,
            "migrationHistory": [
                {"version": "1", "description": "initial schema"},
                {"version": "2", "description": "add orders"},
                {"version": "3", "description": "add payments"},
                {"version": "4", "description": "add indexes"},
                {"version": "5", "description": "add audit columns"},
            ],
        }
        model = GraphManifestV1.model_validate(data)
        assert model.node_count == 25
        assert model.edge_count == 18
        assert len(model.migration_history) == 5
        assert model.migration_history[0].version == "1"
        assert model.migration_history[-1].description == "add audit columns"

    def test_manifest_contract_version_serializes(self):
        data = {
            "schemaVersion": "1",
            "fingerprint": "abc",
            "dialect": "oracle",
            "generatedAt": "2024-01-01T00:00:00Z",
            "sqlfyVersion": "0.20.0",
            "nodeCount": 0,
            "edgeCount": 0,
            "tableCount": 0,
            "columnCount": 0,
            "sequenceCount": 0,
            "relationshipCount": 0,
            "indexCount": 0,
            "tablesWithoutPk": 0,
            "migrationCount": 0,
            "migrationHistory": [],
        }
        model = GraphManifestV1.model_validate(data)
        json_output = model.model_dump_json(by_alias=True)
        assert '"contractVersion":"v1"' in json_output


class TestGraphOutputContract:
    """Tests for GraphOutputV1 contract shape and validation."""

    def test_graph_output_minimal_valid(self):
        """Minimal valid graph output validates."""
        data = {
            "version": "1",
            "generatedAt": "2024-01-01T00:00:00Z",
            "fingerprint": "abc123",
            "dialect": "oracle",
            "nodes": {},
            "edges": [],
            "communities": [],
            "godNodes": [],
            "meta": {},
        }
        model = GraphOutputV1.model_validate(data)
        assert model.version == "1"
        assert model.nodes == {}
        assert model.edges == []
        assert model.contract_version == "v1"

    def test_graph_output_with_data(self):
        data = {
            "version": "2",
            "generatedAt": "2024-01-01T00:00:00Z",
            "fingerprint": "def456",
            "dialect": "oracle",
            "nodes": {
                "APP.USERS": {
                    "id": "APP.USERS",
                    "label": "USERS",
                    "schema": "APP",
                    "type": "table",
                    "columns": [
                        {
                            "name": "ID",
                            "type": "NUMBER",
                            "isPk": True,
                            "nullable": False,
                        },
                        {
                            "name": "EMAIL",
                            "type": "VARCHAR2(255)",
                            "isFk": False,
                            "nullable": False,
                        },
                    ],
                },
                "APP.ORDERS": {
                    "id": "APP.ORDERS",
                    "label": "ORDERS",
                    "schema": "APP",
                    "type": "table",
                    "columns": [
                        {
                            "name": "ID",
                            "type": "NUMBER",
                            "isPk": True,
                            "nullable": False,
                        },
                        {
                            "name": "USER_ID",
                            "type": "NUMBER",
                            "isFk": True,
                            "nullable": False,
                        },
                    ],
                },
            },
            "edges": [
                {
                    "id": "fk_1",
                    "source": "APP.ORDERS",
                    "target": "APP.USERS",
                    "sourceCols": ["USER_ID"],
                    "targetCols": ["ID"],
                    "label": "FK_ORDERS_USER",
                }
            ],
            "communities": [
                {
                    "id": 1,
                    "label": "Core",
                    "nodes": ["APP.USERS", "APP.ORDERS"],
                    "cohesion": 0.85,
                }
            ],
            "godNodes": [
                {
                    "nodeId": "APP.USERS",
                    "degree": 5,
                    "inDegree": 2,
                    "outDegree": 3,
                    "communityId": 1,
                }
            ],
            "meta": {
                "resolution": 1.0,
                "minCohesion": 0.1,
            },
        }
        model = GraphOutputV1.model_validate(data)
        assert len(model.nodes) == 2
        assert len(model.edges) == 1
        assert len(model.communities) == 1
        assert len(model.god_nodes) == 1
        assert model.contract_version == "v1"

    def test_graph_output_contract_version_serializes(self):
        data = {
            "version": "1",
            "generatedAt": "2024-01-01T00:00:00Z",
            "fingerprint": "abc",
            "dialect": "oracle",
            "nodes": {},
            "edges": [],
            "communities": [],
            "godNodes": [],
            "meta": {},
        }
        model = GraphOutputV1.model_validate(data)
        json_output = model.model_dump_json(by_alias=True)
        assert '"contractVersion":"v1"' in json_output


class TestContractSchemaGeneration:
    """Verify JSON Schema generation for graph contracts."""

    def test_manifest_schema_generates(self):
        entry = get_contract("manifest@v1")
        schema = entry.generate_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "contractVersion" in schema["properties"]

    def test_graph_output_schema_generates(self):
        entry = get_contract("graph_output@v1")
        schema = entry.generate_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "contractVersion" in schema["properties"]
