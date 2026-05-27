from __future__ import annotations

import datetime
import json
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class FileProvenance:
    path: str
    commit: Optional[str] = None
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    date: Optional[str] = None
    branches: Optional[List[str]] = None
    pr: Optional[str] = None
    message: Optional[str] = None


def _run_git(args: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True, text=True)


def find_repo_root(start: Path) -> Optional[Path]:
    try:
        res = _run_git(["rev-parse", "--show-toplevel"], cwd=start.resolve())
    except FileNotFoundError:
        return None
    if res.returncode != 0:
        return None
    return Path(res.stdout.strip())


def _git_last_commit_info(path: Path, repo_root: Path) -> Dict[str, Optional[str]]:
    rel = str(path.resolve().relative_to(repo_root.resolve()))
    res = _run_git(["log", "-n", "1", "--pretty=format:%H%n%an%n%ae%n%ai%n%B", "--", rel], cwd=repo_root.resolve())
    if res.returncode != 0 or not res.stdout.strip():
        return {"commit": None, "author_name": None, "author_email": None, "date": None, "message": None}

    lines = res.stdout.splitlines()
    commit = lines[0] if len(lines) > 0 else None
    author_name = lines[1] if len(lines) > 1 else None
    author_email = lines[2] if len(lines) > 2 else None
    date = lines[3] if len(lines) > 3 else None
    message = "\n".join(lines[4:]).strip() if len(lines) > 4 else ""
    return {"commit": commit, "author_name": author_name, "author_email": author_email, "date": date, "message": message}


def _git_branches_containing(commit: Optional[str], repo_root: Path) -> List[str]:
    if not commit:
        return []
    res = _run_git(["branch", "--contains", commit], cwd=repo_root.resolve())
    if res.returncode == 0 and res.stdout.strip():
        branches: List[str] = []
        for line in res.stdout.splitlines():
            name = line.strip().lstrip("* ").strip()
            if name:
                branches.append(name)
        return branches

    # fallback: parse ref names from show -s --format=%D
    res2 = _run_git(["show", "-s", "--format=%D", commit], cwd=repo_root.resolve())
    if res2.returncode == 0 and res2.stdout.strip():
        parts = [p.strip() for p in res2.stdout.split(",")]
        return [p for p in parts if p and not p.startswith("HEAD")]
    return []


def _is_tracked(path: Path, repo_root: Path) -> bool:
    """Return True if the file is tracked by git in repo_root."""
    rel = str(path.resolve().relative_to(repo_root.resolve()))
    res = _run_git(["ls-files", "--error-unmatch", "--", rel], cwd=repo_root.resolve())
    return res.returncode == 0


def _detect_pr_from_message(message: Optional[str]) -> Optional[str]:
    if not message:
        return None
    patterns = [
        r"Merge pull request #(\d+)",
        r"pull request #(\d+)",
        r"Pull Request #(\d+)",
        r"\bPR #?(\d+)\b",
        r"Merge branch 'refs/pull/(\d+)/merge'",
        r"Merge branch 'pr/(\d+)'",
    ]
    for pat in patterns:
        m = re.search(pat, message, flags=re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def collect_provenance(migrations_dir: str, recursive: bool = True, include_untracked: bool = False) -> Dict[str, Any]:
    pdir = Path(migrations_dir).resolve()
    if not pdir.exists():
        raise ValueError(f"Path does not exist: {migrations_dir}")

    repo_root = find_repo_root(pdir)
    if not repo_root and not include_untracked:
        raise ValueError(f"Not a git repository (no git rev-parse) for: {migrations_dir}. Use include_untracked=True to collect without git.")

    sql_files = sorted(pdir.rglob("*.sql")) if recursive else sorted(pdir.glob("*.sql"))
    files: List[Dict[str, Any]] = []

    for f in sql_files:
        # If we have a repo root, optionally filter untracked files when include_untracked=False
        if repo_root and not include_untracked:
            try:
                tracked = _is_tracked(f, repo_root)
            except Exception:
                tracked = False
            if not tracked:
                # skip untracked files when user did not request them
                continue

        if repo_root:
            info = _git_last_commit_info(f, repo_root)
            commit = info.get("commit")
            branches = _git_branches_containing(commit, repo_root)
            pr = _detect_pr_from_message(info.get("message"))
        else:
            # non-git repository; include file with empty provenance
            info = {"commit": None, "author_name": None, "author_email": None, "date": None, "message": None}
            commit = None
            branches = []
            pr = None

        files.append({
            "path": str(f.relative_to(pdir)),
            "commit": commit,
            "author_name": info.get("author_name"),
            "author_email": info.get("author_email"),
            "date": info.get("date"),
            "branches": branches,
            "pr": pr,
            "message": info.get("message"),
        })

    return {
        "migrations_dir": str(pdir.resolve()),
        "repo_root": str(repo_root.resolve()) if repo_root else None,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "files": files,
    }


def write_manifest(manifest: Dict[str, Any], out_path: str) -> None:
    p = Path(out_path)
    p.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def verify_manifest(manifest_path: str, migrations_dir: str, recursive: bool = True, include_untracked: bool = False) -> Dict[str, Any]:
    p = Path(manifest_path)
    if not p.exists():
        raise ValueError(f"Manifest not found: {manifest_path}")
    manifest = json.loads(p.read_text(encoding="utf-8"))
    current = collect_provenance(migrations_dir, recursive=recursive, include_untracked=include_untracked)

    # Build lookup by path
    old_by_path = {f["path"]: f for f in manifest.get("files", [])}
    cur_by_path = {f["path"]: f for f in current.get("files", [])}

    diffs: List[Dict[str, Any]] = []
    for path, old in old_by_path.items():
        cur = cur_by_path.get(path)
        if not cur:
            diffs.append({"path": path, "status": "missing_in_current"})
            continue
        if old.get("commit") != cur.get("commit"):
            diffs.append({"path": path, "status": "commit_changed", "old": old.get("commit"), "new": cur.get("commit")})

    for path in cur_by_path.keys():
        if path not in old_by_path:
            diffs.append({"path": path, "status": "new_file"})

    return {"manifest_path": str(p.resolve()), "migrations_dir": migrations_dir, "diffs": diffs}
