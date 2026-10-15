# CAS Midterm and Assignment Optimization

Developer Names: Shivya Mehta, Harmanpreet Singh Sagar, Vanessa Lai, Anindita Bornomala

Date of project start: September 21, 2026

This project is CAS Midterm and Assignment Optimization.

The documentation for this project is updated on the project's [GitHub page](https://shivyam.github.io/cas-course-optimization/).

## Folder Overview

```text
cas-course-optimization/
├── src/
│   ├── backend/            # FastAPI app (Python)
│   │   ├── app/
│   │   │   ├── main.py     # app setup, CORS, router registration
│   │   │   ├── api/        # one file per group of endpoints
│   │   │   └── db/         # placeholder for schema and migrations
│   │   ├── tests/          # pytest tests
│   │   └── pyproject.toml  # dependencies + Ruff and pytest config
│   └── frontend/           # React + TypeScript app (Vite, Tailwind)
│       ├── src/
│       │   ├── App.tsx     # routes: /, /admin, /instructor
│       │   ├── theme.css   # McMaster colour tokens
│       │   ├── pages/      # one component per page
│       │   └── __tests__/  # Vitest tests
│       └── package.json    # dependencies + npm scripts
├── docs/                   # LaTeX deliverables (SRS, design, plans, ...)
├── refs/                   # reference material, including papers
├── test/                   # template folder (unit tests live next to each app)
├── .env.example            # environment variables template
└── .github/workflows/      # ci.yml (app checks), latex-pages.yml (docs PDFs)
```

## Requirements

| Tool | Version | Check with |
| --- | --- | --- |
| Python | 3.12 or newer | `python --version` |
| Node.js | 22.22.2 or newer (Node 22 LTS) | `node --version` |
| Git | any recent version | `git --version` |

## Setup

For full install and uninstall instructions (including installing Python and Node, and adding or removing dependencies), see [INSTALL.md](INSTALL.md). The quick version follows.

Clone the repo, then copy the environment template from the repo root.

```bash
git clone https://github.com/shivyam/cas-course-optimization.git
cd cas-course-optimization
cp .env.example .env
```

The defaults in `.env` work for local development, so you don't need to edit it. Never commit `.env`.

## Running the Backend

From `src/backend`, create a virtual environment and install the app with its dev tools:

```bash
cd src/backend
python -m venv .venv
```

Activate it (the command depends on your terminal):

| Terminal | Command |
| --- | --- |
| Git Bash | `source .venv/Scripts/activate` |
| PowerShell | `.venv\Scripts\Activate.ps1` |
| Command Prompt | `.venv\Scripts\activate.bat` |
| macOS / Linux | `source .venv/bin/activate` |

Then install and start the server:

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The API runs at <http://127.0.0.1:8000>.

- Health check: <http://127.0.0.1:8000/api/health> returns `{"status": "ok"}`
- Interactive API docs: <http://127.0.0.1:8000/docs>

Opening <http://127.0.0.1:8000>. on its own shows `404 Not Found`. That is expected, since every route lives under `/api`.

## Running the Frontend

In a second terminal, from `src/frontend`:

```bash
cd src/frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. The landing page says **Backend is reachable** when the backend is running. If you see **Backend is not reachable**, start the backend first (see above).

During development, Vite forwards every `/api` request to the backend on port 8000, so the frontend never needs the backend's address.

## Linting and Tests

CI runs these same checks on every pull request (see `.github/workflows/ci.yml`). Run them before you push.

**Backend** (from `src/backend`, with the virtual environment active):

| Task | Command |
| --- | --- |
| Lint | `ruff check .` |
| Fix formatting | `ruff format .` |
| Check formatting | `ruff format --check .` |
| Run tests | `pytest` |

**Frontend** (from `src/frontend`):

| Task | Command |
| --- | --- |
| Lint (ESLint + Prettier check) | `npm run lint` |
| Fix formatting | `npm run format` |
| Run tests | `npm test` |
| Run tests in watch mode | `npm run test:watch` |
| Type-check and build | `npm run build` |

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `.venvScriptsactivate: command not found` | You are in Git Bash. Use forward slashes: `source .venv/Scripts/activate`. |
| `python --version` shows the wrong version after activating | Run the venv's Python directly, e.g. `.venv/Scripts/python -m pytest`. |
| `npm warn EBADENGINE` | Node is too old. Install Node 22.22.2 or newer, open a new terminal, and run `npm ci` again. |
| `npm error code EPERM` during `npm ci` (Windows) | Something has a file in `node_modules` open. Stop any running `npm run dev` and try again. |
| `http proxy error: /api/health ... ECONNREFUSED` | The backend isn't running. Start it with `uvicorn app.main:app --reload`. |
