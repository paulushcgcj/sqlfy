# Contract Versioning

## Strategy

SQLFY uses **slot-based versioning**: each breaking contract change
creates a new version slot while the previous slot remains registered
and published.

Version identifiers are opaque strings of the form `v<N>` where `N`
is an incrementing integer starting at 1.

```
insights@v1   ← first public contract
insights@v2   ← breaking change; v1 still exists
```

## What Constitutes a Breaking Change

A change is **breaking** if it:

* Removes a required field
* Renames a required field
* Changes the type of a field to an incompatible type (e.g. `str → int`)
* Changes an optional field to required
* Removes an enum variant that may be present in existing outputs

A change is **non-breaking** (allowed in-place) if it:

* Adds a new optional field
* Adds a new enum variant
* Improves a field description (documentation only)
* Adds a new `$defs` entry (new nested model)

## Versioning Rules

| Rule | Detail |
|---|---|
| New contract | Start at `v1` |
| Non-breaking change | Modify the `v1` class in-place |
| Breaking change | Create `v2.py`, register `insights@v2`, keep `v1.py` unchanged |
| Deprecation | Mark `v1` with `CONTRACT_DEPRECATED = True`; keep registered for two releases |
| Removal | Remove after the deprecation period; update migration guide |

## File Layout for Multiple Versions

```
contracts/analysis/
├── __init__.py
├── v1.py     ← InsightsV1, HealthV1  (original; never modified after publishing)
└── v2.py     ← InsightsV2            (breaking change; new file)
```

## Registry Keys

Registry keys follow the pattern `"{name}@{version}"`:

```python
CONTRACTS = {
    "insights@v1": ContractEntry(name="insights", version="v1", ...),
    "insights@v2": ContractEntry(name="insights", version="v2", ...),
}
```

## Version in the Schema File

Each generated JSON Schema file includes the contract version in its
`title` and `$id` fields:

```json
{
  "$schema": "https://json-schema.org/draft-07/schema",
  "$id": "https://sqlfy.dev/contracts/insights/v1",
  "title": "InsightsV1",
  ...
}
```

## Coexistence Example

When v2 ships, consumers can target either version explicitly:

```bash
# Consumer using v1 output
sqlfy insights --format json | validate-against insights-v1.json

# Consumer using v2 output (future)
sqlfy insights --format json --contract v2 | validate-against insights-v2.json
```

The CLI command itself does not need to change; version selection is a
future enhancement that the registry already supports.

## Version Compatibility Matrix

Maintained in `build/contracts/index.json`. Each entry includes a
`status` field:

```json
{
  "name": "insights",
  "version": "v1",
  "status": "stable"   ← stable | deprecated | removed
}
```

## Deprecation Timeline

1. **Announce** in release notes: `insights@v1` deprecated, `insights@v2` available
2. **Mark** `CONTRACT_DEPRECATED = True` in `v1.py`
3. **Wait** at least two minor releases
4. **Remove** `v1.py` and the registry entry
5. **Publish** updated `index.json` with `status: "removed"` for the previous version

## Gotchas

* Never modify a published contract class — create a new version.
* Never remove a version from the registry without a deprecation period.
* `models.py` can have non-breaking additive changes without bumping
  contract versions (add optional fields freely).
* A breaking change in `models.py` always requires a new contract
  version AND a new JSON Schema artifact.
