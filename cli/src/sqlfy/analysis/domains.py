"""
domains.py
==========
Semantic domain detection for schema graphs.

Automatically clusters tables into business domains using:
- Dependency density (community detection via Leiden/Louvain)
- Naming patterns (common prefixes)
- Cross-domain dependency analysis

Adapted from graphify Feature #27.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

import networkx as nx

from ..clustering import detect_communities
from ..domain.schema_state import SchemaState


@dataclass
class Domain:
    """A semantic business domain containing related tables."""
    id: int
    name: str
    tables: list[str]
    cohesion: float
    description: str
    table_count: int
    
    def __post_init__(self):
        self.table_count = len(self.tables)


@dataclass
class CrossDomainDependency:
    """Dependency between two domains."""
    from_domain: str
    to_domain: str
    strength: str  # 'weak', 'medium', 'strong'
    fk_count: int


@dataclass
class DomainResult:
    """Result of domain detection."""
    domains: list[Domain]
    cross_domain_deps: list[CrossDomainDependency]
    algorithm: str
    total_tables: int
    
    @property
    def num_domains(self) -> int:
        """Return number of domains."""
        return len(self.domains)


def detect_domains(
    state: SchemaState,
    resolution: float = 1.0,
    min_cohesion: float = 0.1,
    enable_splitting: bool = True,
) -> DomainResult:
    """
    Detect semantic domains in the schema using community detection.
    
    Args:
        state: SchemaState from reconstructed migrations.
        resolution: Community detection resolution (>1 = more communities, <1 = fewer).
        min_cohesion: Minimum cohesion score to keep a domain.
        enable_splitting: If True, split oversized domains.
    
    Returns:
        DomainResult with domains, cross-domain dependencies, and metadata.
    """
    # Build NetworkX graph from SchemaState
    G = _build_graph_from_state(state)
    
    if G.number_of_nodes() == 0:
        return DomainResult(
            domains=[],
            cross_domain_deps=[],
            algorithm='none',
            total_tables=0,
        )
    
    # Run community detection
    comm_result = detect_communities(
        G,
        resolution=resolution,
        min_cohesion=min_cohesion,
        enable_splitting=enable_splitting,
    )
    
    # Convert communities to semantic domains
    domains = []
    for cid, tables in comm_result.communities.items():
        cohesion = comm_result.cohesion_scores[cid]
        label = infer_domain_label(tables)
        description = infer_domain_description(tables, state)
        
        domains.append(Domain(
            id=cid,
            name=label,
            tables=sorted(tables),
            cohesion=cohesion,
            description=description,
            table_count=len(tables),
        ))
    
    # Sort domains by size (largest first)
    domains.sort(key=lambda d: d.table_count, reverse=True)
    
    # Analyze cross-domain dependencies
    cross_deps = _analyze_cross_domain_deps(state, comm_result.node_to_community, domains)
    
    return DomainResult(
        domains=domains,
        cross_domain_deps=cross_deps,
        algorithm=comm_result.algorithm,
        total_tables=len(state.tables),
    )


def _build_graph_from_state(state: SchemaState) -> nx.Graph:
    """Build an undirected NetworkX graph from SchemaState."""
    G = nx.Graph()
    
    # Add nodes (tables)
    for table in state.tables.values():
        G.add_node(table.full_name)
    
    # Add edges (foreign key relationships)
    for rel in state.relationships:
        # Undirected edges for community detection
        G.add_edge(rel.from_table, rel.to_table)
    
    return G


def infer_domain_label(tables: list[str]) -> str:
    """
    Infer domain name from table names using common prefix heuristics.
    
    Args:
        tables: List of table names in the domain.
    
    Returns:
        Human-readable domain name.
    """
    if not tables:
        return "Unknown Domain"
    
    # Extract prefixes (first part before underscore or period)
    prefixes = defaultdict(int)
    for table in tables:
        # Split on period (schema.table) or underscore (prefix_table)
        parts = table.replace('.', '_').split('_')
        if len(parts) > 1:
            prefix = parts[-2] if '.' in table else parts[0]
            prefixes[prefix.upper()] = prefixes[prefix.upper()] + 1
    
    # Find most common prefix
    if prefixes:
        common_prefix = max(prefixes, key=lambda k: prefixes.get(k) or 0)
        count = prefixes[common_prefix]
        
        # If at least 50% of tables share this prefix, use it
        if count >= len(tables) * 0.5:
            return f"{common_prefix.capitalize()} Domain"
    
    # Fallback: use first table name
    first_table = tables[0]
    # Extract just the table name (after schema prefix)
    table_name = first_table.split('.')[-1]
    return f"{table_name.capitalize()} Domain"


def infer_domain_description(tables: list[str], state: SchemaState) -> str:
    """
    Infer domain description from table names and comments.
    
    Args:
        tables: List of table names in the domain.
        state: SchemaState for accessing table metadata.
    
    Returns:
        Brief description of the domain.
    """
    # Try to extract common theme from table comments
    comments = []
    for table_name in tables:
        table = state.tables.get(table_name)
        if table and table.comment:
            comments.append(table.comment)
    
    # For now, just count tables
    # Future enhancement: use LLM or NLP to infer theme
    return f"Domain containing {len(tables)} related tables"


def _analyze_cross_domain_deps(
    state: SchemaState,
    node_to_community: dict[str, int],
    domains: list[Domain],
) -> list[CrossDomainDependency]:
    """
    Analyze foreign key dependencies between domains.
    
    Args:
        state: SchemaState.
        node_to_community: Mapping of table name to domain ID.
        domains: List of detected domains.
    
    Returns:
        List of CrossDomainDependency objects.
    """
    # Build domain name lookup
    domain_names = {d.id: d.name for d in domains}
    
    # Count FKs between domains
    cross_fks: dict[tuple[int, int], int] = defaultdict(int)
    
    for rel in state.relationships:
        from_domain = node_to_community.get(rel.from_table)
        to_domain = node_to_community.get(rel.to_table)
        
        # Skip if same domain or missing domain info
        if from_domain is None or to_domain is None or from_domain == to_domain:
            continue
        
        # Count FK
        cross_fks[(from_domain, to_domain)] += 1
    
    # Convert to CrossDomainDependency objects
    deps = []
    for (from_id, to_id), fk_count in cross_fks.items():
        # Determine strength
        if fk_count >= 10:
            strength = 'strong'
        elif fk_count >= 5:
            strength = 'medium'
        else:
            strength = 'weak'
        
        deps.append(CrossDomainDependency(
            from_domain=domain_names.get(from_id, f"Domain {from_id}"),
            to_domain=domain_names.get(to_id, f"Domain {to_id}"),
            strength=strength,
            fk_count=fk_count,
        ))
    
    # Sort by FK count (strongest first)
    deps.sort(key=lambda d: d.fk_count, reverse=True)
    
    return deps


# ─────────────────────────────────────────────
# FORMATTERS
# ─────────────────────────────────────────────

def format_text(result: DomainResult) -> str:
    """Format domain detection result as human-readable text."""
    lines = []
    a = lines.append
    
    a('\n╔══════════════════════════════════════════╗')
    a('║     SEMANTIC DOMAIN DETECTION            ║')
    a('╚══════════════════════════════════════════╝\n')
    
    a(f'Algorithm: {result.algorithm}')
    a(f'Total tables: {result.total_tables}')
    a(f'Domains detected: {result.num_domains}')
    a('')
    
    if not result.domains:
        a('No domains detected.')
        return '\n'.join(lines)
    
    # Domain details
    for domain in result.domains:
        a(f'\n━━━ {domain.name} (cohesion: {domain.cohesion:.2f}) ━━━')
        a(f'  Tables ({domain.table_count}):')
        for table in domain.tables:
            a(f'    • {table}')
        a(f'  Description: {domain.description}')
    
    # Cross-domain dependencies
    if result.cross_domain_deps:
        a('\n\n╔══════════════════════════════════════════╗')
        a('║     CROSS-DOMAIN DEPENDENCIES            ║')
        a('╚══════════════════════════════════════════╝\n')
        
        for dep in result.cross_domain_deps:
            strength_badge = {
                'weak': '○',
                'medium': '◐',
                'strong': '●',
            }[dep.strength]
            
            a(f'{strength_badge} {dep.from_domain} → {dep.to_domain}')
            a(f'   ({dep.strength}: {dep.fk_count} foreign keys)')
    
    a('')
    return '\n'.join(lines)


def format_json(result: DomainResult) -> str:
    """Format domain detection result as JSON."""
    import json
    
    data = {
        'algorithm': result.algorithm,
        'total_tables': result.total_tables,
        'num_domains': result.num_domains,
        'domains': [
            {
                'id': d.id,
                'name': d.name,
                'table_count': d.table_count,
                'cohesion': round(d.cohesion, 3),
                'tables': d.tables,
                'description': d.description,
            }
            for d in result.domains
        ],
        'cross_domain_dependencies': [
            {
                'from_domain': dep.from_domain,
                'to_domain': dep.to_domain,
                'strength': dep.strength,
                'fk_count': dep.fk_count,
            }
            for dep in result.cross_domain_deps
        ],
    }
    
    return json.dumps(data, indent=2, ensure_ascii=False)
