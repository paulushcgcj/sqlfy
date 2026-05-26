#!/usr/bin/env bash
# Build standalone sqlfy binary using PyInstaller
# Usage: bash build-binary.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Building sqlfy standalone binary ==="

# Install PyInstaller if not available
if ! command -v pyinstaller &>/dev/null; then
  echo "Installing PyInstaller..."
  pip3 install pyinstaller
fi

# Clean previous builds
rm -rf build/ dist/sqlfy dist/sqlfy-binary/

# Install package first (so imports work)
echo "Installing package..."
pip3 install -e . -q

# Build single-file executable
echo "Building binary..."
pyinstaller \
  --name sqlfy \
  --onefile \
  --console \
  --noconfirm \
  --clean \
  --collect-all sqlfy \
  --collect-all sqlglot \
  --hidden-import=sqlglot \
  --hidden-import=sqlglot.dialects.oracle \
  --hidden-import=networkx \
  pyinstaller_entry.py

# Create distribution directory
mkdir -p dist/sqlfy-binary
cp dist/sqlfy dist/sqlfy-binary/
echo "✓ Binary created: dist/sqlfy-binary/sqlfy"

# Test it
echo ""
echo "Testing binary..."
dist/sqlfy-binary/sqlfy --help | head -5

echo ""
echo "=== Build complete ==="
echo "Share the entire dist/sqlfy-binary/ folder"
echo "Users can run: ./sqlfy <command>"
