"""Contract tests for schema command JSON outputs.

Validates that JSON outputs match the registered Pydantic contracts.
"""

from __future__ import annotations

from sqlfy.contracts import get_contract
from sqlfy.contracts.chunks.v1 import ChunksV1
from sqlfy.contracts.query.v1 import QueryResultV1
from sqlfy.contracts.schema.v1 import SchemaStateV1
from sqlfy.models import VectorChunk


class TestContractRegistry:
    """Verify contracts are properly registered."""

    def test_schema_state_contract_registered(self):
        entry = get_contract("schema_state@v1")
        assert entry.name == "schema_state"
        assert entry.version == "v1"
        assert entry.command == "dump"
        assert entry.model_class.__name__ == "SchemaStateV1"

    def test_query_result_contract_registered(self):
        entry = get_contract("query_result@v1")
        assert entry.name == "query_result"
        assert entry.version == "v1"
        assert entry.command == "query"
        assert entry.model_class.__name__ == "QueryResultV1"

    def test_chunks_contract_registered(self):
        entry = get_contract("chunks@v1")
        assert entry.name == "chunks"
        assert entry.version == "v1"
        assert entry.command == "chunks"
        assert entry.model_class.__name__ == "ChunksV1"


class TestSchemaStateContract:
    """Tests for SchemaStateV1 contract shape and validation."""

    def test_schema_state_minimal_valid(self):
        """Minimal valid schema state output validates."""
        data = {
            "version": "1",
            "generatedAt": "2024-01-01T00:00:00Z",
            "fingerprint": "abc123",
            "dialect": "oracle",
            "sqlfyVersion": "0.20.0",
            "tables": {},
            "sequences": {},
            "relationships": [],
            "migrationHistory": [],
            "stats": {},
        }
        model = SchemaStateV1.model_validate(data)
        assert model.version == "1"
        assert model.tables == {}
        assert model.contract_version == "v1"

    def test_schema_state_with_tables(self):
        data = {
            "version": "2",
            "generatedAt": "2024-01-01T00:00:00Z",
            "fingerprint": "def456",
            "dialect": "oracle",
            "sqlfyVersion": "0.20.0",
            "tables": {
                "APP.USERS": {
                    "schema": "APP",
                    "name": "USERS",
                    "fullName": "APP.USERS",
                    "columns": [
                        {
                            "name": "ID",
                            "dataType": "NUMBER",
                            "rawType": "NUMBER",
                            "precision": None,
                            "scale": None,
                            "nullable": False,
                            "default": None,
                            "isPk": True,
                            "isFk": False,
                            "isUnique": False,
                            "comment": None,
                        },
                        {
                            "name": "EMAIL",
                            "dataType": "VARCHAR2(255)",
                            "rawType": "VARCHAR2",
                            "precision": None,
                            "scale": None,
                            "nullable": False,
                            "default": None,
                            "isPk": False,
                            "isFk": False,
                            "isUnique": True,
                            "comment": "User email",
                        },
                    ],
                    "constraints": [
                        {"name": "PK_USERS", "type": "primary_key", "columns": ["ID"]},
                        {
                            "name": "UK_USERS_EMAIL",
                            "type": "unique",
                            "columns": ["EMAIL"],
                        },
                    ],
                    "indexes": [
                        {
                            "name": "IDX_USERS_EMAIL",
                            "columns": ["EMAIL"],
                            "unique": True,
                            "createdIn": "1",
                        }
                    ],
                    "comment": "User accounts",
                    "createdIn": "1",
                    "modifiedIn": [],
                    "columnCount": 2,
                    "hasPk": True,
                    "pkColumns": ["ID"],
                }
            },
            "sequences": {
                "APP.SEQ_USERS": {
                    "schema": "APP",
                    "name": "SEQ_USERS",
                    "fullName": "APP.SEQ_USERS",
                    "startWith": 1,
                    "incrementBy": 1,
                    "createdIn": "1",
                }
            },
            "relationships": [
                {
                    "id": "fk_1",
                    "fromTable": "APP.ORDERS",
                    "fromColumns": ["USER_ID"],
                    "toTable": "APP.USERS",
                    "toColumns": ["ID"],
                    "constraintName": "FK_ORDERS_USER",
                    "onDelete": "CASCADE",
                    "cardinality": "many_to_one",
                }
            ],
            "migrationHistory": [
                {"version": "1", "description": "create users"},
                {"version": "2", "description": "add orders"},
            ],
            "stats": {
                "table_count": 2,
                "column_count": 8,
                "sequence_count": 1,
                "relationship_count": 1,
                "index_count": 3,
                "tables_without_pk": 0,
                "migration_count": 2,
            },
        }
        model = SchemaStateV1.model_validate(data)
        assert len(model.tables) == 1
        assert "APP.USERS" in model.tables
        assert model.tables["APP.USERS"].column_count == 2
        assert len(model.sequences) == 1
        assert len(model.relationships) == 1
        assert model.stats["table_count"] == 2

    def test_schema_state_contract_version_serializes(self):
        data = {
            "version": "1",
            "generatedAt": "2024-01-01T00:00:00Z",
            "fingerprint": "abc",
            "dialect": "oracle",
            "sqlfyVersion": "0.20.0",
            "tables": {},
            "sequences": {},
            "relationships": [],
            "migrationHistory": [],
            "stats": {},
        }
        model = SchemaStateV1.model_validate(data)
        json_output = model.model_dump_json(by_alias=True)
        assert '"contractVersion":"v1"' in json_output


class TestQueryResultContract:
    """Tests for QueryResultV1 contract shape and validation."""

    def test_query_result_minimal_valid(self):
        """Minimal valid query result validates."""
        data = {
            "query": "tables in schema APP",
            "count": 0,
            "columns": ["TABLE_NAME", "SCHEMA"],
            "rows": [],
            "meta": {},
        }
        model = QueryResultV1.model_validate(data)
        assert model.query == "tables in schema APP"
        assert model.count == 0
        assert model.columns == ["TABLE_NAME", "SCHEMA"]
        assert model.contract_version == "v1"

    def test_query_result_with_rows(self):
        data = {
            "query": "fk-path from APP.ORDERS to APP.USERS",
            "count": 1,
            "columns": ["PATH", "LENGTH"],
            "rows": [{"PATH": "APP.ORDERS -> APP.USERS", "LENGTH": 1}],
            "meta": {"length": 1, "from": "APP.ORDERS", "to": "APP.USERS"},
        }
        model = QueryResultV1.model_validate(data)
        assert len(model.rows) == 1
        assert model.meta["from"] == "APP.ORDERS"
        assert model.contract_version == "v1"

    def test_query_result_contract_version_serializes(self):
        data = {
            "query": "test",
            "count": 0,
            "columns": [],
            "rows": [],
            "meta": {},
        }
        model = QueryResultV1.model_validate(data)
        json_output = model.model_dump_json(by_alias=True)
        assert '"contractVersion":"v1"' in json_output


class TestChunksContract:
    """Tests for ChunksV1 contract shape and validation."""

    def test_chunks_minimal_valid(self):
        """Minimal valid chunks output validates."""
        data = {
            "chunks": [],
            "count": 0,
            "meta": {},
        }
        model = ChunksV1.model_validate(data)
        assert model.chunks == []
        assert model.count == 0
        assert model.contract_version == "v1"

    def test_chunks_with_data(self):
        chunk_data = VectorChunk(
            id="chunk_1",
            type="table",
            title="APP.USERS",
            content="TABLE: APP.USERS\nCOLUMNS:\n  ID: NUMBER [PK]",
            metadata={"table": "APP.USERS"},
            hint="User accounts table",
        )
        data = {
            "chunks": [chunk_data.model_dump(by_alias=True)],
            "count": 1,
            "meta": {"schema_version": "1"},
        }
        model = ChunksV1.model_validate(data)
        assert len(model.chunks) == 1
        assert model.chunks[0].id == "chunk_1"
        assert model.chunks[0].title == "APP.USERS"
        assert model.count == 1

    def test_chunks_contract_version_serializes(self):
        data = {
            "chunks": [],
            "count": 0,
            "meta": {},
        }
        model = ChunksV1.model_validate(data)
        json_output = model.model_dump_json(by_alias=True)
        assert '"contractVersion":"v1"' in json_output


class TestContractSchemaGeneration:
    """Verify JSON Schema generation for schema contracts."""

    def test_schema_state_schema_generates(self):
        entry = get_contract("schema_state@v1")
        schema = entry.generate_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "contractVersion" in schema["properties"]

    def test_query_result_schema_generates(self):
        entry = get_contract("query_result@v1")
        schema = entry.generate_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "contractVersion" in schema["properties"]

    def test_chunks_schema_generates(self):
        entry = get_contract("chunks@v1")
        schema = entry.generate_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "contractVersion" in schema["properties"]
