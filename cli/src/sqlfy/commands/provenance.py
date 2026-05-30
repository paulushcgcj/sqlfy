"""Collect git provenance for migration files.

Feature #18: Migration Provenance Tracking
"""

import json
import sys
from pathlib import Path

from ..analysis.provenance import collect_provenance, write_manifest, verify_manifest
from ._utils import write_output


def _format_manifest_text(manifest: dict) -> str:
    lines = [f"Provenance for: {manifest.get('migrations_dir')}", f"Repo root: {manifest.get('repo_root')}", f"Generated at: {manifest.get('generated_at')}", ""]
    for f in manifest.get("files", []):
        branches = ",".join(f.get("branches") or [])
        lines.append(f"{f['path']}: commit={f.get('commit') or 'UNTRACKED'} author={f.get('author_name') or ''} date={f.get('date') or ''} pr={f.get('pr') or ''} branches={branches}")
    return "\n".join(lines)


def _format_diffs_text(result: dict) -> str:
    diffs = result.get("diffs", [])
    lines: list[str] = []
    for d in diffs:
        st = d.get("status")
        if st == "commit_changed":
            lines.append(f"{d['path']}: commit changed {d.get('old')} -> {d.get('new')}")
        elif st == "missing_in_current":
            lines.append(f"{d['path']}: missing in current migrations")
        elif st == "new_file":
            lines.append(f"{d['path']}: new file in current folder")
        else:
            lines.append(str(d))
    return "\n".join(lines)


def _do_verify(manifest_path: str, migrations_dir: str, fmt: str, out: str | None, recursive: bool = True, include_untracked: bool = False) -> int:
    try:
        result = verify_manifest(manifest_path, migrations_dir, recursive=recursive, include_untracked=include_untracked)
    except Exception as e:
        print(f"Error verifying manifest: {e}", file=sys.stderr)
        return 2

    if fmt == "json":
        write_output(json.dumps(result, indent=2, ensure_ascii=False), out)
        return 0

    diffs = result.get("diffs", [])
    if not diffs:
        write_output("No differences found. Manifest matches current git provenance.", out)
        return 0

    write_output(_format_diffs_text(result), out)
    bad = any(d.get("status") in ("commit_changed", "missing_in_current") for d in diffs)
    return 1 if bad else 0


def _do_record(manifest: dict, migrations_dir: str, out: str | None) -> int:
    out_path = out if out else str(Path(migrations_dir) / "provenance.json")
    try:
        write_manifest(manifest, out_path)
        print(f"Wrote provenance manifest: {out_path}", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"Error writing manifest: {e}", file=sys.stderr)
        return 3


def cmd_provenance(
    *,
    migrations_dir: str | None = None,
    format: str = "text",
    out: str | None = None,
    verify: str | None = None,
    record: bool = False,
    no_recursive: bool = False,
    include_untracked: bool = False,
) -> int:
    if not migrations_dir:
        print("Error: migrations_dir required", file=sys.stderr)
        return 1

    fmt = (format or "text").lower()
    recursive = not no_recursive

    if verify:
        return _do_verify(verify, migrations_dir, fmt, out, recursive=recursive, include_untracked=include_untracked)

    try:
        manifest = collect_provenance(migrations_dir, recursive=recursive, include_untracked=include_untracked)
    except Exception as e:
        print(f"Error collecting provenance: {e}", file=sys.stderr)
        return 2

    if record:
        return _do_record(manifest, migrations_dir, out)

    if fmt == "json":
        write_output(json.dumps(manifest, indent=2, ensure_ascii=False), out)
    else:
        write_output(_format_manifest_text(manifest), out)

    return 0
