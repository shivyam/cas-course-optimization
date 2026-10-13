# Installation Guide

How to install and uninstall everything needed to run CAS Midterm and Assignment Optimization locally. For running the app, linting, and testing, see [README.md](README.md).

The project has two parts with separate dependencies:

| Part | Folder | Dependencies listed in | Installed into |
| --- | --- | --- | --- |
| Backend (Python) | `src/backend` | `pyproject.toml` | `src/backend/.venv/` |
| Frontend (React) | `src/frontend` | `package.json` and `package-lock.json` | `src/frontend/node_modules/` |

Both install folders stay inside the project and are ignored by git, so removing them removes the project's dependencies completely.

## 1. Install the Prerequisites

| Tool | Version |
| --- | --- |
| Python | 3.12 or newer |
| Node.js | 22.22.2 or newer (includes npm) |
| Git | any recent version |

**Windows** (PowerShell or Git Bash):

```bash
winget install Python.Python.3.12
winget install OpenJS.NodeJS.22
winget install Git.Git
```

Or download the installers from <https://www.python.org/downloads/>, <https://nodejs.org/>, and <https://git-scm.com/>. When installing Python, tick **Add python.exe to PATH**.

**macOS** (with [Homebrew](https://brew.sh/)):

```bash
brew install python@3.12 node@22 git
```

Close and reopen your terminal, then check the versions:

```bash
python --version   # Python 3.12 or newer (on macOS: python3 --version)
node --version     # v22.22.2 or newer
git --version
```

## 2. Get the Code

```bash
git clone https://github.com/shivyam/cas-course-optimization.git
cd cas-course-optimization
cp .env.example .env
```

## 3. Install the Backend Dependencies

From the repo root:

```bash
cd src/backend
python -m venv .venv
```

Activate the virtual environment:

| Terminal | Command |
| --- | --- |
| Git Bash | `source .venv/Scripts/activate` |
| PowerShell | `.venv\Scripts\Activate.ps1` |
| Command Prompt | `.venv\Scripts\activate.bat` |
| macOS / Linux | `source .venv/bin/activate` |

Your prompt should now start with `(.venv)`. Then install:

```bash
pip install -e ".[dev]"
```

This installs the app's dependencies (FastAPI, uvicorn, python-multipart) plus the dev tools (pytest, httpx, Ruff). The `-e` flag makes it an editable install, so code changes take effect without reinstalling.

To install only what is needed to run the app, without the dev tools, use `pip install -e .` instead.

> **Using Anaconda?** Conda's `base` environment can stay active alongside the venv. If `python --version` still shows Anaconda's Python after activating, call the venv directly instead, e.g. `.venv/Scripts/python -m pip install -e ".[dev]"`. Otherwise pip installs into Anaconda.

## 4. Install the Frontend Dependencies

From the repo root:

```bash
cd src/frontend
npm ci
```

`npm ci` installs the exact versions recorded in `package-lock.json`, so every teammate and CI get identical packages. Use it instead of `npm install` when setting up.

## 5. Verify the Installation

```bash
# In src/backend (venv active)
pytest

# In src/frontend
npm test
```

Both should report all tests passing. See [README.md](README.md) for how to start the app.

## Adding or Removing a Dependency

When a feature needs a new package, add it so teammates and CI get it too.

**Backend:**

1. Add the package to `pyproject.toml`: under `dependencies` if the app needs it at runtime, or under `[project.optional-dependencies] dev` if only for development or testing.
2. Run `pip install -e ".[dev]"` again.
3. To remove one, delete it from `pyproject.toml`, then run `pip uninstall <package>`.

**Frontend:**

```bash
npm install <package>          # runtime dependency
npm install -D <package>       # dev-only dependency (tools, test libraries)
npm uninstall <package>        # remove a dependency
```

These commands update both `package.json` and `package-lock.json`. Commit both files.

After pulling changes from teammates, reinstall to pick up their changes: run `pip install -e ".[dev]"` in `src/backend` and `npm ci` in `src/frontend`.

## Uninstalling

### Remove the project's dependencies

Stop any running servers first (`Ctrl+C` in each terminal). On Windows, a running server keeps files locked and the delete fails.

**Backend:** deactivate and delete the virtual environment.

```bash
deactivate                 # if the venv is active
cd src/backend
rm -rf .venv .pytest_cache .ruff_cache
find . -name __pycache__ -type d -exec rm -rf {} +
```

In PowerShell, use `Remove-Item -Recurse -Force .venv, .pytest_cache, .ruff_cache` instead of `rm -rf`.

If you ever installed the backend outside a venv (for example into Anaconda's `base` environment), remove it from there too:

```bash
pip uninstall cas-course-optimization-backend
```

**Frontend:** delete the installed packages and build output.

```bash
cd src/frontend
rm -rf node_modules dist
```

In PowerShell: `Remove-Item -Recurse -Force node_modules, dist`.

To reinstall later, repeat steps 3 and 4.

### Remove the project entirely

Delete the cloned `cas-course-optimization` folder. All dependencies live inside it, so nothing else is left behind (apart from pip's and npm's shared download caches, which other projects also use).

### Uninstall the prerequisites (optional)

Only do this if no other project on your computer needs them.

**Windows:**

```bash
winget uninstall Python.Python.3.12
winget uninstall OpenJS.NodeJS.22
winget uninstall Git.Git
```

Or use **Settings > Apps > Installed apps**.

**macOS:**

```bash
brew uninstall python@3.12 node@22 git
```
