# sqlfy CLI

Flyway SQL migration parser — schema graph engine, LLM vector chunk builder, and migration analysis toolkit.

## Features

- **Schema Analysis**: Parse Flyway migrations, reconstruct schema state, detect anti-patterns
- **Graph Visualization**: Export schema as DOT, Mermaid, Excalidraw, Draw.io, interactive HTML
- **Natural Language Q&A**: RAG-powered schema assistant with Claude integration
- **Migration Safety**: Validate ordering, detect drift, analyze rollback feasibility, simulate changes
- **Developer Tools**: SQL linting, dependency analysis, column-level lineage tracking

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Quick Start

### Install uv (if not already installed)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Install sqlfy

```bash
# Clone the repo (if not already cloned)
git clone https://github.com/yourorg/sqlfy
cd sqlfy/cli

# Run the install script (installs globally)
./install.sh

# Verify installation
./verify.sh

# Or install manually
uv build
uv pip install dist/sqlfy-*.whl
```

## Development Setup

```bash
# Sync dependencies (creates .venv automatically)
uv sync --all-extras --group dev

# Activate the virtual environment
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Install in editable mode
uv pip install -e .
```

## Running Tests

```bash
# All tests
uv run pytest -v

# Specific test file
uv run pytest tests/test_core.py -v

# With coverage
uv run pytest --cov=sqlfy --cov-report=term-missing
```

## Building

```bash
# Build wheel and source distribution
uv build

# Output: dist/sqlfy-VERSION-py3-none-any.whl
#         dist/sqlfy-VERSION.tar.gz
```

## Usage

### Basic Commands

```bash
# Dump schema state as JSON
sqlfy dump migrations/ --format json > schema.json

# Generate LLM vector chunks
sqlfy chunks migrations/ --format json > chunks.json

# Export as Mermaid diagram
sqlfy graph migrations/ --format mermaid > schema.mmd

# Analyze schema for issues
sqlfy insights migrations/

# Health report with score
sqlfy health migrations/
```

### Schema Evolution

```bash
# Compare two schema versions
sqlfy diff migrations-v1/ migrations-v2/

# Simulate a change before applying
sqlfy simulate migrations/ --sql "ALTER TABLE users ADD (status VARCHAR2(20));" --diff

# Detect drift between environments
sqlfy drift migrations-prod/ migrations-dev/

# Analyze rollback feasibility
sqlfy rollback-analysis migrations/
```

### Developer Tools

```bash
# Validate migration ordering
sqlfy validate migrations/ --fix-numbering

# Analyze dependencies
sqlfy deps migrations/ --critical-path

# Lint SQL files
sqlfy lint migrations/ --min-score 80

# Column-level lineage
sqlfy lineage APP.USERS.EMAIL
```

### Natural Language Q&A

```bash
# Ask a question (uses local BM25 retrieval, no API key needed)
sqlfy ask migrations/ "Which tables have no primary key?"

# Interactive chat (uses local BM25 retrieval, no API key needed)
sqlfy chat migrations/

# With vector embeddings (experimental) — requires VOYAGE_API_KEY
export VOYAGE_API_KEY="..."
sqlfy ask migrations/ "What happens when I delete a user?" --embed
sqlfy chat migrations/ --embed
```

> **Note:** Text generation (Claude) requires `ANTHROPIC_API_KEY`. Vector embeddings (Voyage AI) require `VOYAGE_API_KEY`. These are separate services with separate credentials. The `--embed` flag is experimental.

## Configuration

### pyproject.toml

The project is configured via `pyproject.toml`:

- **Dependencies**: Core runtime deps (sqlglot, networkx, sqllineage, typer, rich, pydantic, watchdog)
- **Optional dependencies**:
  - `yaml` (PyYAML) — for YAML output in `dump` command
  - `lint` (sqlfluff) — for `lint` command; install with `pip install 'sqlfy-cli[lint]'`
  - `dev` (pytest, ruff, pyright, etc.) — for development
- **Entry point**: `sqlfy` command → `sqlfy.main:main`

### uv.lock

Lockfile for reproducible builds. Regenerate with:

```bash
uv sync --upgrade
```

## Project Structure

```
cli/
├── src/sqlfy/           # Source code
│   ├── commands/        # CLI command handlers (modular)
│   ├── analysis/        # Schema analysis modules
│   ├── domain/          # Core data models
│   ├── output/          # Export and visualization
│   ├── core.py          # Schema parsing engine
│   ├── reconstructor.py # Migration reconstruction
│   └── main.py          # CLI entry point
├── tests/               # Test suite (910 tests)
├── pyproject.toml       # Project metadata and dependencies
├── uv.lock              # Lockfile
└── README.md            # This file
```

## Testing

Tests use pytest with comprehensive coverage:

- **910 passing tests, 6 skipped**
- Coverage: Core parsing, reconstruction, analysis, export, CLI commands
- Run time: ~3s

### Add a new test

1. Create `tests/test_myfeature.py`
2. Import the module to test
3. Write test functions starting with `test_`
4. Run: `uv run pytest tests/test_myfeature.py -v`

## Contributing

1. Create a feature branch
2. Make changes
3. Add tests for new functionality
4. Run `uv run pytest -v` to verify
5. Build and test install: `uv build && uv pip install dist/sqlfy-*.whl`
6. Submit PR

## License

See LICENSE file in repository root.

## Support

- Issues: GitHub Issues
- Docs: See main README in repository root
- Examples: `cli/examples/` directory
