#!/usr/bin/env bash
set -euo pipefail

REPO="paulushcgcj/sqlfy"
BINARY="sqlfy"
INSTALL_DIR="/usr/local/bin"

OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "$OS" in
  linux)  OS_KEY="linux" ;;
  darwin) OS_KEY="macos" ;;
  *)      echo "Unsupported OS: $OS" && exit 1 ;;
esac

case "$ARCH" in
  x86_64)           ARCH_KEY="x86_64" ;;
  arm64 | aarch64)  ARCH_KEY="aarch64" ;;
  *)                echo "Unsupported arch: $ARCH" && exit 1 ;;
esac

TARGET="${OS_KEY}-${ARCH_KEY}"

VERSION=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
  | grep '"tag_name"' \
  | sed 's/.*"tag_name": "\(.*\)".*/\1/')

URL="https://github.com/${REPO}/releases/download/${VERSION}/${BINARY}-${TARGET}"

echo "→ Installing ${BINARY} ${VERSION} (${TARGET})"

TMP=$(mktemp)
curl -fsSL "$URL" -o "$TMP"
chmod +x "$TMP"

if [ -w "$INSTALL_DIR" ]; then
  mv "$TMP" "${INSTALL_DIR}/${BINARY}"
elif command -v sudo &>/dev/null; then
  sudo mv "$TMP" "${INSTALL_DIR}/${BINARY}"
else
  mkdir -p "$HOME/.local/bin"
  mv "$TMP" "$HOME/.local/bin/${BINARY}"
  echo "⚠ Installed to ~/.local/bin — make sure it's in your PATH"
fi

echo "✓ Done. Run: ${BINARY} --help"
