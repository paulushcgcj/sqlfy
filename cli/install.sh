#!/usr/bin/env bash
set -euo pipefail

# sqlfy CLI installer
# Detects OS, builds package, and installs globally

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  sqlfy CLI Installer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Detect OS
OS="unknown"
case "$(uname -s)" in
    Linux*)     OS="linux";;
    Darwin*)    OS="macos";;
    CYGWIN*|MINGW*|MSYS*) OS="windows";;
    *)          OS="unknown";;
esac

echo "📍 Detected OS: $OS"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv is not installed"
    echo ""
    echo "Install uv first:"
    echo "  macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  Windows: powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\""
    exit 1
fi

echo "✓ uv found: $(uv --version)"

# Get script directory (handles symlinks)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "🔧 Building package..."
uv build

# Find the built wheel
WHEEL=$(find dist -name "sqlfy-*.whl" -type f | sort -V | tail -n 1)

if [ -z "$WHEEL" ]; then
    echo "❌ Error: No wheel file found in dist/"
    exit 1
fi

echo "✓ Built: $WHEEL"

echo ""
echo "📦 Installing globally..."

# Try uv tool install first (recommended)
if uv tool install --help &> /dev/null 2>&1; then
    echo "  Using uv tool install (installs to isolated environment)..."
    uv tool install --force --from "$WHEEL" sqlfy
    INSTALL_METHOD="uv-tool"
else
    # Fallback to pip install --user
    echo "  Using pip install --user (installs to user site-packages)..."
    uv pip install --user --force-reinstall "$WHEEL"
    INSTALL_METHOD="pip-user"
fi

echo "✓ Installation complete"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Installation Successful!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if sqlfy is in PATH
if command -v sqlfy &> /dev/null; then
    echo "✅ sqlfy is ready to use!"
    echo ""
    echo "  $ sqlfy --version"
    sqlfy dump --help 2>&1 | head -1 || echo "  sqlfy CLI"
else
    echo "⚠️  sqlfy installed but not found in PATH"
    echo ""
    
    if [ "$INSTALL_METHOD" = "uv-tool" ]; then
        # uv tool installs to ~/.local/bin
        BIN_DIR="$HOME/.local/bin"
    else
        # pip --user installs to different locations per OS
        case "$OS" in
            linux)
                BIN_DIR="$HOME/.local/bin"
                ;;
            macos)
                PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
                BIN_DIR="$HOME/Library/Python/${PYTHON_VERSION}/bin"
                ;;
            windows)
                BIN_DIR="$HOME/AppData/Local/Programs/Python/Python3*/Scripts"
                ;;
            *)
                BIN_DIR="$HOME/.local/bin"
                ;;
        esac
    fi
    
    echo "Add this to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
    echo ""
    echo "  export PATH=\"$BIN_DIR:\$PATH\""
    echo ""
    echo "Then reload your shell:"
    echo "  source ~/.bashrc  # or source ~/.zshrc"
fi

echo ""
echo "Try it:"
echo "  sqlfy dump samples/ --format yaml"
echo "  sqlfy insights samples/"
echo "  sqlfy --help"
