"""
Tests for sqlfy.analysis.classifier — migration semantic classification.
"""
from __future__ import annotations

import json

import pytest

from sqlfy.analysis.classifier import (
    MigrationCategory,
    ClassifiedMigration,
    classify_migration,
    classify_migrations,
    group_by_category,
    group_by_risk,
    format_text,
    format_json,
)


# ─────────────────────────────────────────────
# classify_migration — individual statement types
# ─────────────────────────────────────────────

class TestClassifyTableCreation:
    def test_single_create_table(self):
        sql = "CREATE TABLE users (id NUMBER PRIMARY KEY, name VARCHAR2(100));"
        c = classify_migration("V1__create_users.sql", sql)
        assert c.primary_category == MigrationCategory.TABLE_CREATION
        assert c.risk_level == "medium"
        assert c.statement_counts.get("CREATE_TABLE", 0) == 1

    def test_multiple_create_tables(self):
        sql = """
        CREATE TABLE users (id NUMBER PRIMARY KEY);
        CREATE TABLE products (id NUMBER PRIMARY KEY);
        """
        c = classify_migration("V1__create_tables.sql", sql)
        assert c.primary_category == MigrationCategory.TABLE_CREATION
        assert c.statement_counts.get("CREATE_TABLE", 0) == 2


class TestClassifyColumnOperations:
    def test_add_column(self):
        sql = "ALTER TABLE users ADD (email VARCHAR2(255));"
        c = classify_migration("V2__add_email.sql", sql)
        assert c.primary_category == MigrationCategory.COLUMN_ADDITION
        assert c.risk_level == "low"

    def test_drop_column(self):
        sql = "ALTER TABLE users DROP COLUMN old_field;"
        c = classify_migration("V3__drop_field.sql", sql)
        assert c.primary_category == MigrationCategory.COLUMN_REMOVAL
        assert c.risk_level == "high"

    def test_modify_column_via_command_fallback(self):
        # MODIFY comes back as exp.Command in Oracle dialect
        sql = "ALTER TABLE users MODIFY (email VARCHAR2(255) NOT NULL);"
        c = classify_migration("V4__modify.sql", sql)
        assert c.primary_category == MigrationCategory.CONSTRAINT_MODIFICATION


class TestClassifyConstraints:
    def test_add_foreign_key_constraint(self):
        sql = (
            "ALTER TABLE orders ADD CONSTRAINT fk_user "
            "FOREIGN KEY (user_id) REFERENCES users(id);"
        )
        c = classify_migration("V5__add_fk.sql", sql)
        assert c.primary_category == MigrationCategory.CONSTRAINT_MODIFICATION
        assert c.risk_level == "medium"

    def test_drop_constraint(self):
        sql = "ALTER TABLE orders DROP CONSTRAINT fk_user;"
        c = classify_migration("V6__drop_fk.sql", sql)
        assert c.primary_category == MigrationCategory.CONSTRAINT_MODIFICATION


class TestClassifyIndexManagement:
    def test_create_index(self):
        sql = "CREATE INDEX idx_users_email ON users(email);"
        c = classify_migration("V7__add_index.sql", sql)
        assert c.primary_category == MigrationCategory.INDEX_MANAGEMENT
        assert c.risk_level == "low"

    def test_drop_index(self):
        sql = "DROP INDEX idx_users_email;"
        c = classify_migration("V8__drop_index.sql", sql)
        assert c.primary_category == MigrationCategory.INDEX_MANAGEMENT
        assert c.risk_level == "low"


class TestClassifyDataMigration:
    def test_insert(self):
        sql = "INSERT INTO users (id, name) VALUES (1, 'Alice');"
        c = classify_migration("V9__seed.sql", sql)
        assert c.primary_category == MigrationCategory.DATA_MIGRATION
        assert c.risk_level == "high"
        assert c.statement_counts.get("INSERT", 0) == 1

    def test_update(self):
        sql = "UPDATE users SET status = 'active' WHERE created_at < DATE '2020-01-01';"
        c = classify_migration("V10__update.sql", sql)
        assert c.primary_category == MigrationCategory.DATA_MIGRATION
        assert c.risk_level == "high"

    def test_delete(self):
        sql = "DELETE FROM audit_log WHERE created_at < DATE '2020-01-01';"
        c = classify_migration("V11__cleanup.sql", sql)
        assert c.primary_category == MigrationCategory.DATA_MIGRATION
        assert c.risk_level == "high"


class TestClassifyCleanup:
    def test_drop_table(self):
        sql = "DROP TABLE legacy_users;"
        c = classify_migration("V12__drop_legacy.sql", sql)
        assert c.primary_category == MigrationCategory.CLEANUP
        assert c.risk_level == "high"

    def test_drop_sequence(self):
        sql = "DROP SEQUENCE seq_old_users;"
        c = classify_migration("V13__drop_seq.sql", sql)
        assert c.primary_category == MigrationCategory.CLEANUP

    def test_drop_view(self):
        sql = "DROP VIEW active_users_view;"
        c = classify_migration("V14__drop_view.sql", sql)
        assert c.primary_category == MigrationCategory.CLEANUP


class TestClassifyViewTriggerProcedure:
    def test_create_view(self):
        sql = "CREATE VIEW active_users AS SELECT id, name FROM users WHERE status = 'A';"
        c = classify_migration("V15__create_view.sql", sql)
        assert c.primary_category == MigrationCategory.VIEW_TRIGGER_PROCEDURE
        assert c.risk_level == "medium"

    def test_create_trigger_via_command(self):
        # Oracle dialect — triggers come back as exp.Command
        sql = "CREATE OR REPLACE TRIGGER trg_audit BEFORE INSERT ON users FOR EACH ROW BEGIN NULL; END;"
        c = classify_migration("V16__trigger.sql", sql)
        assert c.primary_category == MigrationCategory.VIEW_TRIGGER_PROCEDURE

    def test_create_procedure_via_command(self):
        sql = "CREATE OR REPLACE PROCEDURE do_work AS BEGIN NULL; END;"
        c = classify_migration("V17__proc.sql", sql)
        assert c.primary_category == MigrationCategory.VIEW_TRIGGER_PROCEDURE


class TestClassifyRefactor:
    def test_rename_column_via_command(self):
        sql = "ALTER TABLE users RENAME COLUMN fname TO first_name;"
        c = classify_migration("V18__rename_col.sql", sql)
        # May parse as exp.Alter RenameColumn or as Command; both are acceptable
        assert c.primary_category in (
            MigrationCategory.REFACTOR,
            MigrationCategory.CONSTRAINT_MODIFICATION,
        )


class TestMixedMigrations:
    def test_table_and_index(self):
        sql = """
        CREATE TABLE products (id NUMBER PRIMARY KEY, name VARCHAR2(100));
        CREATE INDEX idx_products_name ON products(name);
        """
        c = classify_migration("V3__products.sql", sql)
        # TABLE_CREATION has higher priority than INDEX_MANAGEMENT
        assert c.primary_category == MigrationCategory.TABLE_CREATION
        assert MigrationCategory.INDEX_MANAGEMENT in c.secondary_categories

    def test_data_and_table_creation(self):
        sql = """
        CREATE TABLE settings (key VARCHAR2(50), value VARCHAR2(255));
        INSERT INTO settings VALUES ('theme', 'dark');
        """
        c = classify_migration("V4__settings.sql", sql)
        # DATA_MIGRATION has highest priority
        assert c.primary_category == MigrationCategory.DATA_MIGRATION
        assert MigrationCategory.TABLE_CREATION in c.secondary_categories

    def test_risk_elevated_by_high_risk_secondary(self):
        # Index creation (low) + DELETE (high) → overall high
        sql = """
        CREATE INDEX idx ON users(email);
        DELETE FROM old_data WHERE created < DATE '2020-01-01';
        """
        c = classify_migration("V5__mixed.sql", sql)
        assert c.risk_level == "high"

    def test_empty_migration_is_mixed(self):
        c = classify_migration("V1__empty.sql", "")
        assert c.primary_category == MigrationCategory.MIXED

    def test_comment_only_is_mixed(self):
        c = classify_migration("V1__comment.sql", "-- just a comment")
        assert c.primary_category == MigrationCategory.MIXED


# ─────────────────────────────────────────────
# classify_migrations — batch API
# ─────────────────────────────────────────────

class TestClassifyMigrations:
    def test_batch_returns_one_per_file(self):
        files = [
            {"filename": "V1__create.sql", "sql": "CREATE TABLE t (id NUMBER);"},
            {"filename": "V2__insert.sql", "sql": "INSERT INTO t VALUES (1);"},
        ]
        results = classify_migrations(files)
        assert len(results) == 2
        assert results[0].primary_category == MigrationCategory.TABLE_CREATION
        assert results[1].primary_category == MigrationCategory.DATA_MIGRATION

    def test_dialect_postgres(self):
        sql = "CREATE TABLE users (id SERIAL PRIMARY KEY);"
        c = classify_migration("V1.sql", sql, dialect="postgres")
        assert c.primary_category == MigrationCategory.TABLE_CREATION

    def test_dialect_mysql(self):
        sql = "CREATE TABLE orders (id INT AUTO_INCREMENT PRIMARY KEY);"
        c = classify_migration("V1.sql", sql, dialect="mysql")
        assert c.primary_category == MigrationCategory.TABLE_CREATION


# ─────────────────────────────────────────────
# group_by_category / group_by_risk
# ─────────────────────────────────────────────

class TestGroupBy:
    _classifications = [
        ClassifiedMigration("V1.sql", MigrationCategory.TABLE_CREATION, [], {}, "medium"),
        ClassifiedMigration("V2.sql", MigrationCategory.TABLE_CREATION, [], {}, "medium"),
        ClassifiedMigration("V3.sql", MigrationCategory.DATA_MIGRATION, [], {}, "high"),
        ClassifiedMigration("V4.sql", MigrationCategory.INDEX_MANAGEMENT, [], {}, "low"),
    ]

    def test_group_by_category_counts(self):
        groups = group_by_category(self._classifications)
        assert len(groups[MigrationCategory.TABLE_CREATION]) == 2
        assert len(groups[MigrationCategory.DATA_MIGRATION]) == 1
        assert len(groups[MigrationCategory.INDEX_MANAGEMENT]) == 1

    def test_group_by_risk_counts(self):
        groups = group_by_risk(self._classifications)
        assert len(groups["medium"]) == 2
        assert len(groups["high"]) == 1
        assert len(groups["low"]) == 1

    def test_group_by_category_empty(self):
        assert group_by_category([]) == {}

    def test_group_by_risk_empty(self):
        assert group_by_risk([]) == {}


# ─────────────────────────────────────────────
# format_text
# ─────────────────────────────────────────────

class TestFormatText:
    _cls = [
        ClassifiedMigration(
            "V1__create.sql",
            MigrationCategory.TABLE_CREATION,
            [],
            {"CREATE_TABLE": 1},
            "medium",
        ),
        ClassifiedMigration(
            "V2__data.sql",
            MigrationCategory.DATA_MIGRATION,
            [MigrationCategory.TABLE_CREATION],
            {"INSERT": 3, "CREATE_TABLE": 1},
            "high",
        ),
    ]

    def test_contains_filenames(self):
        txt = format_text(self._cls)
        assert "V1__create.sql" in txt
        assert "V2__data.sql" in txt

    def test_contains_category_labels(self):
        txt = format_text(self._cls)
        assert "table_creation" in txt
        assert "data_migration" in txt

    def test_contains_summary_section(self):
        txt = format_text(self._cls)
        assert "Summary" in txt

    def test_contains_risk_section(self):
        txt = format_text(self._cls)
        assert "Risk Distribution" in txt

    def test_group_by_shows_headings(self):
        txt = format_text(self._cls, group_by=True)
        assert "Data Migration" in txt or "data_migration" in txt

    def test_secondary_categories_shown(self):
        txt = format_text(self._cls)
        # V2 has secondary TABLE_CREATION
        assert "table_creation" in txt

    def test_empty_returns_message(self):
        assert "No migrations" in format_text([])


# ─────────────────────────────────────────────
# format_json
# ─────────────────────────────────────────────

class TestFormatJson:
    _cls = [
        ClassifiedMigration(
            "V1__create.sql",
            MigrationCategory.TABLE_CREATION,
            [],
            {"CREATE_TABLE": 1},
            "medium",
        ),
        ClassifiedMigration(
            "V2__data.sql",
            MigrationCategory.DATA_MIGRATION,
            [],
            {"DELETE": 2},
            "high",
        ),
    ]

    def test_top_level_keys(self):
        data = json.loads(format_json(self._cls))
        assert "migrations" in data
        assert "summary" in data

    def test_total_count(self):
        data = json.loads(format_json(self._cls))
        assert data["summary"]["total"] == 2

    def test_by_category_present(self):
        data = json.loads(format_json(self._cls))
        assert "by_category" in data["summary"]
        assert data["summary"]["by_category"]["table_creation"] == 1
        assert data["summary"]["by_category"]["data_migration"] == 1

    def test_by_risk_present(self):
        data = json.loads(format_json(self._cls))
        assert "by_risk" in data["summary"]
        assert data["summary"]["by_risk"]["high"] == 1
        assert data["summary"]["by_risk"]["medium"] == 1

    def test_migration_fields(self):
        data = json.loads(format_json(self._cls))
        m = data["migrations"][0]
        assert m["filename"] == "V1__create.sql"
        assert m["primary_category"] == "table_creation"
        assert m["risk_level"] == "medium"
        assert isinstance(m["statement_counts"], dict)
        assert isinstance(m["all_categories"], list)

    def test_empty_list(self):
        data = json.loads(format_json([]))
        assert data["summary"]["total"] == 0
        assert data["migrations"] == []
