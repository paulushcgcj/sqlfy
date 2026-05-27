"""Tests for analysis.safety — migration safety-level scoring (Feature #15)."""
import json
import pytest
from sqlfy.analysis.safety import (
    score_migration, score_migrations,
    format_text, format_json,
    MigrationSafety, StatementRisk,
    _LEVEL_ORDER,
)


# ─────────────────────────────────────────────
# DROP operations
# ─────────────────────────────────────────────

class TestDropOperations:
    def test_drop_table_is_dangerous(self):
        sql = "DROP TABLE user_sessions;"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "DANGEROUS"

    def test_drop_view_is_high_risk(self):
        sql = "DROP VIEW v_active_users;"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "HIGH_RISK"

    def test_drop_index_is_medium_risk(self):
        sql = "DROP INDEX idx_users_email;"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "MEDIUM_RISK"

    def test_drop_column_via_alter_is_high_risk(self):
        sql = "ALTER TABLE users DROP COLUMN email;"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "HIGH_RISK"
        assert result.statement_risks[0].statement_type == "DROP COLUMN"

    def test_statement_type_for_drop_table(self):
        sql = "DROP TABLE sessions;"
        result = score_migration("V1.sql", sql)
        assert result.statement_risks[0].statement_type == "DROP TABLE"


# ─────────────────────────────────────────────
# CREATE operations
# ─────────────────────────────────────────────

class TestCreateOperations:
    def test_create_table_is_safe(self):
        sql = "CREATE TABLE orders (id NUMBER PRIMARY KEY, total NUMBER);"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "SAFE"

    def test_create_index_without_concurrently_is_medium(self):
        sql = "CREATE INDEX idx_orders_total ON orders(total);"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "MEDIUM_RISK"

    def test_create_index_concurrently_is_safe(self):
        sql = "CREATE INDEX CONCURRENTLY idx_orders_total ON orders(total);"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "SAFE"

    def test_create_sequence_is_safe(self):
        sql = "CREATE SEQUENCE order_seq START WITH 1 INCREMENT BY 1;"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "SAFE"


# ─────────────────────────────────────────────
# ALTER TABLE — ADD COLUMN
# ─────────────────────────────────────────────

class TestAlterAddColumn:
    def test_add_nullable_column_is_safe(self):
        sql = "ALTER TABLE users ADD (phone VARCHAR2(20));"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "SAFE"
        assert result.statement_risks[0].statement_type == "ADD COLUMN"

    def test_add_not_null_no_default_is_high_risk(self):
        sql = "ALTER TABLE users ADD (email VARCHAR2(255) NOT NULL);"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "HIGH_RISK"
        assert result.statement_risks[0].statement_type == "ADD COLUMN NOT NULL"

    def test_add_not_null_with_default_is_safe(self):
        sql = "ALTER TABLE users ADD (status VARCHAR2(10) DEFAULT 'A');"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "SAFE"

    def test_add_column_non_oracle_syntax_nullable_is_safe(self):
        sql = "ALTER TABLE users ADD phone VARCHAR2(20);"
        result = score_migration("V1.sql", sql, dialect="mysql")
        assert result.overall_level == "SAFE"


# ─────────────────────────────────────────────
# ALTER TABLE — other actions
# ─────────────────────────────────────────────

class TestAlterOtherActions:
    def test_add_constraint_is_medium_risk(self):
        sql = "ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id);"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "MEDIUM_RISK"
        assert result.statement_risks[0].statement_type == "ADD CONSTRAINT"

    def test_drop_constraint_is_medium_risk(self):
        sql = "ALTER TABLE orders DROP CONSTRAINT fk_user;"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "MEDIUM_RISK"

    def test_rename_column_is_medium_risk(self):
        sql = "ALTER TABLE users RENAME COLUMN old_name TO new_name;"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "MEDIUM_RISK"


# ─────────────────────────────────────────────
# DML operations
# ─────────────────────────────────────────────

class TestDMLOperations:
    def test_insert_is_safe(self):
        sql = "INSERT INTO code_table VALUES ('A', 'Active');"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "SAFE"

    def test_delete_without_where_is_dangerous(self):
        sql = "DELETE FROM sessions;"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "DANGEROUS"
        assert result.statement_risks[0].statement_type == "DELETE WITHOUT WHERE"

    def test_delete_with_where_is_high_risk(self):
        sql = "DELETE FROM sessions WHERE expires_at < SYSDATE;"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "HIGH_RISK"
        assert result.statement_risks[0].statement_type == "DELETE"

    def test_update_without_where_is_dangerous(self):
        sql = "UPDATE users SET active = 0;"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "DANGEROUS"
        assert result.statement_risks[0].statement_type == "UPDATE WITHOUT WHERE"

    def test_update_with_where_is_high_risk(self):
        sql = "UPDATE users SET active = 0 WHERE last_login < SYSDATE - 365;"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "HIGH_RISK"
        assert result.statement_risks[0].statement_type == "UPDATE"


# ─────────────────────────────────────────────
# Oracle Command fallback (exp.Command)
# ─────────────────────────────────────────────

class TestCommandFallback:
    def test_truncate_is_dangerous(self):
        sql = "TRUNCATE TABLE sessions;"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "DANGEROUS"
        assert result.statement_risks[0].statement_type == "TRUNCATE"

    def test_oracle_modify_is_high_risk(self):
        sql = "ALTER TABLE users MODIFY (email VARCHAR2(255) NOT NULL);"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "HIGH_RISK"

    def test_create_trigger_is_safe(self):
        sql = "CREATE OR REPLACE TRIGGER trg_users BEFORE INSERT ON users BEGIN NULL; END;"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "SAFE"

    def test_create_procedure_is_safe(self):
        sql = "CREATE OR REPLACE PROCEDURE proc_test AS BEGIN NULL; END;"
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "SAFE"


# ─────────────────────────────────────────────
# Aggregation
# ─────────────────────────────────────────────

class TestAggregation:
    def test_overall_is_worst_case(self):
        sql = """
        CREATE TABLE audit_log (id NUMBER PRIMARY KEY);
        DROP TABLE sessions;
        """
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "DANGEROUS"
        assert len(result.statement_risks) == 2

    def test_safe_plus_medium_yields_medium(self):
        sql = """
        CREATE TABLE t1 (id NUMBER);
        CREATE INDEX idx_t1 ON t1(id);
        """
        result = score_migration("V1.sql", sql)
        assert result.overall_level == "MEDIUM_RISK"

    def test_empty_migration_is_safe(self):
        result = score_migration("V1.sql", "")
        assert result.overall_level == "SAFE"
        assert result.statement_risks == []

    def test_requires_approval_for_high_risk(self):
        sql = "ALTER TABLE users DROP COLUMN email;"
        result = score_migration("V1.sql", sql)
        assert result.requires_approval is True

    def test_requires_approval_for_dangerous(self):
        sql = "DROP TABLE users;"
        result = score_migration("V1.sql", sql)
        assert result.requires_approval is True

    def test_no_approval_needed_for_safe(self):
        sql = "CREATE TABLE t (id NUMBER);"
        result = score_migration("V1.sql", sql)
        assert result.requires_approval is False

    def test_no_approval_needed_for_medium(self):
        sql = "CREATE INDEX idx ON t(id);"
        result = score_migration("V1.sql", sql)
        assert result.requires_approval is False


# ─────────────────────────────────────────────
# Batch API
# ─────────────────────────────────────────────

class TestScoreMigrations:
    def test_returns_one_result_per_file(self):
        files = [
            {"filename": "V1.sql", "sql": "CREATE TABLE t1 (id NUMBER);"},
            {"filename": "V2.sql", "sql": "DROP TABLE t1;"},
        ]
        results = score_migrations(files)
        assert len(results) == 2

    def test_filenames_preserved(self):
        files = [{"filename": "my_migration.sql", "sql": "CREATE TABLE t (id NUMBER);"}]
        results = score_migrations(files)
        assert results[0].filename == "my_migration.sql"

    def test_levels_correct(self):
        files = [
            {"filename": "V1.sql", "sql": "CREATE TABLE t (id NUMBER);"},
            {"filename": "V2.sql", "sql": "DROP TABLE t;"},
        ]
        results = score_migrations(files)
        assert results[0].overall_level == "SAFE"
        assert results[1].overall_level == "DANGEROUS"


# ─────────────────────────────────────────────
# to_dict
# ─────────────────────────────────────────────

class TestToDict:
    def test_keys_present(self):
        result = score_migration("V1.sql", "CREATE TABLE t (id NUMBER);")
        d = result.to_dict()
        assert set(d.keys()) == {"filename", "overall_level", "requires_approval", "statements"}

    def test_statement_keys(self):
        result = score_migration("V1.sql", "DROP TABLE t;")
        stmt = result.to_dict()["statements"][0]
        assert set(stmt.keys()) == {"statement_type", "level", "reason", "sql_preview"}


# ─────────────────────────────────────────────
# format_text
# ─────────────────────────────────────────────

class TestFormatText:
    def _scores(self):
        return score_migrations([
            {"filename": "V1__create.sql", "sql": "CREATE TABLE t (id NUMBER);"},
            {"filename": "V2__drop.sql", "sql": "DROP TABLE t;"},
        ])

    def test_contains_filenames(self):
        out = format_text(self._scores())
        assert "V1__create.sql" in out
        assert "V2__drop.sql" in out

    def test_contains_level_labels(self):
        out = format_text(self._scores())
        assert "SAFE" in out
        assert "DANGEROUS" in out

    def test_contains_summary_section(self):
        out = format_text(self._scores())
        assert "Summary" in out

    def test_contains_risk_distribution(self):
        out = format_text(self._scores())
        assert "Risk Distribution" in out

    def test_approval_warning_shown_when_needed(self):
        out = format_text(self._scores())
        assert "require manual approval" in out

    def test_no_approval_warning_when_all_safe(self):
        scores = score_migrations([{"filename": "V1.sql", "sql": "CREATE TABLE t (id NUMBER);"}])
        out = format_text(scores)
        assert "require manual approval" not in out

    def test_empty_returns_message(self):
        assert format_text([]) == "No migrations to score."

    def test_verbose_shows_statement_types(self):
        scores = score_migrations([{"filename": "V1.sql", "sql": "DROP TABLE t;"}])
        out = format_text(scores, verbose=True)
        assert "DROP TABLE" in out
        assert "Irreversible" in out


# ─────────────────────────────────────────────
# format_json
# ─────────────────────────────────────────────

class TestFormatJson:
    def _scores(self):
        return score_migrations([
            {"filename": "V1.sql", "sql": "CREATE TABLE t (id NUMBER);"},
            {"filename": "V2.sql", "sql": "DROP TABLE t;"},
        ])

    def test_top_level_keys(self):
        data = json.loads(format_json(self._scores()))
        assert set(data.keys()) == {"migrations", "summary"}

    def test_total_count(self):
        data = json.loads(format_json(self._scores()))
        assert data["summary"]["total"] == 2

    def test_by_level_present(self):
        data = json.loads(format_json(self._scores()))
        assert "by_level" in data["summary"]
        assert data["summary"]["by_level"]["DANGEROUS"] == 1

    def test_requires_approval_count(self):
        data = json.loads(format_json(self._scores()))
        assert data["summary"]["requires_approval"] == 1

    def test_migration_fields(self):
        data = json.loads(format_json(self._scores()))
        m = data["migrations"][0]
        assert "filename" in m
        assert "overall_level" in m
        assert "requires_approval" in m
        assert "statements" in m

    def test_empty_list(self):
        data = json.loads(format_json([]))
        assert data["summary"]["total"] == 0
        assert data["migrations"] == []
