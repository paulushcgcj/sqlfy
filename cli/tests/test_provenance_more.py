"""Additional tests for provenance flags and non-git behavior."""

import json
import pytest
from pathlib import Path

from sqlfy.analysis.provenance import collect_provenance


def test_collect_provenance_non_git_include_untracked(tmp_path):
    d = tmp_path / "mig"
    d.mkdir()
    (d / "V1__a.sql").write_text("CREATE TABLE a (id INT);\n")
    sub = d / "sub"
    sub.mkdir()
    (sub / "V2__b.sql").write_text("CREATE TABLE b (id INT);\n")

    # include_untracked=True should work even when folder is not a git repo
    manifest = collect_provenance(str(d), recursive=True, include_untracked=True)
    paths = {f["path"] for f in manifest["files"]}
    assert "V1__a.sql" in paths
    assert "sub/V2__b.sql" in paths
    # commits are None for untracked files
    for f in manifest["files"]:
        assert f.get("commit") is None

    # include_untracked=False should error when not in a git repo
    with pytest.raises(ValueError):
        collect_provenance(str(d), recursive=True, include_untracked=False)


def test_collect_provenance_no_recursive(tmp_path):
    d = tmp_path / "mig2"
    d.mkdir()
    (d / "V1__root.sql").write_text("CREATE TABLE root (id INT);\n")
    sub = d / "nested"
    sub.mkdir()
    (sub / "V2__nested.sql").write_text("CREATE TABLE nested (id INT);\n")

    manifest = collect_provenance(str(d), recursive=False, include_untracked=True)
    paths = {f["path"] for f in manifest["files"]}
    assert "V1__root.sql" in paths
    assert not any(p.startswith("nested/") for p in paths)
