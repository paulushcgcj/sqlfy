"""
Migration folder health analysis.

Provides high-level summary of migration folder quality:
- Safe vs unsafe migrations
- Irreversible operations
- Health score calculation
- Migration file status

Example:
    files = load_files('./migrations')
    graph = reconstruct(files)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    insights_report = InsightsEngine.analyse(state)
    
    health_report = HealthAnalyzer.analyze(state, insights_report, './migrations')
    print(health_report.to_text())
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from ..analysis.insights import InsightsReport
from ..domain.schema_state import SchemaState


@dataclass
class MigrationStatus:
    """Status of a single migration file."""
    
    filename: str
    status: str  # 'safe', 'unsafe', 'irreversible'
    errors: int
    warnings: int
    infos: int
    has_drop_table: bool = False
    has_drop_column: bool = False


@dataclass
class HealthScore:
    """Health score calculation with breakdown."""
    
    score: int  # 0-100
    grade: str  # 'excellent', 'good', 'warning', 'critical'
    breakdown: dict[str, int]
    recommendation: str


@dataclass
class FolderHealthReport:
    """Migration folder health summary."""
    
    folder: str
    timestamp: str
    total_migrations: int
    safe_migrations: int
    unsafe_migrations: int
    irreversible_migrations: int
    safe_percentage: int
    
    errors: int
    warnings: int
    infos: int
    findings_by_code: dict[str, int]
    
    migration_statuses: list[MigrationStatus]
    health_score: HealthScore
    
    def to_text(self) -> str:
        """Generate formatted text report."""
        lines = []
        
        # Header
        lines.append("╔══════════════════════════════════════════════════════════╗")
        lines.append("║         Migration Folder Health Report                   ║")
        lines.append("╚══════════════════════════════════════════════════════════╝")
        lines.append("")
        lines.append(f"📁 Migration Folder: {self.folder}")
        lines.append(f"📅 Report Date: {self.timestamp}")
        lines.append("")
        
        # Summary Statistics
        lines.append("━" * 60)
        lines.append("📊 SUMMARY STATISTICS")
        lines.append("━" * 60)
        lines.append("")
        lines.append(f"  Total Migrations:              {self.total_migrations}")
        lines.append(f"  Safe Migrations:               {self.safe_migrations} ({self.safe_percentage}%)")
        unsafe_pct = 100 - self.safe_percentage if self.total_migrations > 0 else 0
        lines.append(f"  Unsafe Migrations:             {self.unsafe_migrations} ({unsafe_pct}%)")
        irreversible_pct = int(self.irreversible_migrations / self.total_migrations * 100) if self.total_migrations > 0 else 0
        lines.append(f"  Irreversible Migrations:       {self.irreversible_migrations} ({irreversible_pct}%)")
        lines.append("")
        
        # Findings Breakdown
        lines.append("━" * 60)
        lines.append("🔍 FINDINGS BREAKDOWN")
        lines.append("━" * 60)
        lines.append("")
        lines.append(f"  Errors:                        {self.errors}")
        lines.append(f"  Warnings:                      {self.warnings}")
        lines.append(f"  Infos:                         {self.infos}")
        lines.append("")
        
        if self.findings_by_code:
            lines.append("  Top Issues:")
            for code, count in sorted(self.findings_by_code.items(), key=lambda x: x[1], reverse=True)[:5]:
                lines.append(f"    • {code:30s} ({count} occurrence{'s' if count > 1 else ''})")
            lines.append("")
        
        # Migration File Status
        lines.append("━" * 60)
        lines.append("📋 MIGRATION FILE STATUS")
        lines.append("━" * 60)
        lines.append("")
        
        for mig in self.migration_statuses:
            icon = "✅" if mig.status == "safe" else "⚠️" if mig.status == "unsafe" else "🔴"
            status_text = f"({mig.status.capitalize()})"
            if mig.errors > 0 or mig.warnings > 0:
                issue_text = []
                if mig.errors > 0:
                    issue_text.append(f"{mig.errors} error{'s' if mig.errors > 1 else ''}")
                if mig.warnings > 0:
                    issue_text.append(f"{mig.warnings} warning{'s' if mig.warnings > 1 else ''}")
                status_text += f" ({', '.join(issue_text)})"
            
            lines.append(f"  {icon} {mig.filename:40s} {status_text}")
        lines.append("")
        
        # Health Score
        lines.append("━" * 60)
        lines.append(f"🏥 HEALTH SCORE: {self.health_score.score}/100 ({self.health_score.grade.capitalize()})")
        lines.append("━" * 60)
        lines.append("")
        lines.append("  Score Breakdown:")
        for key, value in self.health_score.breakdown.items():
            label = key.replace('_', ' ').capitalize()
            sign = "" if key == "base" else ("+" if value > 0 else "")
            lines.append(f"    {label:20s} {sign}{value}")
        lines.append("")
        lines.append(f"  Recommendation: {self.health_score.recommendation}")
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """Generate JSON report."""
        from ..models import (
            HealthResult as _HealthResult,
            HealthSummary as _HealthSummary,
            HealthFindings as _HealthFindings,
            HealthMigrationStatus as _HealthMigrationStatus,
            HealthScore as _HealthScore,
            HealthScoreBreakdown as _HealthScoreBreakdown,
            Status as _Status,
            HealthGrade as _HealthGrade,
        )
        model = _HealthResult(
            folder=self.folder,
            timestamp=self.timestamp,
            summary=_HealthSummary(
                total_migrations=self.total_migrations,
                safe_migrations=self.safe_migrations,
                unsafe_migrations=self.unsafe_migrations,
                irreversible_migrations=self.irreversible_migrations,
                safe_percentage=self.safe_percentage,
            ),
            findings=_HealthFindings(
                errors=self.errors,
                warnings=self.warnings,
                infos=self.infos,
                by_code=self.findings_by_code,
            ),
            migrations=[
                _HealthMigrationStatus(
                    filename=m.filename,
                    status=_Status(m.status),
                    errors=m.errors,
                    warnings=m.warnings,
                    has_drop_table=m.has_drop_table,
                    has_drop_column=m.has_drop_column,
                )
                for m in self.migration_statuses
            ],
            health_score=_HealthScore(
                score=self.health_score.score,
                grade=_HealthGrade(self.health_score.grade),
                breakdown=_HealthScoreBreakdown(
                    base=self.health_score.breakdown.get('base', 100),
                    error_penalty=self.health_score.breakdown.get('error_penalty', 0),
                    warning_penalty=self.health_score.breakdown.get('warning_penalty', 0),
                    irreversible_penalty=self.health_score.breakdown.get('irreversible_penalty', 0),
                ),
            ),
            recommendation=self.health_score.recommendation,
        )
        return model.model_dump_json(by_alias=True, indent=2)


class HealthAnalyzer:
    """Analyze migration folder health."""
    
    @staticmethod
    def analyze(state: SchemaState, insights_report: InsightsReport, 
                folder_path: str) -> FolderHealthReport:
        """
        Generate health report from schema state and insights.
        
        Args:
            state: Schema state from migrations
            insights_report: Insights analysis report
            folder_path: Path to migrations folder
        
        Returns:
            Folder health report with score and recommendations
        """
        # Count total migrations
        total_migrations = len(state.source_files)

        # Derive per-file error/warning counts from the InsightsReport instead of
        # re-implementing the same regex checks.  Migration-specific findings embed
        # the filename as the prefix before the first ": " in their message.
        _migration_codes = {
            'ADD_NOT_NULL_NO_DEFAULT',
            'SELECT_STAR_VIEW',
            'LARGE_DELETE_NO_WHERE',
            'TRIGGER_WITH_BUSINESS_LOGIC',
        }
        from collections import defaultdict as _defaultdict
        _per_file_errors: dict[str, int] = _defaultdict(int)
        _per_file_warnings: dict[str, int] = _defaultdict(int)
        for _finding in insights_report.findings:
            if _finding.code not in _migration_codes:
                continue
            colon_pos = _finding.message.find(': ')
            if colon_pos > 0:
                fname = _finding.message[:colon_pos]
                if _finding.severity == 'error':
                    _per_file_errors[fname] += 1
                elif _finding.severity == 'warning':
                    _per_file_warnings[fname] += 1

        # Analyze each migration file (only scan SQL for irreversible operations,
        # which InsightsEngine does not cover).
        migration_statuses = []
        for file_entry in state.source_files:
            filename = file_entry.get('filename', 'unknown')
            sql_upper = file_entry.get('sql', '').upper()

            errors = _per_file_errors[filename]
            warnings = _per_file_warnings[filename]
            infos = 0

            # Irreversible-operation detection (DROP TABLE / DROP COLUMN)
            has_drop_table = 'DROP TABLE' in sql_upper
            has_drop_column = 'DROP COLUMN' in sql_upper or 'DROP (' in sql_upper

            if has_drop_table or has_drop_column:
                status = 'irreversible'
            elif errors > 0:
                status = 'unsafe'
            else:
                status = 'safe'

            migration_statuses.append(MigrationStatus(
                filename=filename,
                status=status,
                errors=errors,
                warnings=warnings,
                infos=infos,
                has_drop_table=has_drop_table,
                has_drop_column=has_drop_column,
            ))
        
        # Count safe/unsafe/irreversible
        safe_count = sum(1 for m in migration_statuses if m.status == 'safe')
        unsafe_count = sum(1 for m in migration_statuses if m.status == 'unsafe')
        irreversible_count = sum(1 for m in migration_statuses if m.status == 'irreversible')
        
        safe_percentage = int(safe_count / total_migrations * 100) if total_migrations > 0 else 0
        
        # Count findings by code
        findings_by_code: dict[str, int] = {}
        for finding in insights_report.findings:
            code = finding.code
            findings_by_code[code] = findings_by_code.get(code, 0) + 1
        
        # Calculate health score
        base_score = 100
        error_penalty = len(insights_report.errors()) * 20
        warning_penalty = len(insights_report.warnings()) * 5
        irreversible_penalty = irreversible_count * 10
        
        score = max(0, base_score - error_penalty - warning_penalty - irreversible_penalty)
        
        # Determine grade
        if score >= 90:
            grade = 'excellent'
        elif score >= 75:
            grade = 'good'
        elif score >= 50:
            grade = 'warning'
        else:
            grade = 'critical'
        
        # Generate recommendation
        error_count = len(insights_report.errors())
        warning_count = len(insights_report.warnings())
        
        if error_count > 0:
            recommendation = f"Fix {error_count} error{'s' if error_count > 1 else ''} before production deployment."
        elif warning_count > 0:
            recommendation = f"Review {warning_count} warning{'s' if warning_count > 1 else ''} to improve migration safety."
        elif irreversible_count > 0:
            recommendation = f"{irreversible_count} irreversible migration{'s' if irreversible_count > 1 else ''} detected - ensure backups are in place."
        else:
            recommendation = "All migrations are safe. No issues detected."
        
        health_score = HealthScore(
            score=score,
            grade=grade,
            breakdown={
                'base': base_score,
                'error_penalty': -error_penalty,
                'warning_penalty': -warning_penalty,
                'irreversible_penalty': -irreversible_penalty,
            },
            recommendation=recommendation,
        )
        
        return FolderHealthReport(
            folder=folder_path,
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_migrations=total_migrations,
            safe_migrations=safe_count,
            unsafe_migrations=unsafe_count,
            irreversible_migrations=irreversible_count,
            safe_percentage=safe_percentage,
            errors=len(insights_report.errors()),
            warnings=len(insights_report.warnings()),
            infos=len(insights_report.infos()),
            findings_by_code=findings_by_code,
            migration_statuses=migration_statuses,
            health_score=health_score,
        )
