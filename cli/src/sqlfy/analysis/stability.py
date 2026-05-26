"""
stability.py
============
Schema stability metrics for tracking schema evolution over time.

Computes:
- Churn rate: How often tables/columns change
- Volatility: Standard deviation of change frequency
- Stability score: Inverse of churn (stable schemas have low churn)
- Migration density: Migrations per table

Adapted from graphify Feature #29.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from ..domain.schema_state import SchemaState


@dataclass
class TableStabilityMetrics:
    """Stability metrics for a single table."""
    table_name: str
    modification_count: int
    churn_rate: float  # 0-100 percentage
    stability_score: int  # 0-100 (higher is more stable)
    created_in: str
    modified_in: list[str]


@dataclass
class ColumnStabilityMetrics:
    """Stability metrics for a single column."""
    table_name: str
    column_name: str
    modification_count: int
    churn_rate: float
    stability_score: int


@dataclass
class StabilityReport:
    """Complete stability report for a schema."""
    total_migrations: int
    migration_rate: Optional[float]  # Per month (if time data available)
    overall_stability_score: int
    high_churn_tables: list[TableStabilityMetrics]
    stable_tables: list[TableStabilityMetrics]
    all_table_metrics: list[TableStabilityMetrics]
    volatility: Optional[float]  # Standard deviation of modification counts
    
    @property
    def num_high_churn_tables(self) -> int:
        """Return number of high-churn tables (>20% churn rate)."""
        return len(self.high_churn_tables)
    
    @property
    def num_stable_tables(self) -> int:
        """Return number of stable tables (<10% churn rate)."""
        return len(self.stable_tables)


def calculate_stability(
    state: SchemaState,
    high_churn_threshold: float = 20.0,
    stable_threshold: float = 10.0,
) -> StabilityReport:
    """
    Calculate stability metrics for all tables in the schema.
    
    Args:
        state: SchemaState from reconstructed migrations.
        high_churn_threshold: Churn rate threshold for "high churn" (default: 20%).
        stable_threshold: Churn rate threshold for "stable" (default: 10%).
    
    Returns:
        StabilityReport with metrics for all tables.
    """
    total_migrations = len(state.migration_history)
    
    if total_migrations == 0:
        # No migrations, no metrics
        return StabilityReport(
            total_migrations=0,
            migration_rate=None,
            overall_stability_score=100,
            high_churn_tables=[],
            stable_tables=[],
            all_table_metrics=[],
            volatility=None,
        )
    
    # Count modifications per table
    table_modifications: dict[str, int] = defaultdict(int)
    table_created_in: dict[str, str] = {}
    table_modified_in: dict[str, list[str]] = defaultdict(list)
    
    # Track from SchemaState
    for table in state.tables.values():
        table_name = table.full_name
        table_created_in[table_name] = table.created_in
        
        # Count creation as one modification
        table_modifications[table_name] = 1
        
        # Add modified versions
        if table.modified_in:
            table_modifications[table_name] += len(table.modified_in)
            table_modified_in[table_name] = table.modified_in.copy()
    
    # Calculate metrics for each table
    all_metrics = []
    for table_name, mod_count in table_modifications.items():
        churn_rate = (mod_count / total_migrations) * 100
        stability_score = max(0, 100 - int(churn_rate * 2))
        
        all_metrics.append(TableStabilityMetrics(
            table_name=table_name,
            modification_count=mod_count,
            churn_rate=round(churn_rate, 2),
            stability_score=stability_score,
            created_in=table_created_in.get(table_name, 'unknown'),
            modified_in=table_modified_in.get(table_name, []),
        ))
    
    # Sort by churn rate (highest first)
    all_metrics.sort(key=lambda m: m.churn_rate, reverse=True)
    
    # Categorize tables
    high_churn = [m for m in all_metrics if m.churn_rate >= high_churn_threshold]
    stable = [m for m in all_metrics if m.churn_rate < stable_threshold]
    
    # Calculate overall stability score (weighted average)
    if all_metrics:
        overall_score = int(sum(m.stability_score for m in all_metrics) / len(all_metrics))
    else:
        overall_score = 100
    
    # Calculate volatility (standard deviation of modification counts)
    volatility = _calculate_volatility([m.modification_count for m in all_metrics])
    
    # Estimate migration rate (if we had time data, we'd use it)
    # For now, just return None since we don't have timestamps
    migration_rate = None
    
    return StabilityReport(
        total_migrations=total_migrations,
        migration_rate=migration_rate,
        overall_stability_score=overall_score,
        high_churn_tables=high_churn,
        stable_tables=stable,
        all_table_metrics=all_metrics,
        volatility=volatility,
    )


def _calculate_volatility(values: list[int]) -> Optional[float]:
    """Calculate standard deviation (volatility) of modification counts."""
    if not values or len(values) < 2:
        return None
    
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance ** 0.5


# ─────────────────────────────────────────────
# FORMATTERS
# ─────────────────────────────────────────────

def format_text(report: StabilityReport, show_all: bool = False) -> str:
    """Format stability report as human-readable text."""
    lines = []
    a = lines.append
    
    a('\n╔══════════════════════════════════════════╗')
    a('║     SCHEMA STABILITY METRICS             ║')
    a('╚══════════════════════════════════════════╝\n')
    
    a('Overall:')
    a(f'  Total migrations: {report.total_migrations}')
    if report.migration_rate is not None:
        a(f'  Migration rate: {report.migration_rate:.1f} per month')
    a(f'  Stability score: {report.overall_stability_score}/100')
    if report.volatility is not None:
        a(f'  Volatility (std dev): {report.volatility:.2f}')
    a('')
    
    # Grade
    grade = _get_stability_grade(report.overall_stability_score)
    a(f'  Grade: {grade}')
    a('')
    
    # High churn tables
    if report.high_churn_tables:
        a(f'\nHigh Churn Tables ({len(report.high_churn_tables)}):')
        a('  (Tables with churn rate >= 20%)\n')
        
        for m in report.high_churn_tables[:10]:  # Show top 10
            a(f'  • {m.table_name}')
            a(f'      {m.modification_count} modifications')
            a(f'      {m.churn_rate}% churn rate')
            a(f'      Stability score: {m.stability_score}/100')
            if m.modified_in:
                a(f'      Modified in versions: {", ".join(m.modified_in)}')
            a('')
    else:
        a('\nNo high-churn tables detected. ✓')
        a('')
    
    # Stable tables
    if report.stable_tables:
        a(f'\nStable Tables ({len(report.stable_tables)}):')
        a('  (Tables with churn rate < 10%)\n')
        
        for m in report.stable_tables[:5]:  # Show top 5
            a(f'  • {m.table_name}')
            a(f'      {m.modification_count} modifications')
            a(f'      {m.churn_rate}% churn rate')
            a(f'      Stability score: {m.stability_score}/100')
            a('')
    
    # Show all tables if requested
    if show_all and report.all_table_metrics:
        a('\n\nAll Tables (sorted by churn rate):')
        a('─' * 70)
        a(f'{"Table":<35} {"Mods":<6} {"Churn":<10} {"Stability":<10}')
        a('─' * 70)
        
        for m in report.all_table_metrics:
            churn_str = f'{m.churn_rate:.1f}%'
            stability_str = f'{m.stability_score}/100'
            a(f'{m.table_name:<35} {m.modification_count:<6} {churn_str:<10} {stability_str:<10}')
        
        a('─' * 70)
    
    a('')
    return '\n'.join(lines)


def format_json(report: StabilityReport) -> str:
    """Format stability report as JSON."""
    import json
    
    data = {
        'total_migrations': report.total_migrations,
        'migration_rate': report.migration_rate,
        'overall_stability_score': report.overall_stability_score,
        'grade': _get_stability_grade(report.overall_stability_score),
        'volatility': round(report.volatility, 3) if report.volatility is not None else None,
        'summary': {
            'high_churn_tables': len(report.high_churn_tables),
            'stable_tables': len(report.stable_tables),
            'total_tables': len(report.all_table_metrics),
        },
        'high_churn_tables': [
            {
                'table_name': m.table_name,
                'modification_count': m.modification_count,
                'churn_rate': m.churn_rate,
                'stability_score': m.stability_score,
                'created_in': m.created_in,
                'modified_in': m.modified_in,
            }
            for m in report.high_churn_tables
        ],
        'stable_tables': [
            {
                'table_name': m.table_name,
                'modification_count': m.modification_count,
                'churn_rate': m.churn_rate,
                'stability_score': m.stability_score,
                'created_in': m.created_in,
                'modified_in': m.modified_in,
            }
            for m in report.stable_tables
        ],
        'all_tables': [
            {
                'table_name': m.table_name,
                'modification_count': m.modification_count,
                'churn_rate': m.churn_rate,
                'stability_score': m.stability_score,
                'created_in': m.created_in,
                'modified_in': m.modified_in,
            }
            for m in report.all_table_metrics
        ],
    }
    
    return json.dumps(data, indent=2, ensure_ascii=False)


def _get_stability_grade(score: int) -> str:
    """Get letter grade for stability score."""
    if score >= 90:
        return 'A (Excellent)'
    elif score >= 75:
        return 'B (Good)'
    elif score >= 60:
        return 'C (Fair)'
    elif score >= 50:
        return 'D (Poor)'
    else:
        return 'F (Critical)'
