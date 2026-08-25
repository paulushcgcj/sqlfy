"""Contract tests for analysis command JSON outputs.

Validates that JSON outputs match the registered Pydantic contracts.
"""

from __future__ import annotations

import json

import pytest

from sqlfy.contracts import CONTRACTS, get_contract
from sqlfy.contracts.analysis.v1 import HealthV1, InsightsV1
from sqlfy.contracts.analysis.pii_v1 import PiiScanV1


class TestContractRegistry:
    """Verify contracts are properly registered."""

    def test_insights_contract_registered(self):
        entry = get_contract("insights@v1")
        assert entry.name == "insights"
        assert entry.version == "v1"
        assert entry.command == "insights"
        assert entry.model_class is InsightsV1

    def test_health_contract_registered(self):
        entry = get_contract("health@v1")
        assert entry.name == "health"
        assert entry.version == "v1"
        assert entry.command == "health"
        assert entry.model_class is HealthV1

    def test_pii_scan_contract_registered(self):
        entry = get_contract("pii_scan@v1")
        assert entry.name == "pii_scan"
        assert entry.version == "v1"
        assert entry.command == "pii-scan"
        assert entry.model_class is PiiScanV1

    def test_all_contracts_have_unique_keys(self):
        keys = [e.key for e in CONTRACTS.values()]
        assert len(keys) == len(set(keys)), "Duplicate contract keys found"


class TestInsightsContract:
    """Tests for InsightsV1 contract shape and validation."""

    def test_insights_minimal_valid(self):
        """Minimal valid insights output validates."""
        data = {
            "version": "1",
            "fingerprint": "abc123",
            "summary": {
                "errors": 0,
                "warnings": 0,
                "infos": 0,
                "total": 0,
                "healthy": True,
            },
            "findings": {"error": [], "warning": [], "info": []},
            "godTables": None,
            "surprisingJoins": None,
            "diagnostics": {"total": 0, "errors": 0, "warnings": 0, "infos": 0},
        }
        # Should not raise
        model = InsightsV1.model_validate(data)
        assert model.version == "1"
        assert model.contract_version == "v1"

    def test_insights_with_findings(self):
        """Insights with findings validates."""
        data = {
            "version": "2",
            "fingerprint": "def456",
            "summary": {
                "errors": 1,
                "warnings": 2,
                "infos": 3,
                "total": 6,
                "healthy": False,
            },
            "findings": {
                "error": [
                    {
                        "code": "NO_PK",
                        "severity": "error",
                        "category": "structural",
                        "message": "Table has no primary key",
                        "detail": None,
                        "fix": "Add primary key",
                        "table": "APP.USERS",
                        "column": None,
                    }
                ],
                "warning": [
                    {
                        "code": "ORPHAN_TABLE",
                        "severity": "warning",
                        "category": "structural",
                        "message": "Table has no FK relationships",
                        "detail": None,
                        "fix": None,
                        "table": "APP.LOGS",
                        "column": None,
                    },
                    {
                        "code": "WIDE_TABLE",
                        "severity": "warning",
                        "category": "modelling",
                        "message": "Table has many columns",
                        "detail": "25 columns",
                        "fix": None,
                        "table": "APP.ORDERS",
                        "column": None,
                    },
                ],
                "info": [
                    {
                        "code": "EMPTY_TABLE_COMMENT",
                        "severity": "info",
                        "category": "structural",
                        "message": "Table has no comment",
                        "detail": None,
                        "fix": "Add comment",
                        "table": "APP.USERS",
                        "column": None,
                    }
                ],
            },
            "godTables": [
                {
                    "tableName": "APP.USERS",
                    "degree": 5,
                    "inDegree": 3,
                    "outDegree": 2,
                    "communityId": 1,
                    "communityLabel": "Core",
                }
            ],
            "surprisingJoins": [
                {
                    "fromTable": "APP.ORDERS",
                    "toTable": "APP.USERS",
                    "viaColumn": "USER_ID",
                    "fromCommunity": 1,
                    "toCommunity": 2,
                    "fromCommunityLabel": "Core",
                    "toCommunityLabel": "Reporting",
                    "surpriseScore": 0.85,
                }
            ],
            "diagnostics": {"total": 5, "errors": 1, "warnings": 2, "infos": 2},
        }
        model = InsightsV1.model_validate(data)
        assert len(model.findings.error) == 1
        assert len(model.findings.warning) == 2
        assert len(model.findings.info) == 1
        assert model.god_tables is not None
        assert len(model.god_tables) == 1
        assert model.surprising_joins is not None
        assert len(model.surprising_joins) == 1

    def test_insights_missing_required_field_fails(self):
        """Missing required field should fail validation."""
        data = {
            "version": "1",
            "fingerprint": "abc",
            # missing summary
            "findings": {"error": [], "warning": [], "info": []},
        }
        with pytest.raises(Exception):  # Pydantic validation error
            InsightsV1.model_validate(data)

    def test_insights_extra_field_fails(self):
        """Extra field should fail (extra='forbid')."""
        data = {
            "version": "1",
            "fingerprint": "abc",
            "summary": {
                "errors": 0,
                "warnings": 0,
                "infos": 0,
                "total": 0,
                "healthy": True,
            },
            "findings": {"error": [], "warning": [], "info": []},
            "extra_field": "not allowed",
        }
        with pytest.raises(Exception):
            InsightsV1.model_validate(data)

    def test_insights_contract_version_serializes(self):
        """contractVersion field serializes to camelCase."""
        data = {
            "version": "1",
            "fingerprint": "abc",
            "summary": {
                "errors": 0,
                "warnings": 0,
                "infos": 0,
                "total": 0,
                "healthy": True,
            },
            "findings": {"error": [], "warning": [], "info": []},
            "diagnostics": {"total": 0, "errors": 0, "warnings": 0, "infos": 0},
        }
        model = InsightsV1.model_validate(data)
        json_output = model.model_dump_json(by_alias=True)
        assert '"contractVersion":"v1"' in json_output


class TestHealthContract:
    """Tests for HealthV1 contract shape and validation."""

    def test_health_minimal_valid(self):
        """Minimal valid health output validates."""
        data = {
            "folder": "/migrations",
            "timestamp": "2024-01-01T00:00:00Z",
            "summary": {
                "totalMigrations": 10,
                "safeMigrations": 8,
                "unsafeMigrations": 2,
                "irreversibleMigrations": 0,
                "safePercentage": 80,
            },
            "findings": {
                "errors": 2,
                "warnings": 5,
                "infos": 3,
                "byCode": {"NO_PK": 2, "ORPHAN_TABLE": 3},
            },
            "migrations": [
                {
                    "filename": "V1__create.sql",
                    "status": "safe",
                    "errors": 0,
                    "warnings": 0,
                    "hasDropTable": False,
                    "hasDropColumn": False,
                }
            ],
            "healthScore": {
                "score": 80,
                "grade": "good",
                "breakdown": {
                    "base": 100,
                    "errorPenalty": 10,
                    "warningPenalty": 5,
                    "irreversiblePenalty": 5,
                },
            },
            "recommendation": "Review unsafe migrations",
        }
        model = HealthV1.model_validate(data)
        assert model.folder == "/migrations"
        assert model.health_score.score == 80

    def test_health_contract_version_serializes(self):
        data = {
            "folder": "/migrations",
            "timestamp": "2024-01-01T00:00:00Z",
            "summary": {
                "totalMigrations": 0,
                "safeMigrations": 0,
                "unsafeMigrations": 0,
                "irreversibleMigrations": 0,
                "safePercentage": 100,
            },
            "findings": {"errors": 0, "warnings": 0, "infos": 0, "byCode": {}},
            "migrations": [],
            "healthScore": {
                "score": 100,
                "grade": "excellent",
                "breakdown": {
                    "base": 100,
                    "errorPenalty": 0,
                    "warningPenalty": 0,
                    "irreversiblePenalty": 0,
                },
            },
            "recommendation": "All good",
        }
        model = HealthV1.model_validate(data)
        json_output = model.model_dump_json(by_alias=True)
        assert '"contractVersion":"v1"' in json_output


class TestPiiScanContract:
    """Tests for PiiScanV1 contract shape and validation."""

    def test_pii_scan_minimal_valid(self):
        """Minimal valid PII scan output validates."""
        data = {
            "tables_scanned": 1,
            "columns_scanned": 5,
            "pii_table_count": 0,
            "pii_column_count": 0,
            "findings": [],
        }
        model = PiiScanV1.model_validate(data)
        assert model.tables_scanned == 1
        assert model.contract_version == "v1"

    def test_pii_scan_with_findings(self):
        """PII scan with findings validates."""
        data = {
            "tables_scanned": 2,
            "columns_scanned": 10,
            "pii_table_count": 1,
            "pii_column_count": 2,
            "findings": [
                {
                    "table_name": "APP.USERS",
                    "column_name": "EMAIL",
                    "column_type": "VARCHAR2",
                    "pii_categories": ["email"],
                    "confidence": 1.0,
                    "evidence": "Column name matches email pattern",
                },
                {
                    "table_name": "APP.USERS",
                    "column_name": "PHONE",
                    "column_type": "VARCHAR2",
                    "pii_categories": ["phone"],
                    "confidence": 0.8,
                    "evidence": "Column name matches phone pattern",
                },
            ],
        }
        model = PiiScanV1.model_validate(data)
        assert len(model.findings) == 2
        assert model.findings[0].pii_categories == ["email"]
        assert model.findings[1].confidence == 0.8

    def test_pii_scan_contract_version_serializes(self):
        data = {
            "tables_scanned": 0,
            "columns_scanned": 0,
            "pii_table_count": 0,
            "pii_column_count": 0,
            "findings": [],
        }
        model = PiiScanV1.model_validate(data)
        json_output = model.model_dump_json(by_alias=True)
        assert '"contractVersion":"v1"' in json_output


class TestContractSchemaGeneration:
    """Verify JSON Schema generation for contracts."""

    def test_insights_schema_generates(self):
        entry = get_contract("insights@v1")
        schema = entry.generate_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "contractVersion" in schema["properties"]

    def test_health_schema_generates(self):
        entry = get_contract("health@v1")
        schema = entry.generate_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "contractVersion" in schema["properties"]

    def test_pii_scan_schema_generates(self):
        entry = get_contract("pii_scan@v1")
        schema = entry.generate_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "contractVersion" in schema["properties"]
