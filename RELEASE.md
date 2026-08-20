# Release Process

This project uses [Conventional Commits](https://www.conventionalcommits.org/)
and [git-cliff](https://github.com/orhun/git-cliff) for automated changelogs.
Releases are driven by Git tags.

---

## Commit Convention (required)

Every commit merged to `main` **must** follow the pattern:

```
<type>[optional scope]: <short description>

[optional body]

[optional footer — use BREAKING CHANGE: <description> for breaking changes]
```

| Type | Meaning | Bumps version |
|---|---|---|
| `feat` | New user-facing feature | minor |
| `fix` | Bug fix | patch |
| `perf` | Performance improvement | patch |
| `refactor` | Code restructure, no behaviour change | — |
| `docs` | Documentation only | — |
| `test` | Test changes only | — |
| `ci` | CI/CD changes | — |
| `chore` | Maintenance (deps, config) | — |
| `feat!` or `BREAKING CHANGE:` footer | Breaking API/CLI change | **major** |

---

## Versioning Policy

This project follows [Semantic Versioning 2.0](https://semver.org/):

- `MAJOR.MINOR.PATCH`
- Patch: backwards-compatible bug fixes
- Minor: new backwards-compatible features
- Major: breaking changes

---

## Prerequisites (one-time setup)

### 1. Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install `git-cliff` locally (for local changelog preview)

```bash
uv tool install git-cliff
```

### 3. Configure PyPI Trusted Publishing (first release only)

1. Log in to [pypi.org](https://pypi.org) and go to
   **Your projects → sqlfy-cli → Publishing**.
2. Add a **Trusted Publisher** with:
   - Publisher: GitHub Actions
   - Owner: `paulushcgcj`
   - Repository: `sqlfy`
   - Workflow filename: `publish-pypi.yml`
   - Environment name: `pypi`
3. In GitHub, create an Actions **Environment** named `pypi` under
   **Settings → Environments**.
   Add an approval gate if you want a human sign-off before publishing.

---

## Release Checklist

### Step 1 — Verify `main` is green

```bash
git checkout main && git pull
```

Check that the latest CI run on `main` is passing.

### Step 2 — Preview the changelog

```bash
# Preview what will be in the release notes
git cliff --latest --strip header
```

Review the output. If commits are missing the conventional prefix, this is the
last chance to rebase and fix them before tagging.

### Step 3 — Decide the next version

Use the table above to determine whether the bump is patch, minor, or major.

Current version is in `cli/pyproject.toml` → `[project] version`.

### Step 4 — Bump the version

Edit `cli/pyproject.toml` and set the new version string, then commit:

```bash
# Example: bumping to 1.2.0
sed -i 's/^version = .*/version = "1.2.0"/' cli/pyproject.toml
git add cli/pyproject.toml
git commit -m "chore: bump version to 1.2.0"
git push
```

### Step 5 — Tag the release

```bash
git tag -a v1.2.0 -m "Release v1.2.0"
git push origin v1.2.0
```

Pushing the tag triggers `release.yml`, which will:

- Generate the changelog from conventional commits between the previous tag
  and `v1.2.0`
- Build standalone binaries for Linux, macOS, and Windows via PyInstaller
- Build the Python wheel and source distribution via `uv build`
- Create a GitHub Release, populate the body with the changelog, and attach
  all artifacts

### Step 6 — Monitor the Release workflow

Go to **GitHub → Actions → Release** and watch the run.
If any build job fails, fix the issue, delete the tag locally and remotely,
then re-tag:

```bash
git tag -d v1.2.0
git push --delete origin v1.2.0
# fix the issue, commit, then re-tag
```

### Step 7 — Publish the GitHub Release

The Release workflow creates the release automatically.
If you want to **review before publishing**, change `draft: false` to
`draft: true` in `release.yml`, then manually publish from the GitHub UI.

### Step 8 — Automatic PyPI publish

Publishing the GitHub Release triggers `publish-pypi.yml`.
The workflow builds the package fresh with `uv build` and publishes via OIDC —
no tokens required.

Monitor progress at **Actions → Publish to PyPI**.

Once complete, the new version will be live at:
`https://pypi.org/project/sqlfy-cli/`

Users can install it immediately:

```bash
pip install sqlfy-cli
# or
uv tool install sqlfy-cli
```

---

## Publishing to PyPI Without a GitHub Release

If you need to publish to PyPI independently of GitHub (e.g. a hotfix that
doesn't need a binary release):

```bash
cd cli
uv build
uv publish
# uv will prompt for credentials or use OIDC if running in CI
```

Or to publish to TestPyPI first:

```bash
cd cli
uv build
uv publish --index https://test.pypi.org/legacy/
```

---

## Rolling Back a Bad Release

PyPI does **not** allow deleting released versions. Instead:

1. Yank the bad version on PyPI:
   Go to **PyPI → project → [version] → Options → Yank this release**.
   Yanked versions are hidden from searches but still installable by explicit pin.
2. Fix the bug, bump the patch version, and release again.

---

## Pre-releases

Tag with a pre-release suffix to publish a pre-release to PyPI:

```bash
git tag -a v2.0.0-rc.1 -m "Release candidate v2.0.0-rc.1"
git push origin v2.0.0-rc.1
```

The `release.yml` workflow detects `-rc`, `-beta`, and `-alpha` suffixes and
marks the GitHub Release as a **pre-release** automatically.

On PyPI the version will appear as `2.0.0rc1` and will only be installed if
the user explicitly requests it:

```bash
pip install "sqlfy-cli==2.0.0rc1"
# or
pip install --pre sqlfy-cli
```
