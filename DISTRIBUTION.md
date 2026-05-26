# SQLfy Distribution Guide

Complete guide for building and sharing sqlfy with users who don't want to build from source.

---

## 🎯 Distribution Options

### Option 1: Python Wheel (CLI) ⚡ Fastest
**Best for:** Users with Python 3.11+ installed

**Build:**
```bash
cd cli
pip install build
python -m build
```

**Output:** `cli/dist/sqlfy-0.20.0-py3-none-any.whl`

**How user installs:**
```bash
pip install sqlfy-0.20.0-py3-none-any.whl
sqlfy --help
```

**Pros:** Small file size (~119 KB), fast  
**Cons:** Requires Python 3.11+

---

### Option 2: Standalone Binary (CLI) 🎁 Most User-Friendly
**Best for:** Non-technical users, no Python needed

**Build:**
```bash
cd cli
bash build-binary.sh
```

**Output:** `cli/dist/sqlfy-binary/sqlfy` (~15-20 MB)

**How user installs:**
```bash
# macOS/Linux:
chmod +x sqlfy
./sqlfy --help

# Add to PATH (optional):
sudo mv sqlfy /usr/local/bin/
```

**Pros:** Zero dependencies, works anywhere  
**Cons:** Larger file size

**Cross-platform builds:**
- Build on macOS → works on macOS
- Build on Linux → works on Linux  
- Build on Windows → works on Windows

---

### Option 3: Desktop App (Tauri) 🖥️ Full GUI
**Best for:** Users who prefer graphical interface

**Build:**
```bash
cd app
npm install
npm run build
npm run tauri build
```

**Output (macOS):**
- DMG installer: `app/src-tauri/target/release/bundle/dmg/sqlfy_0.1.0_aarch64.dmg`
- App bundle: `app/src-tauri/target/release/bundle/macos/sqlfy.app`

**Output (Windows):**
- MSI installer: `app/src-tauri/target/release/bundle/msi/sqlfy_0.1.0_x64_en-US.msi`
- Setup.exe: `app/src-tauri/target/release/bundle/nsis/sqlfy_0.1.0_x64-setup.exe`

**Output (Linux):**
- AppImage: `app/src-tauri/target/release/bundle/appimage/sqlfy_0.1.0_amd64.AppImage`
- deb package: `app/src-tauri/target/release/bundle/deb/sqlfy_0.1.0_amd64.deb`

**How user installs:**
- macOS: Open DMG, drag to Applications
- Windows: Run MSI installer
- Linux: `chmod +x *.AppImage && ./sqlfy*.AppImage` or `dpkg -i *.deb`

**Pros:** Professional installers, auto-updates possible, GUI + CLI hybrid  
**Cons:** Large file size (50-100 MB), requires building on each platform

---

## 📦 Quick Reference

| Option | Size | User Setup | Cross-Platform | GUI |
|--------|------|------------|----------------|-----|
| Wheel | ~120 KB | `pip install` | ✅ | ❌ |
| Binary | ~15 MB | `chmod +x && ./sqlfy` | ⚠️ Build per OS | ❌ |
| Tauri App | ~50 MB | Double-click installer | ⚠️ Build per OS | ✅ |

---

## 🚀 Recommended Workflow

**For a single user on your platform:**
1. Build wheel: `cd cli && python -m build`
2. Send `cli/dist/sqlfy-0.20.0-py3-none-any.whl`
3. They install: `pip install sqlfy-0.20.0-py3-none-any.whl`

**For non-technical users:**
1. Build binary: `cd cli && bash build-binary.sh`
2. Send `cli/dist/sqlfy-binary/sqlfy` (or zip it)
3. They run: `chmod +x sqlfy && ./sqlfy --help`

**For GUI users:**
1. Build app: `cd app && npm run tauri build`
2. Send platform-specific installer from `app/src-tauri/target/release/bundle/`
3. They double-click and install

---

## 🌐 Publishing to Package Managers (Future)

### PyPI (for pip install sqlfy)
```bash
cd cli
pip install twine
python -m build
twine upload dist/*
# Users install: pip install sqlfy
```

### Homebrew (macOS)
```bash
# Create formula at: https://github.com/Homebrew/homebrew-core
# Users install: brew install sqlfy
```

### GitHub Releases
```bash
# Upload wheel, binary, and DMG/MSI to:
# https://github.com/paulushcgcj/sqlfy/releases
# Tag as v0.20.0
```

---

## 🔧 Troubleshooting

**PyInstaller: "command not found"**
```bash
pip3 install pyinstaller
```

**Tauri build fails:**
```bash
# Install Rust if missing
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install system dependencies (Linux)
sudo apt install libwebkit2gtk-4.0-dev libssl-dev libgtk-3-dev
```

**Binary doesn't run on another machine:**
- Make sure you're building on the same OS (macOS binary won't work on Linux)
- Use `pyinstaller --onefile --hidden-import=...` to include all dependencies

---

## 📝 Version Bumping

Before releasing, update versions:
- CLI: `cli/pyproject.toml` → `version = "0.20.0"`
- App: `app/package.json` → `version = "0.15.0"`
- App: `app/src-tauri/tauri.conf.json` → `version = "0.1.0"`

Then rebuild all artifacts.
