# Build Process

## Overview

Contract schema generation is integrated into the Python build lifecycle.
When `python setup.py build` runs (or `pip install -e .`), schemas are
generated automatically before any source is packaged.

```
developer runs:
  python setup.py build
  OR pip install -e .
  OR make contracts

    ↓

setup.py CustomBuildPy.run()
    ↓
sqlfy.build.generate_contracts.generate_all(output_dir)
    ↓
Iterates CONTRACTS registry
    ↓
Calls model_class.model_json_schema() for each entry
    ↓
Writes:
  build/contracts/schemas/<name>-<version>.json
  build/contracts/index.json
  build/contracts/manifest.json
```

## Entry Points

### `setup.py` (primary)

The `cli/setup.py` file defines `CustomBuildPy`, a subclass of
`setuptools.command.build_py.build_py`. Its `run()` method calls
`generate_contracts.generate_all()` before delegating to the standard
build.

```python
# cli/setup.py
from setuptools import setup
from setuptools.command.build_py import build_py

class CustomBuildPy(build_py):
    def run(self) -> None:
        from sqlfy.build.generate_contracts import generate_all
        generate_all()
        super().run()

setup(cmdclass={"build_py": CustomBuildPy})
```

### `python -m sqlfy.build.generate_contracts` (standalone)

The generator can also be invoked directly:

```bash
cd cli
python -m sqlfy.build.generate_contracts
# Or with a custom output directory:
python -m sqlfy.build.generate_contracts --out path/to/artifacts
```

### `make contracts` (Makefile convenience)

```bash
make contracts   # Equivalent to the above
```

## Output Artifacts

All artifacts are written under `cli/build/contracts/` by default.

### `schemas/`

One JSON Schema file per registered contract:

```
schemas/
├── insights-v1.json
├── health-v1.json
├── impact-v1.json
├── diff-v1.json
├── simulate-v1.json
├── rollback-v1.json
└── manifest-v1.json
```

Each file is a standard JSON Schema draft-07 document produced by
Pydantic's `model_json_schema()`. The schema includes:

* All field names and types
* Required fields
* Descriptions from `Field(..., description=...)`
* Nested model definitions under `$defs`

### `index.json`

Machine-readable discovery index. Consumers use this to list available
contracts without importing Python:

```json
{
  "generated_at": "2025-01-15T12:00:00Z",
  "contracts": [
    {
      "name": "insights",
      "version": "v1",
      "command": "insights",
      "description": "Schema quality findings",
      "schema_path": "schemas/insights-v1.json"
    }
  ]
}
```

### `manifest.json`

Build provenance metadata:

```json
{
  "build_timestamp": "2025-01-15T12:00:00Z",
  "sqlfy_version": "0.20.0",
  "python_version": "3.12.0",
  "contract_count": 7,
  "contracts": ["insights@v1", "health@v1", ...]
}
```

## Determinism

Schema generation is deterministic:

* The same `models.py` always produces the same schema JSON.
* Field order is stable (Pydantic preserves declaration order).
* JSON is serialised with `indent=2, sort_keys=False` (declaration order
  is the canonical order).

Run `git diff build/contracts/` after a `make contracts` to detect
unintended contract changes before committing.

## CI Integration

Recommended CI steps:

```yaml
- name: Build contracts
  run: cd cli && python setup.py build

- name: Verify contracts are up-to-date
  run: |
    git diff --exit-code cli/build/contracts/
    # Fails if schemas changed but were not committed
```

This ensures that contracts checked into the repository always match
the source models.
