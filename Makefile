# SQLfy — top-level Makefile
# Usage: make <target>

.PHONY: codegen-ts codegen-py codegen contracts test help

## codegen-ts: Regenerate app/src/core/types.ts from schema/types.json
codegen-ts:
	node schema/codegen.mjs

## codegen-py: Regenerate cli/src/sqlfy/models.py from schema/types.json
codegen-py:
	python3 schema/codegen.py

## codegen: Regenerate both TypeScript and Python types
codegen: codegen-ts codegen-py

## contracts: Generate JSON Schema build artifacts from the contract registry
contracts:
	cd cli && python -m sqlfy.build.generate_contracts

## test: Run Python CLI test suite
test:
	cd cli && python3 -m pytest tests/ -q

## help: Show this help
help:
	@grep -E '^## ' Makefile | sed 's/## /  /'
