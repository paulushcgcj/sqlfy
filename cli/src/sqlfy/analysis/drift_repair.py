"""
sqlfy.analysis.drift_repair
============================
Schema drift detection and auto-repair SQL generation.

Compares two schema states and generates SQL to reconcile differences.
Useful for:
- Comparing dev vs production migration folders
- Generating catch-up migrations
- Detecting manual schema changes
- Reconciling divergent branches

Usage
-----
    from sqlfy.reconstructor import reconstruct
    from sqlfy.analysis.drift_repair import analyze_drift, generate_repair_migration
    
    # Load two schemas
    base_graph = reconstruct(base_files)
    target_graph = reconstruct(target_files)
    
    # Analyze drift
    report = analyze_drift(base_graph, target_graph)
    
    # Generate repair SQL
    if not report.is_clean:
        migration_sql = generate_repair_migration(report, version='10')
        print(migration_sql)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ..domain.models import SchemaGraph, Table, Column
from ..domain.schema_state import SchemaStateBuilder, SchemaState


DriftCategory = Literal[
    'missing_table', 'extra_table',
    'missing_column', 'extra_column',
    'type_mismatch', 'nullability_mismatch',
    'missing_constraint', 'extra_constraint',
    'missing_index', 'extra_index',
]

DriftSeverity = Literal['error', 'warning', 'info']


@dataclass
class DriftFinding:
    """Single drift detection finding."""
    
    category: DriftCategory
    """Type of drift detected."""
    
    severity: DriftSeverity
    """Impact level: error (breaking), warning (data-safe), info (optional)."""
    
    object_name: str
    """Fully qualified name of the affected object."""
    
    description: str
    """Human-readable description of the drift."""
    
    expected: str | None = None
    """Expected state from base schema."""
    
    actual: str | None = None
    """Actual state from target schema."""
    
    repair_sql: str = ""
    """SQL statement(s) to fix the drift."""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'category': self.category,
            'severity': self.severity,
            'object_name': self.object_name,
            'description': self.description,
            'expected': self.expected,
            'actual': self.actual,
            'repair_sql': self.repair_sql,
        }


@dataclass
class DriftReport:
    """Complete drift analysis report."""
    
    findings: list[DriftFinding] = field(default_factory=list)
    """All detected drift findings."""
    
    base_label: str = "Base"
    """Label for base schema (e.g., 'Production', 'V5')."""
    
    target_label: str = "Target"
    """Label for target schema (e.g., 'Development', 'V10')."""
    
    @property
    def total_drift_count(self) -> int:
        """Total number of drift findings."""
        return len(self.findings)
    
    @property
    def by_category(self) -> dict[str, int]:
        """Count findings by category."""
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.category] = counts.get(finding.category, 0) + 1
        return counts
    
    @property
    def by_severity(self) -> dict[str, int]:
        """Count findings by severity."""
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts
    
    @property
    def is_clean(self) -> bool:
        """True if no drift detected."""
        return len(self.findings) == 0
    
    def errors(self) -> list[DriftFinding]:
        """Get error-level findings."""
        return [f for f in self.findings if f.severity == 'error']
    
    def warnings(self) -> list[DriftFinding]:
        """Get warning-level findings."""
        return [f for f in self.findings if f.severity == 'warning']
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'status': 'clean' if self.is_clean else 'drift_detected',
            'base_label': self.base_label,
            'target_label': self.target_label,
            'total_findings': self.total_drift_count,
            'by_category': self.by_category,
            'by_severity': self.by_severity,
            'findings': [f.to_dict() for f in self.findings],
        }
    
    def to_json(self) -> str:
        """Format as JSON."""
        import json
        return json.dumps(self.to_dict(), indent=2)
    
    def to_text(self) -> str:
        """Format as human-readable text."""
        lines = [
            "Schema Drift Report",
            "=" * 60,
            "",
            f"Base:   {self.base_label}",
            f"Target: {self.target_label}",
            "",
        ]
        
        if self.is_clean:
            lines.append("✓ No drift detected — schemas are identical")
            return "\n".join(lines)
        
        lines.append(f"Status: DRIFT DETECTED")
        lines.append(f"Total findings: {self.total_drift_count}")
        lines.append("")
        
        if self.by_category:
            lines.append("By Category:")
            for cat, count in sorted(self.by_category.items()):
                lines.append(f"  {cat:<25} : {count}")
            lines.append("")
        
        if self.by_severity:
            lines.append("By Severity:")
            for sev, count in sorted(self.by_severity.items()):
                lines.append(f"  {sev:<10} : {count}")
            lines.append("")
        
        lines.append("─" * 60)
        lines.append("")
        
        # Group findings by category
        by_cat: dict[str, list[DriftFinding]] = {}
        for finding in self.findings:
            if finding.category not in by_cat:
                by_cat[finding.category] = []
            by_cat[finding.category].append(finding)
        
        # Display findings by category
        for category, findings in sorted(by_cat.items()):
            cat_label = category.replace('_', ' ').upper()
            lines.append(f"{cat_label} ({len(findings)})")
            lines.append("")
            
            for finding in findings:
                severity_badge = {
                    'error': '[ERROR]',
                    'warning': '[WARN]',
                    'info': '[INFO]',
                }[finding.severity]
                
                lines.append(f"  {severity_badge} {finding.object_name}")
                lines.append(f"    {finding.description}")
                
                if finding.expected:
                    lines.append(f"    Expected: {finding.expected}")
                if finding.actual:
                    lines.append(f"    Actual:   {finding.actual}")
                
                if finding.repair_sql:
                    lines.append(f"")
                    lines.append(f"    Repair SQL:")
                    for sql_line in finding.repair_sql.strip().split('\n'):
                        lines.append(f"      {sql_line}")
                
                lines.append("")
            
            lines.append("")
        
        lines.append("─" * 60)
        lines.append("")
        lines.append("Recommendation:")
        lines.append("  Use --generate-migration to create catch-up migration file")
        
        return "\n".join(lines)


def analyze_drift(
    base_graph: SchemaGraph,
    target_graph: SchemaGraph,
    base_label: str = "Base",
    target_label: str = "Target",
) -> DriftReport:
    """
    Compare two schema graphs and detect drift.
    
    Args:
        base_graph: Base schema (e.g., production migrations)
        target_graph: Target schema (e.g., development migrations)
        base_label: Label for base schema (default: "Base")
        target_label: Label for target schema (default: "Target")
    
    Returns:
        DriftReport with detected differences and repair SQL
    """
    report = DriftReport(base_label=base_label, target_label=target_label)
    
    base_tables = set(base_graph.tables.keys())
    target_tables = set(target_graph.tables.keys())
    
    # Detect missing tables (in base but not in target)
    for table_id in base_tables - target_tables:
        table = base_graph.tables[table_id]
        report.findings.append(DriftFinding(
            category='missing_table',
            severity='error',
            object_name=table.full,
            description=f"Table exists in {base_label} but missing in {target_label}",
            expected=f"Exists (created in V{table.created_in})",
            actual="Does not exist",
            repair_sql=_generate_create_table_sql(table),
        ))
    
    # Detect extra tables (in target but not in base)
    for table_id in target_tables - base_tables:
        table = target_graph.tables[table_id]
        report.findings.append(DriftFinding(
            category='extra_table',
            severity='warning',
            object_name=table.full,
            description=f"Table exists in {target_label} but missing in {base_label}",
            expected="Does not exist",
            actual=f"Exists (created in V{table.created_in})",
            repair_sql=f"DROP TABLE {table.full};",
        ))
    
    # Compare columns for common tables
    for table_id in base_tables & target_tables:
        base_table = base_graph.tables[table_id]
        target_table = target_graph.tables[table_id]
        
        _compare_columns(base_table, target_table, report, base_label, target_label)
        _compare_constraints(base_table, target_table, report, base_label, target_label)
        _compare_indexes(base_table, target_table, report, base_label, target_label)
    
    return report


def _compare_columns(
    base_table: Table,
    target_table: Table,
    report: DriftReport,
    base_label: str,
    target_label: str,
) -> None:
    """Compare columns between two tables."""
    base_cols = {col.name: col for col in base_table.columns}
    target_cols = {col.name: col for col in target_table.columns}
    
    base_col_names = set(base_cols.keys())
    target_col_names = set(target_cols.keys())
    
    # Missing columns
    for col_name in base_col_names - target_col_names:
        col = base_cols[col_name]
        report.findings.append(DriftFinding(
            category='missing_column',
            severity='error',
            object_name=f"{base_table.full}.{col_name}",
            description=f"Column exists in {base_label} but missing in {target_label}",
            expected=_format_column_def(col),
            actual="Does not exist",
            repair_sql=f"ALTER TABLE {base_table.full} ADD {col_name} {_format_column_def(col)};",
        ))
    
    # Extra columns
    for col_name in target_col_names - base_col_names:
        col = target_cols[col_name]
        report.findings.append(DriftFinding(
            category='extra_column',
            severity='warning',
            object_name=f"{target_table.full}.{col_name}",
            description=f"Column exists in {target_label} but missing in {base_label}",
            expected="Does not exist",
            actual=_format_column_def(col),
            repair_sql=f"ALTER TABLE {target_table.full} DROP COLUMN {col_name};",
        ))
    
    # Type/nullability mismatches for common columns
    for col_name in base_col_names & target_col_names:
        base_col = base_cols[col_name]
        target_col = target_cols[col_name]
        
        base_type = _format_type(base_col)
        target_type = _format_type(target_col)
        
        if base_type != target_type:
            report.findings.append(DriftFinding(
                category='type_mismatch',
                severity='error',
                object_name=f"{base_table.full}.{col_name}",
                description=f"Column type differs between {base_label} and {target_label}",
                expected=base_type,
                actual=target_type,
                repair_sql=f"ALTER TABLE {target_table.full} MODIFY ({col_name} {base_type});",
            ))
        
        if base_col.nullable != target_col.nullable:
            report.findings.append(DriftFinding(
                category='nullability_mismatch',
                severity='warning',
                object_name=f"{base_table.full}.{col_name}",
                description=f"Column nullability differs",
                expected="NULLABLE" if base_col.nullable else "NOT NULL",
                actual="NULLABLE" if target_col.nullable else "NOT NULL",
                repair_sql=f"ALTER TABLE {target_table.full} MODIFY ({col_name} {'NULL' if base_col.nullable else 'NOT NULL'});",
            ))


def _compare_constraints(
    base_table: Table,
    target_table: Table,
    report: DriftReport,
    base_label: str,
    target_label: str,
) -> None:
    """Compare constraints between two tables."""
    base_constraints = {(c.type, tuple(c.columns)): c for c in base_table.constraints}
    target_constraints = {(c.type, tuple(c.columns)): c for c in target_table.constraints}
    
    base_keys = set(base_constraints.keys())
    target_keys = set(target_constraints.keys())
    
    # Missing constraints
    for key in base_keys - target_keys:
        constraint = base_constraints[key]
        report.findings.append(DriftFinding(
            category='missing_constraint',
            severity='warning',
            object_name=f"{base_table.full}.{constraint.name or 'unnamed'}",
            description=f"{constraint.type.upper()} constraint missing in {target_label}",
            expected=f"{constraint.type.upper()} ({', '.join(constraint.columns)})",
            actual="Does not exist",
            repair_sql=_generate_add_constraint_sql(base_table.full, constraint),
        ))
    
    # Extra constraints
    for key in target_keys - base_keys:
        constraint = target_constraints[key]
        report.findings.append(DriftFinding(
            category='extra_constraint',
            severity='info',
            object_name=f"{target_table.full}.{constraint.name or 'unnamed'}",
            description=f"{constraint.type.upper()} constraint exists in {target_label} but not in {base_label}",
            expected="Does not exist",
            actual=f"{constraint.type.upper()} ({', '.join(constraint.columns)})",
            repair_sql=f"ALTER TABLE {target_table.full} DROP CONSTRAINT {constraint.name};" if constraint.name else "",
        ))


def _compare_indexes(
    base_table: Table,
    target_table: Table,
    report: DriftReport,
    base_label: str,
    target_label: str,
) -> None:
    """Compare indexes between two tables."""
    base_indexes = {(tuple(idx.columns), idx.unique): idx for idx in base_table.indexes}
    target_indexes = {(tuple(idx.columns), idx.unique): idx for idx in target_table.indexes}
    
    base_keys = set(base_indexes.keys())
    target_keys = set(target_indexes.keys())
    
    # Missing indexes
    for key in base_keys - target_keys:
        idx = base_indexes[key]
        report.findings.append(DriftFinding(
            category='missing_index',
            severity='info',
            object_name=f"{base_table.full}.{idx.name}",
            description=f"Index missing in {target_label}",
            expected=f"{'UNIQUE ' if idx.unique else ''}INDEX ({', '.join(idx.columns)})",
            actual="Does not exist",
            repair_sql=f"CREATE {'UNIQUE ' if idx.unique else ''}INDEX {idx.name} ON {base_table.full} ({', '.join(idx.columns)});",
        ))
    
    # Extra indexes
    for key in target_keys - base_keys:
        idx = target_indexes[key]
        report.findings.append(DriftFinding(
            category='extra_index',
            severity='info',
            object_name=f"{target_table.full}.{idx.name}",
            description=f"Index exists in {target_label} but not in {base_label}",
            expected="Does not exist",
            actual=f"{'UNIQUE ' if idx.unique else ''}INDEX ({', '.join(idx.columns)})",
            repair_sql=f"DROP INDEX {idx.name};",
        ))


def _generate_create_table_sql(table: Table) -> str:
    """Generate CREATE TABLE statement."""
    lines = [f"CREATE TABLE {table.full} ("]
    
    col_defs = []
    for col in table.columns:
        col_defs.append(f"  {col.name} {_format_column_def(col)}")
    
    lines.append(",\n".join(col_defs))
    lines.append(");")
    
    return "\n".join(lines)


def _generate_add_constraint_sql(table_name: str, constraint) -> str:
    """Generate ALTER TABLE ADD CONSTRAINT statement."""
    if constraint.type == 'primary_key':
        return f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint.name} PRIMARY KEY ({', '.join(constraint.columns)});"
    elif constraint.type == 'unique':
        return f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint.name} UNIQUE ({', '.join(constraint.columns)});"
    elif constraint.type == 'foreign_key' and constraint.references:
        ref_table = constraint.references['table']
        ref_cols = ', '.join(constraint.references['columns'])
        on_delete = f" ON DELETE {constraint.references.get('on_delete', '')}" if constraint.references.get('on_delete') else ""
        return f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint.name} FOREIGN KEY ({', '.join(constraint.columns)}) REFERENCES {ref_table} ({ref_cols}){on_delete};"
    else:
        return f"-- Cannot generate constraint: {constraint.type}"


def _format_column_def(col: Column) -> str:
    """Format column definition for DDL."""
    parts = [_format_type(col)]
    
    if col.default:
        parts.append(f"DEFAULT {col.default}")
    
    if not col.nullable:
        parts.append("NOT NULL")
    
    return " ".join(parts)


def _format_type(col: Column) -> str:
    """Format column type with precision/scale."""
    if col.precision is not None:
        if col.scale is not None:
            return f"{col.type}({col.precision},{col.scale})"
        else:
            return f"{col.type}({col.precision})"
    return col.type


def generate_repair_migration(
    report: DriftReport,
    version: str,
    description: str = "catch_up_drift",
) -> str:
    """
    Generate migration file content from drift report.
    
    Args:
        report: Drift analysis report
        version: Migration version number
        description: Migration description
    
    Returns:
        Migration file content (SQL)
    """
    if report.is_clean:
        return f"-- V{version}__{description}.sql\n-- No drift detected - no changes needed\n"
    
    lines = [
        f"-- V{version}__{description}.sql",
        f"-- Auto-generated migration to reconcile drift between {report.base_label} and {report.target_label}",
        f"-- Total findings: {report.total_drift_count}",
        "",
    ]
    
    # Group findings by category
    by_cat: dict[str, list[DriftFinding]] = {}
    for finding in report.findings:
        if finding.category not in by_cat:
            by_cat[finding.category] = []
        by_cat[finding.category].append(finding)
    
    # Generate SQL by category
    for category, findings in sorted(by_cat.items()):
        cat_label = category.replace('_', ' ').title()
        lines.append(f"-- {cat_label} ({len(findings)})")
        lines.append("")
        
        for finding in findings:
            if finding.repair_sql:
                lines.append(f"-- {finding.object_name}: {finding.description}")
                lines.append(finding.repair_sql)
                lines.append("")
    
    return "\n".join(lines)
