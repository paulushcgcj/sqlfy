# SQLFY Contract System

## Overview

SQLFY exposes structured JSON output from every CLI command. Those outputs
represent the **public interface** between SQLFY (producer) and any
consuming application (frontend, SDK, external tooling).

The Contract System formalises those outputs as:

* Explicit, versioned Pydantic models
* JSON Schema artifacts generated at build time
* A central registry for discovery and validation

## Contents

| Document | Purpose |
|---|---|
| [Architecture](architecture.md) | Module layout, responsibilities, extension points |
| [Build Process](build-process.md) | How schemas are generated during the build lifecycle |
| [Versioning](versioning.md) | Contract versioning strategy and breaking-change policy |
| [Registry](registry.md) | How contracts are registered and discovered |
| [Migration Plan](migration-plan.md) | Transition from ad-hoc JSON to formal contracts |

## Quick Start

### Add a new contract

1. Create `cli/src/sqlfy/contracts/<domain>/v1.py`
2. Define a class that inherits from `ContractBase` and the matching
   domain model in `models.py`
3. Register the contract in `cli/src/sqlfy/contracts/registry.py`
4. Run `make contracts` to regenerate build artifacts

### Run the build

```bash
cd cli
python setup.py build            # triggers contract generation
# OR
python -m sqlfy.build.generate_contracts --out build/contracts
# OR
make contracts                   # convenience target
```

### Inspect generated schemas

```bash
ls cli/build/contracts/schemas/
cat cli/build/contracts/index.json
cat cli/build/contracts/manifest.json
```

## Public Contracts

| Contract | Version | Command | Description |
|---|---|---|---|
| `insights` | v1 | `insights` | Schema quality findings |
| `health` | v1 | `health` | Migration folder health score |
| `impact` | v1 | `impact` | Transitive impact analysis |
| `diff` | v1 | `diff-versions` | Schema diff between versions |
| `simulate` | v1 | `simulate` | Dry-run DDL simulation |
| `rollback` | v1 | `rollback-analysis` | Rollback feasibility analysis |
| `manifest` | v1 | `manifest` | Schema graph metadata |
