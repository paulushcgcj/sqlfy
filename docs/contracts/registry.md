# Contract Registry

## Purpose

The registry is the **single source of truth** for all public contracts.
It answers: "What JSON outputs does SQLFY produce, and what is their schema?"

## Location

```
cli/src/sqlfy/contracts/registry.py
```

## Structure

```python
from dataclasses import dataclass
from typing import ClassVar, Type
from pydantic import BaseModel

@dataclass(frozen=True)
class ContractEntry:
    name: str           # stable identifier, e.g. "insights"
    version: str        # slot version, e.g. "v1"
    command: str        # CLI command, e.g. "insights"
    description: str    # human-readable purpose
    model_class: Type[BaseModel]

CONTRACTS: dict[str, ContractEntry] = {
    "insights@v1": ContractEntry(...),
    "health@v1":   ContractEntry(...),
    ...
}
```

## Registry Key Convention

Keys follow `"{name}@{version}"`. This makes it unambiguous to address a
specific version and allows the same name to appear at multiple versions:

```python
CONTRACTS["insights@v1"]   # first version
CONTRACTS["insights@v2"]   # hypothetical breaking-change version
```

## Adding a Contract

1. Define the contract class in its domain module (e.g.
   `contracts/analysis/v1.py`).
2. Import it in `registry.py`.
3. Add a `ContractEntry` to `CONTRACTS`.

```python
# contracts/analysis/v1.py
class InsightsV1(ContractBase, InsightsResult):
    CONTRACT_NAME = "insights"
    CONTRACT_VERSION = "v1"
    CONTRACT_DESCRIPTION = "Schema quality findings"
    CONTRACT_COMMAND = "insights"

# contracts/registry.py
from .analysis.v1 import InsightsV1

CONTRACTS: dict[str, ContractEntry] = {
    "insights@v1": ContractEntry(
        name="insights",
        version="v1",
        command="insights",
        description="Schema quality findings from sqlfy insights --format json",
        model_class=InsightsV1,
    ),
    ...
}
```

## Discovery Helpers

The registry module exposes several helpers for tooling:

```python
from sqlfy.contracts.registry import (
    CONTRACTS,
    all_contracts,          # list all entries
    get_contract,           # get by name@version key
    latest_contracts,       # latest version per name
    discover,               # auto-discovery via module walk (opt-in)
)
```

### `all_contracts()`

Returns all registered `ContractEntry` instances in registration order.

### `get_contract(key: str) -> ContractEntry`

Returns the entry for `"insights@v1"`. Raises `KeyError` on missing key.

### `latest_contracts()`

Returns the highest-version entry for each unique contract name. Useful
for generating documentation or the current recommended schema set.

### `discover()`

Walks `contracts/**/*.py` and auto-registers any class that inherits
from `ContractBase` and has a non-empty `CONTRACT_NAME`. Useful if the
number of contract modules grows large. Not called by default.

## Invariants

* Every CLI command that produces JSON output must have at least one
  registered contract.
* Registry keys are immutable once published.
* Entries are `frozen=True` dataclasses; they cannot be mutated at runtime.
* The registry is populated at import time with no I/O side effects.

## Validation

The build generator validates the registry before writing artifacts:

* All `model_class` values must be importable Pydantic models.
* All `model_class.model_json_schema()` calls must succeed.
* Duplicate keys raise a `ValueError` at import time.
