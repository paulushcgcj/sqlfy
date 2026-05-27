#!/usr/bin/env bash
# Quick verification script for sqlfy installation

set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  sqlfy CLI Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if sqlfy is available
if command -v sqlfy &> /dev/null; then
    echo "✅ sqlfy is installed and in PATH"
    echo "   Location: $(which sqlfy)"
else
    echo "❌ sqlfy not found in PATH"
    echo ""
    echo "Run ./install.sh to install"
    exit 1
fi

echo ""
echo "🧪 Testing commands..."

# Test each major command
COMMANDS=(
    "dump --help"
    "chunks --help"
    "graph --help"
    "insights --help"
    "query --help"
    "validate --help"
    "lint --help"
    "cache info"
)

FAILED=0

for cmd in "${COMMANDS[@]}"; do
    if sqlfy $cmd > /dev/null 2>&1; then
        echo "  ✓ sqlfy $cmd"
    else
        echo "  ✗ sqlfy $cmd"
        FAILED=$((FAILED + 1))
    fi
done

echo ""

if [ $FAILED -eq 0 ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ All checks passed!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Try it:"
    echo "  sqlfy dump samples/ --format yaml"
    exit 0
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ❌ $FAILED command(s) failed"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 1
fi
