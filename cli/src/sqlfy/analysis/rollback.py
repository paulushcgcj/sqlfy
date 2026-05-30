"""
sqlfy.analysis.rollback
=======================
Migration rollback feasibility analysis.

Analyzes each migration to determine if it can be safely rolled back:
- Reversible: Can be undone without data loss
- Partially reversible: Can be undone with caveats
- Irreversible: Cannot be undone

Provides:
- Rollback difficulty score (0-100)
- Suggested rollback script (reverse migration)
- Warnings about data loss and risks
"""

from __future__ import annotations

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal

import sqlglot
import sqlglot.expressions as exp

# Suppress sqlglot warnings
import logging
logging.getLogger("sqlglot").setLevel(logging.CRITICAL)


# ─────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────

@dataclass
class RollbackAnalysis:
    """Rollback feasibility analysis for a single migration."""
    migration: str
    feasibility: Literal["reversible", "partial", "irreversible"]
    score: int  # 0-100
    rollback_script: str | None
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    operations: list[str] = field(default_factory=list)  # List of detected operations
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'migration': self.migration,
            'feasibility': self.feasibility,
            'score': self.score,
            'rollback_script': self.rollback_script,
            'warnings': self.warnings,
            'recommendations': self.recommendations,
            'operations': self.operations,
        }


# ─────────────────────────────────────────────
# ROLLBACK ANALYSIS ENGINE
# ─────────────────────────────────────────────

def analyze_rollback_feasibility(filename: str, content: str) -> RollbackAnalysis:
    """
    Analyze if a migration can be rolled back.
    
    Args:
        filename: Migration filename (e.g., V1__create_users.sql)
        content: SQL content of the migration
    
    Returns:
        RollbackAnalysis with feasibility, score, rollback script, warnings
    """
    reverse_ops = []
    warnings = []
    operations = []
    is_irreversible = False
    partial_score_penalty = 0
    
    try:
        statements = sqlglot.parse(content, dialect='oracle')
        
        for stmt in statements:
            if isinstance(stmt, exp.Create):
                # CREATE TABLE / CREATE VIEW / CREATE INDEX
                table_name = _extract_table_name(stmt.this)
                
                if stmt.kind == 'TABLE':
                    operations.append(f"CREATE TABLE {table_name}")
                    reverse_ops.append(f"DROP TABLE {table_name} CASCADE CONSTRAINTS;")
                    warnings.append(f"Rollback will drop table {table_name} - all data will be lost")
                    partial_score_penalty += 10
                
                elif stmt.kind == 'VIEW':
                    operations.append(f"CREATE VIEW {table_name}")
                    reverse_ops.append(f"DROP VIEW {table_name};")
                    # Views are safe to drop/recreate
                
                elif stmt.kind == 'INDEX':
                    operations.append(f"CREATE INDEX {table_name}")
                    reverse_ops.append(f"DROP INDEX {table_name};")
                    warnings.append(f"Rollback will drop index {table_name} - queries may be slower")
                    partial_score_penalty += 5
                
                elif stmt.kind == 'SEQUENCE':
                    operations.append(f"CREATE SEQUENCE {table_name}")
                    reverse_ops.append(f"DROP SEQUENCE {table_name};")
                    warnings.append(f"Rollback will drop sequence {table_name} - ID generation will reset")
                    partial_score_penalty += 10
            
            elif isinstance(stmt, exp.Alter):
                # ALTER TABLE operations
                table_name = _extract_table_name(stmt.this)
                
                for action in stmt.expressions:
                    if isinstance(action, exp.ColumnDef):
                        # ADD COLUMN
                        col_name = action.name if hasattr(action, 'name') else str(action.this)
                        operations.append(f"ALTER TABLE {table_name} ADD COLUMN {col_name}")
                        reverse_ops.append(f"ALTER TABLE {table_name} DROP COLUMN {col_name};")
                        warnings.append(f"Rollback will drop column {table_name}.{col_name} - data will be lost")
                        partial_score_penalty += 15
                    
                    elif isinstance(action, exp.Drop) and isinstance(action.this, exp.Column):
                        # DROP COLUMN
                        col_name = str(action.this.this)
                        operations.append(f"ALTER TABLE {table_name} DROP COLUMN {col_name}")
                        is_irreversible = True
                        warnings.append(f"Cannot restore dropped column {table_name}.{col_name} without backup")
                    
                    elif isinstance(action, exp.ForeignKey):
                        # ADD CONSTRAINT (FK)
                        fk_name = action.args.get('constraint', {}).name if hasattr(action.args.get('constraint', {}), 'name') else 'FK'
                        operations.append(f"ALTER TABLE {table_name} ADD FOREIGN KEY")
                        reverse_ops.append(f"ALTER TABLE {table_name} DROP CONSTRAINT {fk_name};")
                        # FKs are safe to drop/recreate
                    
                    elif isinstance(action, exp.UniqueColumnConstraint):
                        # ADD UNIQUE CONSTRAINT
                        operations.append(f"ALTER TABLE {table_name} ADD UNIQUE")
                        reverse_ops.append(f"ALTER TABLE {table_name} DROP CONSTRAINT constraint_name;")
                        warnings.append(f"Rollback constraint name must be specified manually")
                        partial_score_penalty += 5
            
            elif isinstance(stmt, exp.Drop):
                # DROP TABLE / DROP VIEW / DROP INDEX
                table_name = _extract_table_name(stmt.this)
                
                if stmt.kind == 'TABLE':
                    operations.append(f"DROP TABLE {table_name}")
                    is_irreversible = True
                    warnings.append(f"Cannot restore table {table_name} without full backup and schema definition")
                
                elif stmt.kind == 'VIEW':
                    operations.append(f"DROP VIEW {table_name}")
                    is_irreversible = True
                    warnings.append(f"Cannot restore view {table_name} without original CREATE VIEW statement")
                
                elif stmt.kind == 'INDEX':
                    operations.append(f"DROP INDEX {table_name}")
                    is_irreversible = True
                    warnings.append(f"Cannot restore index {table_name} without original CREATE INDEX statement")
                
                elif stmt.kind == 'SEQUENCE':
                    operations.append(f"DROP SEQUENCE {table_name}")
                    is_irreversible = True
                    warnings.append(f"Cannot restore sequence {table_name} without knowing original start value")
            
            elif isinstance(stmt, exp.Insert):
                # INSERT statements
                operations.append("INSERT data")
                is_irreversible = True
                warnings.append("Cannot undo INSERT without knowing exact rows inserted")
            
            elif isinstance(stmt, exp.Update):
                # UPDATE statements
                operations.append("UPDATE data")
                is_irreversible = True
                warnings.append("Cannot undo UPDATE without knowing original values")
            
            elif isinstance(stmt, exp.Delete):
                # DELETE statements
                operations.append("DELETE data")
                is_irreversible = True
                warnings.append("Cannot undo DELETE - data is permanently lost")
            
            elif isinstance(stmt, exp.TruncateTable):
                # TRUNCATE statements
                operations.append("TRUNCATE table")
                is_irreversible = True
                warnings.append("Cannot undo TRUNCATE - all data is permanently lost")
            
            # Check for MODIFY operations via regex (sqlglot may not parse them)
            if 'MODIFY' in content.upper():
                modify_matches = re.findall(r'ALTER\s+TABLE\s+(\w+)\s+MODIFY', content, re.IGNORECASE)
                for table in modify_matches:
                    operations.append(f"ALTER TABLE {table} MODIFY columns")
                    is_irreversible = True
                    warnings.append(f"Cannot undo MODIFY on {table} without knowing original column definitions")
    
    except Exception as e:
        # Fallback to regex if sqlglot fails
        pass  # Will be handled below
    
    # Always check for DML operations that sqlglot might miss (especially in mixed DDL/DML scripts)
    if re.search(r'\bDELETE\s+FROM\b', content, re.IGNORECASE):
        if "DELETE data" not in operations:
            operations.append("DELETE data")
        is_irreversible = True
        if "Cannot undo DELETE" not in ' '.join(warnings):
            warnings.append("Cannot undo DELETE - data is permanently lost")
    
    if re.search(r'\bUPDATE\s+\w+\s+SET\b', content, re.IGNORECASE):
        if "UPDATE data" not in operations:
            operations.append("UPDATE data")
        is_irreversible = True
        if "Cannot undo UPDATE" not in ' '.join(warnings):
            warnings.append("Cannot undo UPDATE without knowing original values")
    
    if re.search(r'\bINSERT\s+INTO\b', content, re.IGNORECASE):
        if "INSERT data" not in operations:
            operations.append("INSERT data")
        is_irreversible = True
        if "Cannot undo INSERT" not in ' '.join(warnings):
            warnings.append("Cannot undo INSERT without knowing exact rows inserted")
    
    if re.search(r'\bTRUNCATE\s+TABLE\b', content, re.IGNORECASE):
        if "TRUNCATE table" not in operations:
            operations.append("TRUNCATE table")
        is_irreversible = True
        if "Cannot undo TRUNCATE" not in ' '.join(warnings):
            warnings.append("Cannot undo TRUNCATE - all data is permanently lost")
    
    # If no operations detected via sqlglot, try regex fallback for DDL
    if not operations:
        operations, reverse_ops, warnings, is_irreversible, partial_score_penalty = _analyze_with_regex(content)
    
    # Calculate feasibility and score
    if is_irreversible:
        feasibility = "irreversible"
        score = 0
    elif warnings or partial_score_penalty > 0:
        feasibility = "partial"
        # Start at 100, subtract penalties (min 20)
        score = max(20, 100 - partial_score_penalty)
    else:
        feasibility = "reversible"
        score = 95
    
    # Generate rollback script
    rollback_script = "\n".join(reverse_ops) if reverse_ops and not is_irreversible else None
    
    # Generate recommendations
    recommendations = _generate_recommendations(feasibility, warnings)
    
    return RollbackAnalysis(
        migration=filename,
        feasibility=feasibility,
        score=score,
        rollback_script=rollback_script,
        warnings=warnings,
        recommendations=recommendations,
        operations=operations,
    )


def _extract_table_name(node) -> str:
    """Extract table name from AST node."""
    if not node:
        return "UNKNOWN"
    
    # Try various levels of nesting
    current = node
    for _ in range(5):
        if hasattr(current, 'name'):
            name = current.name if isinstance(current.name, str) else str(current.name)
            if name and name != '':
                return name.upper()
        if hasattr(current, 'this'):
            current = current.this
        else:
            break
    
    return "UNKNOWN"


def _analyze_with_regex(content: str) -> tuple[list[str], list[str], list[str], bool, int]:
    """
    Fallback regex-based analysis when sqlglot fails.
    
    Returns:
        (operations, reverse_ops, warnings, is_irreversible, partial_score_penalty)
    """
    operations = []
    reverse_ops = []
    warnings = []
    is_irreversible = False
    partial_score_penalty = 0
    
    # CREATE TABLE
    for match in re.finditer(r'CREATE\s+TABLE\s+(\w+)', content, re.IGNORECASE):
        table = match.group(1).upper()
        operations.append(f"CREATE TABLE {table}")
        reverse_ops.append(f"DROP TABLE {table} CASCADE CONSTRAINTS;")
        warnings.append(f"Rollback will drop table {table} - all data will be lost")
        partial_score_penalty += 10
    
    # DROP TABLE
    for match in re.finditer(r'DROP\s+TABLE\s+(\w+)', content, re.IGNORECASE):
        table = match.group(1).upper()
        operations.append(f"DROP TABLE {table}")
        is_irreversible = True
        warnings.append(f"Cannot restore table {table} without full backup")
    
    # DROP VIEW
    for match in re.finditer(r'DROP\s+VIEW\s+(\w+)', content, re.IGNORECASE):
        view = match.group(1).upper()
        operations.append(f"DROP VIEW {view}")
        is_irreversible = True
        warnings.append(f"Cannot restore view {view} without original CREATE VIEW statement")
    
    # DROP INDEX
    for match in re.finditer(r'DROP\s+INDEX\s+(\w+)', content, re.IGNORECASE):
        index = match.group(1).upper()
        operations.append(f"DROP INDEX {index}")
        is_irreversible = True
        warnings.append(f"Cannot restore index {index} without original CREATE INDEX statement")
    
    # DROP SEQUENCE
    for match in re.finditer(r'DROP\s+SEQUENCE\s+(\w+)', content, re.IGNORECASE):
        seq = match.group(1).upper()
        operations.append(f"DROP SEQUENCE {seq}")
        is_irreversible = True
        warnings.append(f"Cannot restore sequence {seq} without knowing original start value")
    
    # ADD COLUMN
    for match in re.finditer(r'ALTER\s+TABLE\s+(\w+)\s+ADD\s+(?:COLUMN\s+)?(\w+)', content, re.IGNORECASE):
        table, col = match.group(1).upper(), match.group(2).upper()
        operations.append(f"ALTER TABLE {table} ADD COLUMN {col}")
        reverse_ops.append(f"ALTER TABLE {table} DROP COLUMN {col};")
        warnings.append(f"Rollback will drop column {table}.{col} - data will be lost")
        partial_score_penalty += 15
    
    # DROP COLUMN
    for match in re.finditer(r'ALTER\s+TABLE\s+(\w+)\s+DROP\s+COLUMN\s+(\w+)', content, re.IGNORECASE):
        table, col = match.group(1).upper(), match.group(2).upper()
        operations.append(f"ALTER TABLE {table} DROP COLUMN {col}")
        is_irreversible = True
        warnings.append(f"Cannot restore column {table}.{col} without backup")
    
    # MODIFY
    for match in re.finditer(r'ALTER\s+TABLE\s+(\w+)\s+MODIFY', content, re.IGNORECASE):
        table = match.group(1).upper()
        operations.append(f"ALTER TABLE {table} MODIFY columns")
        is_irreversible = True
        warnings.append(f"Cannot undo MODIFY on {table} without knowing original column definitions")
    
    # DELETE
    if re.search(r'\bDELETE\s+FROM\b', content, re.IGNORECASE):
        operations.append("DELETE data")
        is_irreversible = True
        warnings.append("Cannot undo DELETE - data is permanently lost")
    
    # UPDATE
    if re.search(r'\bUPDATE\s+\w+\s+SET\b', content, re.IGNORECASE):
        operations.append("UPDATE data")
        is_irreversible = True
        warnings.append("Cannot undo UPDATE without knowing original values")
    
    # INSERT
    if re.search(r'\bINSERT\s+INTO\b', content, re.IGNORECASE):
        operations.append("INSERT data")
        is_irreversible = True
        warnings.append("Cannot undo INSERT without knowing exact rows inserted")
    
    # TRUNCATE
    if re.search(r'\bTRUNCATE\s+TABLE\b', content, re.IGNORECASE):
        operations.append("TRUNCATE table")
        is_irreversible = True
        warnings.append("Cannot undo TRUNCATE - all data is permanently lost")
    
    return operations, reverse_ops, warnings, is_irreversible, partial_score_penalty


def _generate_recommendations(feasibility: str, warnings: list[str]) -> list[str]:
    """Generate recommendations based on feasibility analysis."""
    recommendations = []
    
    if feasibility == "irreversible":
        recommendations.append("⚠️  Keep full database backup before applying this migration")
        recommendations.append("Consider point-in-time recovery (PITR) capability")
        recommendations.append("Document data preservation requirements")
    elif feasibility == "partial":
        recommendations.append("Test rollback script on staging environment first")
        recommendations.append("Document manual steps required for complete rollback")
        if any("data will be lost" in w for w in warnings):
            recommendations.append("Consider backing up affected tables before migration")
    else:
        recommendations.append("✓ Rollback script can be safely applied")
        recommendations.append("Still recommended to test on staging first")
    
    return recommendations


# ─────────────────────────────────────────────
# BATCH ANALYSIS
# ─────────────────────────────────────────────

def analyze_migrations(files: list[dict]) -> list[RollbackAnalysis]:
    """
    Analyze rollback feasibility for multiple migrations.
    
    Args:
        files: List of {filename, sql} dicts
    
    Returns:
        List of RollbackAnalysis results
    """
    results = []
    for file_data in files:
        analysis = analyze_rollback_feasibility(file_data['filename'], file_data['sql'])
        results.append(analysis)
    return results


# ─────────────────────────────────────────────
# OUTPUT FORMATTERS
# ─────────────────────────────────────────────

def format_rollback_text(results: list[RollbackAnalysis]) -> str:
    """Format rollback analysis as human-readable text."""
    lines = ['Rollback Feasibility Analysis', '=' * 80, '']
    
    # Summary statistics
    reversible = sum(1 for r in results if r.feasibility == 'reversible')
    partial = sum(1 for r in results if r.feasibility == 'partial')
    irreversible = sum(1 for r in results if r.feasibility == 'irreversible')
    
    lines.append(f'Total migrations: {len(results)}')
    lines.append(f'  ✓ Reversible: {reversible}')
    lines.append(f'  ⚠  Partially reversible: {partial}')
    lines.append(f'  ✗ Irreversible: {irreversible}')
    lines.append('')
    lines.append('=' * 80)
    lines.append('')
    
    # Individual analyses
    for result in results:
        # Header with status emoji
        if result.feasibility == 'reversible':
            status = f'✅ REVERSIBLE (Score: {result.score}/100)'
        elif result.feasibility == 'partial':
            status = f'⚠️  PARTIALLY REVERSIBLE (Score: {result.score}/100)'
        else:
            status = f'❌ IRREVERSIBLE (Score: {result.score}/100)'
        
        lines.append(f'{result.migration}')
        lines.append(f'  {status}')
        lines.append('')
        
        # Operations detected
        if result.operations:
            lines.append('  Operations:')
            for op in result.operations:
                lines.append(f'    • {op}')
            lines.append('')
        
        # Rollback script
        if result.rollback_script:
            lines.append('  Rollback script:')
            for line in result.rollback_script.split('\n'):
                lines.append(f'    {line}')
            lines.append('')
        else:
            lines.append('  ⚠️  No automatic rollback script available')
            lines.append('')
        
        # Warnings
        if result.warnings:
            lines.append('  Warnings:')
            for warning in result.warnings:
                lines.append(f'    ⚠️  {warning}')
            lines.append('')
        
        # Recommendations
        if result.recommendations:
            lines.append('  Recommendations:')
            for rec in result.recommendations:
                lines.append(f'    → {rec}')
            lines.append('')
        
        lines.append('-' * 80)
        lines.append('')
    
    return '\n'.join(lines)


def format_rollback_json(results: list[RollbackAnalysis]) -> str:
    """Format rollback analysis as JSON."""
    from ..models import (
        RollbackResult as _RollbackResult,
        RollbackAnalysis as _RollbackAnalysis,
        Summary as _Summary,
        Feasibility as _Feasibility,
    )
    reversible = sum(1 for r in results if r.feasibility == 'reversible')
    partial = sum(1 for r in results if r.feasibility == 'partial')
    irreversible = sum(1 for r in results if r.feasibility == 'irreversible')
    model = _RollbackResult(
        summary=_Summary(
            total=len(results),
            reversible=reversible,
            partial=partial,
            irreversible=irreversible,
        ),
        migrations=[
            _RollbackAnalysis(
                migration=r.migration,
                feasibility=_Feasibility(r.feasibility),
                score=r.score,
                rollback_script=r.rollback_script,
                warnings=r.warnings,
                recommendations=r.recommendations,
                operations=r.operations,
            )
            for r in results
        ],
    )
    return model.model_dump_json(by_alias=True, indent=2)
