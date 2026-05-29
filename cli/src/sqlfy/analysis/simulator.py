"""
Schema evolution simulator for testing hypothetical migrations.

Provides sandbox mode for testing DDL changes before committing:
- Apply what-if migrations on top of existing state
- Compare simulated state vs actual state
- Test migration impact without modifying files
- Validate DDL syntax and schema changes

Example:
    simulator = SchemaSimulator(base_files, base_version='3')
    result = simulator.simulate_sql("ALTER TABLE users ADD (status VARCHAR2(20));")
    
    if result.is_safe():
        print("Safe to apply!")
    else:
        print(f"Errors: {result.errors}")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..domain.schema_state import SchemaState, SchemaStateBuilder
from ..reconstructor import Reconstructor, reconstruct, reconstruct_at
from .differ import SchemaDiffer, DiffResult
from .insights import InsightsEngine, InsightsReport


@dataclass
class SimulationResult:
    """Result of a schema evolution simulation."""
    
    base_version: str
    base_state: SchemaState
    simulated_state: SchemaState
    diff: DiffResult
    insights: InsightsReport
    health_score: int
    health_grade: str
    
    sql: str
    success: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def is_safe(self) -> bool:
        """Check if simulation is safe (no errors, no breaking changes)."""
        has_errors = len(self.errors) > 0 or len(self.insights.errors()) > 0
        return self.success and not has_errors and not self.diff.is_breaking()
    
    def is_breaking(self) -> bool:
        """Check if simulation introduces breaking changes."""
        return self.diff.is_breaking()
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = []
        
        if self.success:
            lines.append("✅ Simulation successful")
        else:
            lines.append("❌ Simulation failed")
        
        # Schema changes
        stats = self.diff.stats()
        if stats['tables_added'] > 0:
            lines.append(f"  • {stats['tables_added']} table(s) added")
        if stats['tables_modified'] > 0:
            lines.append(f"  • {stats['tables_modified']} table(s) modified")
        if stats['tables_removed'] > 0:
            lines.append(f"  • {stats['tables_removed']} table(s) removed")
        
        # Health
        lines.append(f"  • Health score: {self.health_score}/100 ({self.health_grade})")
        
        # Errors/warnings
        if self.errors:
            lines.append(f"  • {len(self.errors)} error(s)")
        if self.warnings:
            lines.append(f"  • {len(self.warnings)} warning(s)")
        
        return "\n".join(lines)
    
    def to_text(self) -> str:
        """Generate formatted text report."""
        lines = []
        
        # Header
        lines.append("╔══════════════════════════════════════════════════════════╗")
        lines.append("║         Schema Evolution Simulation                      ║")
        lines.append("╚══════════════════════════════════════════════════════════╝")
        lines.append("")
        lines.append(f"📦 Base State: V{self.base_version}")
        lines.append(f"🧪 Simulated SQL: {self.sql[:100]}{'...' if len(self.sql) > 100 else ''}")
        lines.append("")
        
        # Status
        lines.append("━" * 60)
        if self.success:
            lines.append("✅ SIMULATION SUCCESSFUL")
        else:
            lines.append("❌ SIMULATION FAILED")
        lines.append("━" * 60)
        lines.append("")
        
        # Errors
        if self.errors:
            lines.append("Errors:")
            for err in self.errors:
                lines.append(f"  • {err}")
            lines.append("")
        
        # Schema Changes
        stats = self.diff.stats()
        has_changes = (stats['tables_added'] > 0 or stats['tables_removed'] > 0 or 
                       stats['tables_modified'] > 0)
        if has_changes:
            lines.append("Schema Changes:")
            diff_text = self.diff.to_text()
            for line in diff_text.split('\n')[:20]:  # Limit to first 20 lines
                if line.strip():
                    lines.append(f"  {line}")
            lines.append("")
        
        # Impact Analysis (if breaking)
        if self.is_breaking():
            lines.append("⚠️  Breaking Changes Detected:")
            lines.append("  This migration may cause issues in production.")
            lines.append("")
        
        # Health Score
        lines.append(f"Health Score: {self.health_score}/100 ({self.health_grade})")
        if len(self.insights.errors()) > 0:
            lines.append(f"  • {len(self.insights.errors())} error(s)")
        if len(self.insights.warnings()) > 0:
            lines.append(f"  • {len(self.insights.warnings())} warning(s)")
        lines.append("")
        
        # Recommendation
        if self.is_safe():
            lines.append("✅ Recommendation: Safe to apply.")
        elif self.is_breaking():
            lines.append("⚠️  Recommendation: Review breaking changes before applying.")
        else:
            lines.append("❌ Recommendation: Fix errors before applying.")
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """Generate JSON report."""
        from ..models import (
            SimulateResult as _SimulateResult,
            SimulateDiff as _SimulateDiff,
            SimulateHealth as _SimulateHealth,
            DiffStats as _DiffStats,
        )
        diff_stats = self.diff.stats()
        model = _SimulateResult(
            timestamp=self.timestamp,
            base_version=self.base_version,
            sql=self.sql,
            success=self.success,
            is_safe=self.is_safe(),
            is_breaking=self.is_breaking(),
            errors=self.errors,
            warnings=self.warnings,
            diff=_SimulateDiff(
                stats=_DiffStats(
                    tables_added=diff_stats['tables_added'],
                    tables_removed=diff_stats['tables_removed'],
                    tables_modified=diff_stats['tables_modified'],
                    columns_added=diff_stats['columns_added'],
                    columns_removed=diff_stats['columns_removed'],
                    columns_modified=diff_stats['columns_modified'],
                    sequences_added=diff_stats['sequences_added'],
                    sequences_removed=diff_stats['sequences_removed'],
                    relationships_added=diff_stats['relationships_added'],
                    relationships_removed=diff_stats['relationships_removed'],
                    is_breaking=diff_stats['is_breaking'],
                ),
                is_breaking=self.diff.is_breaking(),
            ),
            health=_SimulateHealth(
                score=self.health_score,
                grade=self.health_grade,
                errors=len(self.insights.errors()),
                warnings=len(self.insights.warnings()),
            ),
        )
        return model.model_dump_json(by_alias=True, indent=2)


class SchemaSimulator:
    """Schema evolution simulator for testing hypothetical migrations."""
    
    def __init__(self, base_files: list[dict], base_version: Optional[str] = None, 
                 dialect: str = 'oracle'):
        """
        Initialize simulator with base migration files.
        
        Args:
            base_files: List of migration file dicts with 'filename' and 'sql'
            base_version: Version to simulate from (default: latest)
            dialect: SQL dialect (default: 'oracle')
        """
        self.base_files = base_files
        self.base_version = base_version
        self.dialect = dialect
        
        # Reconstruct base state
        if base_version:
            self.base_graph = reconstruct_at(base_files, base_version, dialect)
        else:
            self.base_graph = reconstruct(base_files, dialect)
            # Extract version from last file
            if base_files:
                from ..core import parse_flyway_ver
                last_file = sorted(base_files, key=lambda f: parse_flyway_ver(f['filename'])['order'])[-1]
                self.base_version = parse_flyway_ver(last_file['filename'])['version']
            else:
                self.base_version = '0'
        
        self.base_state = SchemaStateBuilder.from_graph(self.base_graph, source_files=base_files)
    
    def simulate_sql(self, sql: str) -> SimulationResult:
        """
        Simulate applying SQL on top of base state.
        
        Args:
            sql: SQL DDL statement(s) to simulate
        
        Returns:
            Simulation result with diff, insights, and safety assessment
        """
        errors = []
        warnings = []
        
        try:
            # Create reconstructor with base state
            reconstructor = Reconstructor(dialect=self.dialect)
            
            # Apply base migrations
            if self.base_version and self.base_version != '0':
                reconstructor.apply_up_to(self.base_files, self.base_version)
            elif self.base_files:
                reconstructor.apply_all(self.base_files)
            
            # Simulate hypothetical migration
            # Compute a next version that handles both integer and dotted semantic versions.
            try:
                next_version = str(int(self.base_version) + 1)
            except (ValueError, TypeError):
                # Fallback: if dotted (e.g. 1.0.2) increment the last numeric element
                if isinstance(self.base_version, str) and '.' in self.base_version:
                    parts = self.base_version.split('.')
                    try:
                        parts[-1] = str(int(parts[-1]) + 1)
                        next_version = '.'.join(parts)
                    except ValueError:
                        # As a last resort, append .1
                        next_version = f"{self.base_version}.1"
                else:
                    # Unknown format — just append .1
                    next_version = f"{self.base_version}.1"

            sim_filename = f"V{next_version}__simulated.sql"
            result = reconstructor.apply_file(sim_filename, sql)
            
            # Check for errors
            if result.errors:
                errors.extend(result.errors)
            
            # Get simulated graph
            sim_graph = reconstructor.snapshot()
            sim_state = SchemaStateBuilder.from_graph(
                sim_graph, 
                source_files=self.base_files + [{'filename': sim_filename, 'sql': sql}]
            )
            
            # Run diff
            diff = SchemaDiffer.diff(self.base_state, sim_state)
            
            # Run insights on simulated state
            insights = InsightsEngine.analyse(sim_state)
            
            # Calculate health score (simplified - just use error/warning counts)
            health_score = 100
            health_score -= len(insights.errors()) * 20
            health_score -= len(insights.warnings()) * 5
            health_score = max(0, health_score)
            
            if health_score >= 90:
                health_grade = 'excellent'
            elif health_score >= 75:
                health_grade = 'good'
            elif health_score >= 50:
                health_grade = 'warning'
            else:
                health_grade = 'critical'
            
            # Collect warnings from insights
            for finding in insights.warnings():
                warnings.append(f"{finding.code}: {finding.message}")
            
            success = len(errors) == 0
            
        except Exception as exc:
            errors.append(f"Simulation failed: {exc}")
            success = False
            
            # Return failed result
            return SimulationResult(
                base_version=self.base_version,
                base_state=self.base_state,
                simulated_state=self.base_state,  # Unchanged
                diff=SchemaDiffer.diff(self.base_state, self.base_state),  # Empty diff
                insights=InsightsEngine.analyse(self.base_state),
                health_score=0,
                health_grade='critical',
                sql=sql,
                success=False,
                errors=errors,
                warnings=warnings,
            )
        
        return SimulationResult(
            base_version=self.base_version,
            base_state=self.base_state,
            simulated_state=sim_state,
            diff=diff,
            insights=insights,
            health_score=health_score,
            health_grade=health_grade,
            sql=sql,
            success=success,
            errors=errors,
            warnings=warnings,
        )
    
    def simulate_file(self, filepath: str) -> SimulationResult:
        """
        Simulate applying SQL from a file.
        
        Args:
            filepath: Path to SQL file
        
        Returns:
            Simulation result
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            sql = f.read()
        return self.simulate_sql(sql)
    
    def compare_with_actual(self, target_version: str) -> DiffResult:
        """
        Compare simulated state with actual state at target version.
        
        Args:
            target_version: Version to compare against
        
        Returns:
            Diff result showing differences
        """
        # Reconstruct actual state at target version
        actual_graph = reconstruct_at(self.base_files, target_version, self.dialect)
        actual_state = SchemaStateBuilder.from_graph(actual_graph, source_files=self.base_files)
        
        # Compare with base state
        return SchemaDiffer.diff(self.base_state, actual_state)
