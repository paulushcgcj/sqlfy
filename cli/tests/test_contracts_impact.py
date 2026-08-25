"""Contract tests for impact command JSON outputs.

Validates that JSON outputs match the registered Pydantic contracts.
"""

from __future__ import annotations

import pytest

from sqlfy.contracts import CONTRACTS, get_contract
from sqlfy.contracts.impact.v1 import ImpactV1


class TestContractRegistry:
    """Verify contracts are properly registered."""

    def test_impact_contract_registered(self):
        entry = get_contract("impact@v1")
        assert entry.name == "impact"
        assert entry.version == "v1"
        assert entry.command == "impact"
        assert entry.model_class.__name__ == "ImpactV1"


class TestImpactContract:
    """Tests for ImpactV1 contract shape and validation."""

    def test_impact_minimal_valid(self):
        """Minimal valid impact output validates."""
        data = {
            "objectId": "APP.USERS",
            "direct": ["APP.ORDERS"],
            "transitive": ["APP.ORDER_ITEMS"],
            "depthMap": {"APP.USERS": 0, "APP.ORDERS": 1, "APP.ORDER_ITEMS": 2},
            "byType": {"table": ["APP.ORDERS", "APP.ORDER_ITEMS"]},
            "criticalPaths": [["APP.USERS", "APP.ORDERS", "APP.ORDER_ITEMS"]],
            "maxDepth": 2,
            "totalCount": 2,
        }
        model = ImpactV1.model_validate(data)
        assert model.object_id == "APP.USERS"
        assert len(model.direct) == 1
        assert len(model.transitive) == 1
        assert model.max_depth == 2
        assert model.total_count == 2
        assert model.contract_version == "v1"

    def test_impact_with_multiple_direct(self):
        data = {
            "objectId": "APP.CUSTOMERS",
            "direct": ["APP.ORDERS", "APP.ADDRESSES", "APP.PAYMENTS"],
            "transitive": ["APP.ORDER_ITEMS", "APP.SHIPPING"],
            "depthMap": {
                "APP.CUSTOMERS": 0,
                "APP.ORDERS": 1,
                "APP.ADDRESSES": 1,
                "APP.PAYMENTS": 1,
                "APP.ORDER_ITEMS": 2,
                "APP.SHIPPING": 2,
            },
            "byType": {
                "table": [
                    "APP.ORDERS",
                    "APP.ADDRESSES",
                    "APP.PAYMENTS",
                    "APP.ORDER_ITEMS",
                    "APP.SHIPPING",
                ]
            },
            "criticalPaths": [
                ["APP.CUSTOMERS", "APP.ORDERS", "APP.ORDER_ITEMS"],
                ["APP.CUSTOMERS", "APP.ORDERS", "APP.SHIPPING"],
            ],
            "maxDepth": 2,
            "totalCount": 5,
        }
        model = ImpactV1.model_validate(data)
        assert len(model.direct) == 3
        assert len(model.transitive) == 2
        assert model.depth_map["APP.CUSTOMERS"] == 0
        assert model.by_type["table"] == [
            "APP.ORDERS",
            "APP.ADDRESSES",
            "APP.PAYMENTS",
            "APP.ORDER_ITEMS",
            "APP.SHIPPING",
        ]
        assert len(model.critical_paths) == 2

    def test_impact_missing_required_field_fails(self):
        data = {
            "objectId": "APP.USERS",
            # missing direct, transitive, depthMap, byType, criticalPaths, maxDepth, totalCount
        }
        with pytest.raises(Exception):
            ImpactV1.model_validate(data)

    def test_impact_extra_field_fails(self):
        data = {
            "objectId": "APP.USERS",
            "direct": [],
            "transitive": [],
            "depthMap": {},
            "byType": {},
            "criticalPaths": [],
            "maxDepth": 0,
            "totalCount": 0,
            "extra_field": "not allowed",
        }
        with pytest.raises(Exception):
            ImpactV1.model_validate(data)

    def test_impact_contract_version_serializes(self):
        data = {
            "objectId": "APP.USERS",
            "direct": [],
            "transitive": [],
            "depthMap": {},
            "byType": {},
            "criticalPaths": [],
            "maxDepth": 0,
            "totalCount": 0,
        }
        model = ImpactV1.model_validate(data)
        json_output = model.model_dump_json(by_alias=True)
        assert '"contractVersion":"v1"' in json_output


class TestContractSchemaGeneration:
    """Verify JSON Schema generation for impact contract."""

    def test_impact_schema_generates(self):
        entry = get_contract("impact@v1")
        schema = entry.generate_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "contractVersion" in schema["properties"]
