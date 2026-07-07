"""Git hook management commands for sqlfy."""
from __future__ import annotations

import os
import sys
from pathlib import Path


MARKER_START = "# sqlfy-hook-start"
MARKER_END = "# sqlfy-hook-end"

HOOK_BLOCK = f"""{MARKER_START}
# Added by sqlfy hooks install — do not edit this block manually.
_SQLFY_CHANGED=$(git diff --cached --name-only --diff-filter=ACM | grep '\\\\.sql$' || true)
if [ -n "$_SQLFY_CHANGED" ]; then
  echo "[sqlfy] Running lint + safety on staged SQL files..."
  sqlfy lint "$(git rev-parse --show-toplevel)" --dialect oracle
  _LINT_EXIT=$?
  sqlfy safety "$(git rev-parse --show-toplevel)" --dialect oracle
  _SAFETY_EXIT=$?
  if [ $_LINT_EXIT -ne 0 ] || [ $_SAFETY_EXIT -ne 0 ]; then
    echo "[sqlfy] Pre-commit check FAILED. Fix issues or use --no-verify to bypass."
    exit 1
  fi
fi
{MARKER_END}
"""


def _find_git_root(start_path: Path) -> Path:
    """Walk upward from start_path looking for .git directory.
    
    Raises ValueError if no .git directory is found.
    """
    current = start_path.resolve()
    while True:
        git_dir = current / ".git"
        if git_dir.exists():
            return current
        parent = current.parent
        if parent == current:
            # Reached filesystem root
            break
        current = parent
    raise ValueError(f"No .git directory found starting from {start_path}")


def _get_hook_file(git_root: Path) -> Path:
    """Return the path to the pre-commit hook file."""
    return git_root / ".git" / "hooks" / "pre-commit"


def _detect_dialect(git_root: Path) -> str:
    """Auto-detect dialect from manifest.json if present, fallback to oracle."""
    manifest_path = git_root / "sqlfy-out" / "manifest.json"
    if manifest_path.exists():
        try:
            import json
            with open(manifest_path, encoding="utf-8") as f:
                data = json.load(f)
                dialect = data.get("dialect", "oracle")
                return dialect if dialect else "oracle"
        except Exception:
            pass
    return "oracle"


def cmd_hooks_install(*, path: str = ".", **kwargs) -> int:
    """Install sqlfy pre-commit hook into the git repository at path."""
    start_path = Path(path)
    try:
        git_root = _find_git_root(start_path)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    hooks_dir = git_root / ".git" / "hooks"
    hook_file = _get_hook_file(git_root)
    
    # Ensure hooks directory exists
    hooks_dir.mkdir(parents=True, exist_ok=True)
    
    # Read existing content
    existing_content = ""
    if hook_file.exists():
        existing_content = hook_file.read_text(encoding="utf-8")
    
    # Check if already installed
    if MARKER_START in existing_content:
        print("Already installed.")
        return 0
    
    # Detect dialect for the hook script
    dialect = _detect_dialect(git_root)
    
    # Build the hook block with detected dialect
    hook_block = f"""{MARKER_START}
# Added by sqlfy hooks install — do not edit this block manually.
_SQLFY_CHANGED=$(git diff --cached --name-only --diff-filter=ACM | grep '\\\\.sql$' || true)
if [ -n "$_SQLFY_CHANGED" ]; then
  echo "[sqlfy] Running lint + safety on staged SQL files..."
  sqlfy lint "$(git rev-parse --show-toplevel)" --dialect {dialect}
  _LINT_EXIT=$?
  sqlfy safety "$(git rev-parse --show-toplevel)" --dialect {dialect}
  _SAFETY_EXIT=$?
  if [ $_LINT_EXIT -ne 0 ] || [ $_SAFETY_EXIT -ne 0 ]; then
    echo "[sqlfy] Pre-commit check FAILED. Fix issues or use --no-verify to bypass."
    exit 1
  fi
fi
{MARKER_END}
"""
    
    # Append the hook block
    new_content = existing_content + hook_block
    hook_file.write_text(new_content, encoding="utf-8")
    
    # Set executable permissions
    os.chmod(hook_file, 0o755)
    
    print(f"Installed sqlfy pre-commit hook at {hook_file}.")
    return 0


def cmd_hooks_uninstall(*, path: str = ".", **kwargs) -> int:
    """Remove sqlfy pre-commit hook from the git repository at path."""
    start_path = Path(path)
    try:
        git_root = _find_git_root(start_path)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    hook_file = _get_hook_file(git_root)
    
    # Read existing content
    if not hook_file.exists():
        print("Not installed.")
        return 0
    
    existing_content = hook_file.read_text(encoding="utf-8")
    
    # Check if marker is present
    if MARKER_START not in existing_content:
        print("Not installed.")
        return 0
    
    # Strip the marker block (including markers)
    lines = existing_content.splitlines(keepends=True)
    new_lines = []
    in_block = False
    for line in lines:
        stripped = line.rstrip("\n\r")
        if MARKER_START in stripped:
            in_block = True
            continue
        if MARKER_END in stripped:
            in_block = False
            continue
        if not in_block:
            new_lines.append(line)
    
    new_content = "".join(new_lines)
    
    # If remaining content is only blank lines/shebangs, optionally delete
    remaining_stripped = new_content.strip()
    if not remaining_stripped or remaining_stripped.startswith("#!"):
        # Keep shebang if it's the only thing, otherwise delete
        if not remaining_stripped:
            hook_file.unlink()
        else:
            hook_file.write_text(new_content, encoding="utf-8")
    else:
        hook_file.write_text(new_content, encoding="utf-8")
    
    print(f"Removed sqlfy hook from {hook_file}.")
    return 0


def cmd_hooks_status(*, path: str = ".", **kwargs) -> int:
    """Check and report whether sqlfy hooks are installed."""
    start_path = Path(path)
    try:
        git_root = _find_git_root(start_path)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    hook_file = _get_hook_file(git_root)
    
    if not hook_file.exists():
        print(f"Not installed (hook file does not exist: {hook_file})")
        return 0
    
    content = hook_file.read_text(encoding="utf-8")
    if MARKER_START in content:
        print(f"Installed at {hook_file}")
    else:
        print(f"Not installed (marker not found in {hook_file})")
    
    return 0
