# Contract System Architecture

## Separation of Concerns

SQLFY makes a hard distinction between **internal domain models** and
**public contracts**.

```
Internal Domain Models          Public Contracts
─────────────────────           ────────────────
analysis/insights.py            contracts/analysis/v1.py
analysis/health.py              contracts/graph/v1.py
analysis/differ.py              contracts/impact/v1.py
domain/schema_state.py          contracts/evolution/v1.py
core.py                         contracts/registry.py
```

Internal models are allowed to change freely. Public contracts are
stable interfaces that follow a strict versioning policy.

## Module Layout

```
cli/src/sqlfy/
├── contracts/
│   ├── __init__.py             Public surface: ContractBase, registry
│   │
│   ├── common/
│   │   ├── __init__.py
│   │   ├── base.py             ContractBase mixin, ContractMetadata
│   │   ├── envelope.py         ResponseEnvelope[T] generic wrapper
│   │   └── metadata.py         BuildInfo dataclass
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   └── v1.py               InsightsV1, HealthV1
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   └── v1.py               GraphManifestV1
│   │
│   ├── impact/
│   │   ├── __init__.py
│   │   └── v1.py               ImpactV1
│   │
│   ├── evolution/
│   │   ├── __init__.py
│   │   └── v1.py               DiffV1, SimulateV1, RollbackV1
│   │
│   └── registry.py             CONTRACTS dict, ContractEntry
│
└── build/
    ├── __init__.py
    └── generate_contracts.py   Schema generator invoked at build time
```

## ContractBase

Every public contract class inherits from `ContractBase` alongside its
domain model:

```python
class InsightsV1(ContractBase, InsightsResult):
    CONTRACT_NAME: ClassVar[str] = "insights"
    CONTRACT_VERSION: ClassVar[str] = "v1"
    CONTRACT_DESCRIPTION: ClassVar[str] = "..."
    CONTRACT_COMMAND: ClassVar[str] = "insights"
```

`ContractBase` adds four `ClassVar` attributes. It does not add any
Pydantic fields, so the serialized JSON shape is identical to the
underlying model. The metadata is used solely by the registry and the
build generator.

## ContractEntry

`ContractEntry` is the registry record for one contract:

```python
@dataclass(frozen=True)
class ContractEntry:
    name: str               # stable contract name (e.g. "insights")
    version: str            # semantic version string (e.g. "v1")
    command: str            # CLI command that produces this output
    description: str        # human-readable description
    model_class: type       # the Pydantic contract class
```

The registry key is `"{name}@{version}"`, e.g. `"insights@v1"`.

## Schema Generation Pipeline

```
contracts/registry.py        ← source of truth
      ↓
build/generate_contracts.py  ← iterate CONTRACTS, call model_json_schema()
      ↓
build/contracts/schemas/     ← one JSON Schema file per contract
build/contracts/index.json   ← discovery index
build/contracts/manifest.json← build metadata
```

## Extension Points

### Adding a new contract

1. Create `contracts/<domain>/v1.py` with a class inheriting from
   `ContractBase` and the appropriate `models.py` class.
2. Add a `ContractEntry` to `contracts/registry.py`.
3. Run `make contracts` or `python setup.py build`.

### Adding a v2 contract

1. Create `contracts/<domain>/v2.py`.
2. Inherit from `ContractBase` and define new Pydantic fields.
3. Register under version `"v2"` in `registry.py`.
4. The v1 contract remains registered and is not removed.

### Auto-discovery

The registry currently uses explicit registration. If the number of
contracts grows large, switch to import-time auto-discovery via
`pkgutil.walk_packages` scanning `contracts/**/*.py` for classes
that inherit from `ContractBase`. The `registry.py` module already
exposes a `discover()` helper that enables this pattern.

## Invariants

* `models.py` is the canonical Python model source (auto-generated from
  `schema/types.json`). Do not hand-edit it.
* Contract classes never add Pydantic fields — they only add `ClassVar`
  metadata. Field changes always go through `schema/types.json`.
* Schema generation is deterministic: the same source always produces
  the same JSON Schema output.
* Contract names and versions are immutable once published.
