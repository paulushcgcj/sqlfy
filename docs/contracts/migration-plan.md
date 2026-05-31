# Migration Plan

## Current State

Before this contract system was introduced, SQLFY's JSON output was
managed as follows:

* `schema/types.json` — hand-authored JSON Schema (source of truth)
* `schema/codegen.py` — generates `models.py` from `types.json`
* `cli/src/sqlfy/models.py` — auto-generated Pydantic models
* Commands serialise directly via `model.model_dump_json(by_alias=True)`

This worked, but had no:

* Build-time schema artifact generation
* Contract registry for discovery
* Versioning layer
* Separation between "model source" and "contract metadata"

## Target State

```
schema/types.json     →  models.py (auto-generated, unchanged)
                                 ↓
contracts/<domain>/v1.py  (thin wrapper adds ContractBase + ClassVar metadata)
                                 ↓
contracts/registry.py     (central CONTRACTS dict)
                                 ↓
build/generate_contracts.py  (emit JSON Schema artifacts at build time)
                                 ↓
build/contracts/             (distributable artifacts)
```

## Migration Steps

### Phase 0 (complete): Introduce the contract layer

* `contracts/` package created with `ContractBase`, domain modules,
  and `registry.py`.
* `build/` package created with `generate_contracts.py`.
* `setup.py` integrates generation into the build lifecycle.
* All existing models registered.

### Phase 1 (next): Validate output against contracts at runtime

Optionally validate CLI JSON output against the registered schema before
writing to disk or stdout. This catches regressions immediately:

```python
from sqlfy.contracts.registry import get_contract

entry = get_contract("insights@v1")
# Validate by constructing the contract model:
entry.model_class.model_validate(output_dict)
```

### Phase 2 (future): CLI output via contract models

Replace direct `model.model_dump_json()` calls in commands with contract
model instantiation. This makes the contract the *assembly point* rather
than just a schema mirror:

```python
# Currently (commands/analysis.py):
report.to_json()

# Future:
InsightsV1.from_domain(report).model_dump_json(by_alias=True)
```

This requires adding `from_domain()` factory methods to each contract,
mapping internal domain objects to public contract shapes. It is a
deliberate decoupling step.

### Phase 3 (future): Generate TypeScript types from schemas

With stable JSON Schema artifacts in `build/contracts/schemas/`, TypeScript
interfaces can be generated using any JSON-Schema-to-TypeScript tool:

```bash
npx json-schema-to-typescript \
  build/contracts/schemas/insights-v1.json \
  -o app/src/core/contracts/insights.ts
```

This replaces the current `schema/codegen.mjs` flow. SQLFY Python
becomes the *only* source of truth.

### Phase 4 (future): SDK generation

Use `build/contracts/index.json` to drive SDK generation for other
languages (Go, Rust, Java) via OpenAPI Generator or similar tooling.

## Backward Compatibility During Migration

* `models.py` is unchanged — all existing code continues to work.
* Contract classes are thin wrappers that add no new Pydantic fields.
* The JSON serialised by contract models is byte-for-byte identical to
  the JSON serialised by the underlying models.
* No command logic changes in Phase 0.

## Checklist

- [x] Create `contracts/common/base.py`
- [x] Create `contracts/common/envelope.py`
- [x] Create `contracts/common/metadata.py`
- [x] Create domain contract modules (`analysis`, `graph`, `impact`, `evolution`)
- [x] Create `contracts/registry.py`
- [x] Create `build/generate_contracts.py`
- [x] Add `setup.py` build integration
- [x] Add `make contracts` Makefile target
- [x] Add documentation in `docs/contracts/`
- [ ] Phase 1: Runtime output validation
- [ ] Phase 2: CLI output via contract models (`from_domain()` factories)
- [ ] Phase 3: TypeScript type generation from schemas
- [ ] Phase 4: Multi-language SDK generation
