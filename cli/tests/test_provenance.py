"""Tests for provenance collection and verification (Feature #18)."""

import json
import subprocess
import shutil
from pathlib import Path

import pytest

from sqlfy.analysis.provenance import collect_provenance, write_manifest, verify_manifest


pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")


def _run(cmd, cwd: Path):
    return subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def test_collect_and_verify(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    migrations = repo / "migrations"
    migrations.mkdir()

    # Create two migration files
    f1 = migrations / "V1__create.sql"
    f1.write_text("CREATE TABLE t1 (id INT);\n")
    f2 = migrations / "V2__add.sql"
    f2.write_text("CREATE TABLE t2 (id INT);\n")

    # Init git repo and commit
    _run(["git", "init"], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Test User"], repo)
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "Initial commit"], repo)

    manifest = collect_provenance(str(migrations))
    assert manifest.get("migrations_dir")
    assert manifest.get("repo_root") == str(repo.resolve())
    files = manifest.get("files", [])
    assert len(files) == 2
    for f in files:
        assert "commit" in f
        assert f.get("commit") is not None

    out = tmp_path / "prov.json"
    write_manifest(manifest, str(out))

    verify_result = verify_manifest(str(out), str(migrations))
    assert isinstance(verify_result, dict)
    assert "diffs" in verify_result
    assert len(verify_result["diffs"]) == 0
