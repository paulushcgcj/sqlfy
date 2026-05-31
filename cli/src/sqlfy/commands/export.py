"""
sqlfy.commands.export
=====================
Export schema diagrams in various formats.

Supports:
  - dot (Graphviz DOT)
  - mermaid (Mermaid ERD)
  - excalidraw (Excalidraw JSON)
  - drawio (Draw.io XML)
"""

import json
import click
from pathlib import Path
from sqlfy.reconstructor import reconstruct
from sqlfy.core import parse_flyway_ver
from sqlfy.domain.schema_state import SchemaStateBuilder
from sqlfy.output.grapher import Grapher
from sqlfy.output.excalidraw_exporter import to_excalidraw
from sqlfy.output.drawio_exporter import to_drawio
from ._utils import load_files


@click.command()
@click.argument('migrations_dir', type=click.Path(exists=True, file_okay=False))
@click.option(
    '--format',
    type=click.Choice(['dot', 'mermaid', 'excalidraw', 'drawio', 'all']),
    default='mermaid',
    help='Export format'
)
@click.option(
    '--output',
    type=click.Path(),
    help='Output file path (default: stdout for single format, required for --all)'
)
@click.option(
    '--output-dir',
    type=click.Path(),
    help='Output directory when using --format all'
)
@click.option(
    '--title',
    default='',
    help='Diagram title'
)
@click.option(
    '--dialect',
    default='oracle',
    help='SQL dialect'
)
def export_cmd(migrations_dir, format, output, output_dir, title, dialect):
    """
    Export schema diagram in various formats.
    
    Examples:
    
        # Export to Mermaid (stdout)
        sqlfy export migrations/ --format mermaid
        
        # Export to Excalidraw file
        sqlfy export migrations/ --format excalidraw --output schema.excalidraw
        
        # Export all formats to directory
        sqlfy export migrations/ --format all --output-dir exports/
    """
    # Load migrations using the shared cached loader
    files = load_files(migrations_dir, None)

    if not files:
        click.echo(f"No .sql files found in {migrations_dir}", err=True)
        raise click.Abort()
    
    # Reconstruct schema
    graph = reconstruct(files, dialect=dialect)
    state = SchemaStateBuilder.from_graph(graph, source_files=files)
    
    # Generate title if not provided
    if not title:
        title = f"Database Schema ({len(state.tables)} tables)"
    
    # Export based on format
    if format == 'all':
        if not output_dir:
            click.echo("--output-dir is required when using --format all", err=True)
            raise click.Abort()
        
        export_all_formats(state, Path(output_dir), title)
        click.echo(f"Exported all formats to {output_dir}/")
    
    else:
        content = export_single_format(state, format, title)
        
        if output:
            output_path = Path(output)
            output_path.write_text(content, encoding='utf-8')
            click.echo(f"Exported to {output}")
        else:
            click.echo(content)


def export_single_format(state, format: str, title: str) -> str:
    """Export schema in a single format."""
    if format == 'dot':
        return Grapher.to_dot(state, title=title)
    
    elif format == 'mermaid':
        return Grapher.to_mermaid(state, title=title)
    
    elif format == 'excalidraw':
        data = to_excalidraw(state, title=title)
        return json.dumps(data, indent=2)
    
    elif format == 'drawio':
        return to_drawio(state, title=title)
    
    else:
        raise ValueError(f"Unknown format: {format}")


def export_all_formats(state, output_dir: Path, title: str):
    """Export schema in all formats to a directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # DOT
    (output_dir / 'schema.dot').write_text(
        Grapher.to_dot(state, title=title),
        encoding='utf-8'
    )
    
    # Mermaid
    (output_dir / 'schema.mmd').write_text(
        Grapher.to_mermaid(state, title=title),
        encoding='utf-8'
    )
    
    # Excalidraw
    excalidraw_data = to_excalidraw(state, title=title)
    (output_dir / 'schema.excalidraw').write_text(
        json.dumps(excalidraw_data, indent=2),
        encoding='utf-8'
    )
    
    # Draw.io
    (output_dir / 'schema.drawio').write_text(
        to_drawio(state, title=title),
        encoding='utf-8'
    )
