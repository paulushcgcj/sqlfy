#!/usr/bin/env bash
# cli/install.sh — Install the sqlfy CLI
#
# Strategy (in order):
#   1. pipx  — preferred: manages its own venv, puts `sqlfy` on PATH
#   2. venv  — fallback: creates .venv inside cli/, installs there
#
# Usage:
#   cd cli && bash install.sh          # from the cli/ directory
#   bash cli/install.sh                # from the repo root
#
# After installing with pipx, `sqlfy` is available in every shell.
# After installing with venv, activate with:
#   source cli/.venv/bin/activate

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== sqlfy CLI installer ==="

# ── 1. Try pipx ──────────────────────────────────────────────────────────────
if command -v pipx &>/dev/null; then
  echo "✓ pipx found — installing with pipx"
  pipx install --editable . || pipx install .
  echo ""
  echo "✓ Done. Run: sqlfy --help"
  exit 0
fi

echo "  pipx not found. Checking if it can be installed..."

# Try to install pipx automatically if we have pip available
if command -v pip3 &>/dev/null || command -v pip &>/dev/null; then
  PIP=$(command -v pip3 || command -v pip)
  echo "  Attempting: $PIP install --user pipx"
  if "$PIP" install --user pipx 2>/dev/null; then
    # Ensure ~/.local/bin is on PATH for this session
    export PATH="$HOME/.local/bin:$PATH"
    if command -v pipx &>/dev/null; then
      pipx ensurepath
      echo "✓ pipx installed and sqlfy installed via pipx"
      pipx install .
      echo ""
      echo "✓ Done. Restart your shell or run: source ~/.bashrc"
      echo "  Then: sqlfy --help"
      exit 0
    fi
  fi
fi

# ── 2. Fallback: venv ─────────────────────────────────────────────────────────
echo "  Falling back to venv installation in cli/.venv"

PYTHON=$(command -v python3 || command -v python)
if [[ -z "$PYTHON" ]]; then
  echo "ERROR: python3 not found. Install Python 3.9+ and retry." >&2
  exit 1
fi

VENV_DIR="$SCRIPT_DIR/.venv"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "  Creating virtual environment at $VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
fi

VENV_PIP="$VENV_DIR/bin/pip"
VENV_PYTHON="$VENV_DIR/bin/python"

echo "  Installing sqlfy into venv..."
"$VENV_PIP" install --quiet --upgrade pip
"$VENV_PIP" install .

echo ""
echo "✓ Installed into $VENV_DIR"
echo ""
echo "To use sqlfy, either:"
echo "  1. Activate the venv first:"
echo "       source $VENV_DIR/bin/activate"
echo "       sqlfy --help"
echo ""
echo "  2. Or run directly:"
echo "       $VENV_DIR/bin/sqlfy --help"
echo ""
echo "Tip: install pipx for a cleaner global install:"
echo "  sudo apt install pipx   # Debian/Ubuntu"
echo "  brew install pipx       # macOS"
echo "  Then re-run this script."
