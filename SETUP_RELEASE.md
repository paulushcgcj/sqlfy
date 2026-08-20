# One-Time Release Setup Guide

> **Who is this for?**
> Anyone setting up the automated release pipeline for the first time.
> You only need to do this once per project. After completing every step here,
> day-to-day releasing is covered by [`RELEASE.md`](RELEASE.md).

---

## What this guide sets up

| What | Why |
|---|---|
| PyPI account + 2FA | Required to own and publish the `sqlfy-cli` package |
| PyPI Trusted Publishing | Lets GitHub Actions publish to PyPI without any stored API key or password |
| GitHub Actions Environment | Scopes the PyPI publish workflow and lets you add human approval gates |
| (Optional) TestPyPI account | Lets you do a full end-to-end dry run against a safe sandbox before touching production PyPI |
| (Optional) Tag protection rule | Prevents accidental tag pushes from anyone other than maintainers |

> ⚠️ **No API keys are created in this guide.**
> The pipeline uses [OIDC Trusted Publishing](https://docs.pypi.org/trusted-publishers/),
> which means PyPI trusts GitHub Actions directly via a short-lived token.
> There is nothing to rotate, nothing to store in GitHub Secrets, and nothing to leak.

---

## Step 1 — Create a PyPI account

> Skip this step if you already have a PyPI account.

1. Open [https://pypi.org/account/register/](https://pypi.org/account/register/) in your browser.
2. Fill in your **name**, **username**, **email address**, and **password**.
   - Your username becomes part of your public PyPI profile URL.
   - Use your work email if this is an organisational project.
3. Click **Create account**.
4. Check your inbox for a verification email from PyPI and click the confirmation link.
5. You are now logged in to PyPI.

---

## Step 2 — Enable Two-Factor Authentication (2FA) on PyPI

> PyPI **requires** 2FA to be active before you can configure Trusted Publishing.
> Do this immediately after creating your account.

1. While logged in to PyPI, click your username in the top-right corner → **Account settings**.
2. Scroll down to the **Two factor authentication** section.
3. Click **Add 2FA with authentication application**.
4. Open any TOTP authenticator app (e.g. Google Authenticator, Authy, 1Password, Bitwarden).
5. Scan the QR code shown on PyPI, or paste the manual key into your authenticator.
6. Enter the 6-digit code from your authenticator to confirm it is working.
7. **Save the recovery codes** shown on the next screen somewhere safe
   (password manager, printed paper — not a sticky note on your monitor).
8. 2FA is now active. Every future PyPI login will require your authenticator code.

---

## Step 3 — (Optional but recommended) Create a TestPyPI account

TestPyPI is an identical but isolated staging environment. Publishing there first
lets you verify your metadata, README rendering, and install command before
touching production PyPI.

1. Open [https://test.pypi.org/account/register/](https://test.pypi.org/account/register/).
2. Repeat Steps 1–2 above. TestPyPI and PyPI are **completely separate** — you need
   a new account even if your usernames are the same.
3. Keep this account handy for smoke-testing new release workflows.

---

## Step 4 — Configure PyPI Trusted Publishing

This is the most important step. It tells PyPI: "Trust GitHub Actions when it
runs the `publish-pypi.yml` workflow in the `paulushcgcj/sqlfy` repository."

### 4a — For a brand-new project (package does not exist on PyPI yet)

PyPI supports **pending trusted publishers** — you can set up the trust *before*
your first publish, so the first automated run just works.

1. Log in to [https://pypi.org](https://pypi.org).
2. Click your username → **Your projects**.
3. You will not see the package yet. That is fine. Click
   **Publishing** in the left sidebar  
   *(direct link: [https://pypi.org/manage/account/publishing/](https://pypi.org/manage/account/publishing/))*.
4. Scroll down to the section **"Add a new pending publisher"**.
5. Fill in the form with **exactly** these values:

   | Field | Value |
   |---|---|
   | PyPI Project Name | `sqlfy-cli` |
   | Owner | `paulushcgcj` |
   | Repository name | `sqlfy` |
   | Workflow name | `publish-pypi.yml` |
   | Environment name | `pypi` |

6. Click **Add**.
7. You will see the pending publisher listed. It becomes active on the first successful publish.

### 4b — For an existing project (package already exists on PyPI)

1. Log in to [https://pypi.org](https://pypi.org).
2. Click your username → **Your projects** → click `sqlfy-cli`.
3. In the left sidebar click **Publishing**.
4. Scroll to **"Add a new publisher"** and fill in the form with **exactly** these values:

   | Field | Value |
   |---|---|
   | Owner | `paulushcgcj` |
   | Repository name | `sqlfy` |
   | Workflow name | `publish-pypi.yml` |
   | Environment name | `pypi` |

5. Click **Add**.

> ⚠️ **The values above must match the workflow file exactly.**
> If you rename `.github/workflows/publish-pypi.yml` or the GitHub Environment,
> you must update the Trusted Publisher entry on PyPI to match.

---

## Step 5 — (Optional) Configure TestPyPI Trusted Publishing

Repeat Step 4 on [https://test.pypi.org](https://test.pypi.org) to enable
dry-run publishing to the sandbox.

Use the same field values as Step 4, but:
- Log in to **test.pypi.org**, not pypi.org.
- If you add a TestPyPI workflow, its filename goes in the **Workflow name** field
  (e.g. `publish-testpypi.yml`).

---

## Step 6 — Create the GitHub Actions Environment

The `publish-pypi.yml` workflow references an environment named **`pypi`**.
GitHub will refuse to run that workflow until this environment exists.

1. Open your repository on GitHub: [https://github.com/paulushcgcj/sqlfy](https://github.com/paulushcgcj/sqlfy).
2. Click **Settings** (top navigation bar, requires repo admin permissions).
3. In the left sidebar, click **Environments**.
4. Click **New environment**.
5. Name it exactly: **`pypi`** (lowercase, no spaces).
6. Click **Configure environment**.

### 6a — (Recommended) Add a required reviewer

Adding a reviewer means no publish can happen without a human clicking "Approve"
in the Actions UI. This gives you a final sanity check before packages go live.

1. Under **Deployment protection rules**, tick **Required reviewers**.
2. Search for and add yourself (or the team/person responsible for releases).
3. Click **Save protection rules**.

### 6b — Environment secrets (none needed)

Do **not** add any secrets to this environment. The OIDC setup in Step 4 is all
that is required. Storing a `PYPI_API_TOKEN` here would be redundant and a
security risk.

---

## Step 7 — (Optional) Protect tags in GitHub

Tag protection prevents anyone other than designated people from pushing
`v*` tags, which would otherwise accidentally trigger the release workflow.

1. In your repository, go to **Settings → Rules → Rulesets**.
2. Click **New ruleset → New branch ruleset**
   *(GitHub uses branch rulesets for tags too)*.
3. Name it `Release tags`.
4. Change **Target** from "Branches" to **"Tags"**.
5. Under **Target tags**, click **Add target → Include by pattern** and enter `v*`.
6. Under **Rules**, enable:
   - ✅ **Restrict deletions** — prevents tag deletion by non-admins
   - ✅ **Restrict creations** — only allowed actors can push new `v*` tags
7. Under **Bypass list**, add yourself and any CI service accounts that need to push tags.
8. Click **Create**.

---

## Step 8 — Verify the setup (dry run)

Before attempting a real release, do a local build and metadata check.

### Prerequisites

Install `uv` if you have not already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# then restart your terminal, or run:
source $HOME/.cargo/env
```

### Local checks

```bash
# Clone the repository
git clone https://github.com/paulushcgcj/sqlfy.git
cd sqlfy

# Install the project in development mode
cd cli
uv sync

# Make sure the CLI entry point works
uv run sqlfy-cli --help

# Build the distribution packages
uv build
# Expected output:
#   dist/sqlfy_cli-<version>.tar.gz
#   dist/sqlfy_cli-<version>-py3-none-any.whl

# Validate metadata (does not upload anything)
uv publish --dry-run
```

If `uv publish --dry-run` exits without errors, the metadata is valid and
the package is ready to publish.

---

## Step 9 — Cut your first release

Once every step above is complete, you are ready. Follow the full process in
[`RELEASE.md`](RELEASE.md).

The very short version:

```bash
# 1. Make sure main is clean and tests pass
git checkout main && git pull

# 2. Set the version in cli/pyproject.toml, then commit
#    (edit the file manually or use sed)
git add cli/pyproject.toml
git commit -m "chore: bump version to 0.20.1"
git push

# 3. Tag and push — this triggers the entire release pipeline
git tag -a v0.20.1 -m "Release v0.20.1"
git push origin v0.20.1
```

After the push, go to **GitHub → Actions** and watch:

1. **Release** workflow — builds binaries and creates the GitHub Release (3–8 min).
2. Once you (or your reviewer) publish the GitHub Release, the
   **Publish to PyPI** workflow fires automatically (~1 min).

The package will then be live at:
`https://pypi.org/project/sqlfy-cli/`

Anyone can install it with:

```bash
pip install sqlfy-cli
# or
uv tool install sqlfy-cli
```

---

## Troubleshooting

### "403 Forbidden" from PyPI during publish

**Cause:** The Trusted Publisher entry on PyPI does not match the workflow.  
**Fix:** Double-check that the **Owner**, **Repository name**, **Workflow name**,
and **Environment name** in the PyPI Trusted Publishing settings are identical
to what is in `.github/workflows/publish-pypi.yml` — including capitalisation.

### "Environment 'pypi' not found"

**Cause:** The GitHub Actions Environment was not created, or was named differently.  
**Fix:** Go to **Settings → Environments** on GitHub and create an environment
named exactly `pypi`.

### Workflow triggers but nothing publishes

**Cause:** The `publish-pypi.yml` workflow triggers on `release: published`.
If you left the GitHub Release as a **draft**, the trigger does not fire.  
**Fix:** Open the draft release on GitHub and click **Publish release**.

### `check-wheel-contents` reports missing files

**Cause:** Non-Python data files (SQL, TOML, JSON, etc.) were not declared in
`pyproject.toml` under `[tool.hatch.build.targets.wheel]`.  
**Fix:** Add the missing includes and rebuild with `uv build`.

### Binary produced by PyInstaller crashes on the target OS

**Cause:** Hidden imports or bundled data files were not declared.  
**Fix:** Add `--hidden-import <module>` or `--add-data <src:dest>` flags to the
PyInstaller command in `.github/workflows/release.yml` and retag.

### "Package name already taken" on PyPI

**Cause:** Someone else owns that name on PyPI.  
**Fix:** Choose a different name in `cli/pyproject.toml → [project] name`, update
the Trusted Publisher entry on PyPI, and re-run the release.

---

## Quick Reference — Key URLs

| Resource | URL |
|---|---|
| PyPI project page | `https://pypi.org/project/sqlfy-cli/` |
| PyPI publishing settings (account) | `https://pypi.org/manage/account/publishing/` |
| PyPI publishing settings (project) | `https://pypi.org/manage/project/sqlfy-cli/settings/publishing/` |
| TestPyPI project page | `https://test.pypi.org/project/sqlfy-cli/` |
| GitHub Actions runs | `https://github.com/paulushcgcj/sqlfy/actions` |
| GitHub Environments | `https://github.com/paulushcgcj/sqlfy/settings/environments` |
| OIDC Trusted Publishing docs | `https://docs.pypi.org/trusted-publishers/` |
| uv documentation | `https://docs.astral.sh/uv/` |
| git-cliff documentation | `https://git-cliff.org/` |
