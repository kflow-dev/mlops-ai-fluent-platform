# mlops-ai-fluent-platform

Repository for two related Python surfaces:

- `aifluent/`: an MVP multi-agent coding assistant CLI and FastAPI service.
- `example_project/catchme/`: a fuller example app for local activity capture, retrieval, and web visualization.

This README focuses on how to run and test what is actually present in this checkout.

The main `aifluent` package now also includes a migrated memory subsystem derived from `catchme` storage and explorer patterns.

## Repository Layout

```text
.
├── config/
│   └── models.yaml
├── requirements.txt
├── aifluent/
│   ├── api.py
│   ├── cli.py
│   └── core/
└── example_project/
    ├── pyproject.toml
    ├── README.md
    └── catchme/
```

## Prerequisites

- Python 3.11+ for `catchme`
- Python 3.9+ is sufficient for the current `aifluent` files, but using one modern interpreter for the whole repo is simpler
- macOS or Windows if you want to exercise the native recorder features in `catchme`

## Install

### AIFluent

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy the environment template and adjust it if you want a different model config path:

```bash
cp .env.example .env
```

`aifluent` expects a model config at `config/models.yaml` by default. You can override it with `AIFLUENT_MODEL_CONFIG` in `.env`.

### CatchMe

`catchme` is packaged from `example_project/` and has its own dependencies:

```bash
cd example_project
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Platform notes:

- macOS: grant Accessibility, Input Monitoring, and Screen Recording permissions before testing `catchme awake`
- Windows: run with Administrator privileges for global input monitoring

## Run

### AIFluent CLI

From the repository root:

```bash
PYTHONPATH=. python -m aifluent.cli --help
PYTHONPATH=. python -m aifluent.cli analyze --repo .
PYTHONPATH=. python -m aifluent.cli refactor --file aifluent/cli.py
PYTHONPATH=. python -m aifluent.cli test --repo .
PYTHONPATH=. python -m aifluent.cli memory-add --kind note --data '{"text":"reviewed design"}'
PYTHONPATH=. python -m aifluent.cli memory-search --query reviewed
PYTHONPATH=. python -m aifluent.cli memory-stats
```

Notes:

- Use `python -m aifluent.cli`, not `python aifluent/cli.py`, so package imports resolve correctly.
- `refactor` requires `--file`.
- The CLI now validates repo and file paths before model loading starts.
- Memory commands persist and search event data under `AIFLUENT_DATA_ROOT` or the default `data/` directory.

### AIFluent API

From the repository root:

```bash
uvicorn aifluent.api:app --reload
```

The API initializes models at import time, so `config/models.yaml` must be valid before startup.

Migrated memory endpoints are also available:

- `GET /memory`
- `GET /memory/api/events`
- `GET /memory/api/search?q=...`
- `GET /memory/api/stats`
- `GET /memory/api/timeline`
- `POST /memory/api/events`

### CatchMe

From `example_project/`:

```bash
catchme --help
catchme init
catchme awake
catchme web --host 127.0.0.1 --port 8765
catchme ask -- "What did I work on today?"
```

You can also run it as a module:

```bash
python -m catchme --help
```

### VS Code

The repository includes workspace files in `.vscode/` for common AIFluent flows.

1. Open the repository in VS Code.
2. Create and activate a repo-local virtual environment if needed:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

3. Run `Python: Select Interpreter` and choose `${workspaceFolder}/.venv/bin/python`.
4. Run `Tasks: Run Task` for:

- `aifluent: cli help`
- `aifluent: api`
- `aifluent: inline refactor current file`

5. Open `Run and Debug` for:

- `AIFluent API`
- `AIFluent CLI Help`

The inline refactor task uses the currently open file path and calls `aifluent.vs_code.inline_refactor.suggest_inline_refactor(...)`.
The tasks and launch profiles load `${workspaceFolder}/.env`, so `AIFLUENT_MODEL_CONFIG` can be changed without editing the workspace JSON files.

## Test Instructions

### 1. Quick CLI smoke tests

These verify that help text, argument parsing, and basic entry points work without exercising native recorders.

### AIFluent smoke tests

From the repository root:

```bash
PYTHONPATH=. python -m aifluent.cli --help
PYTHONPATH=. python -m aifluent.cli refactor
PYTHONPATH=. python -m aifluent.cli analyze --repo .
```

Expected results:

- `--help` prints subcommands and examples
- `refactor` without `--file` exits with a usage error
- `analyze --repo .` starts normal CLI execution if `config/models.yaml` is valid

### CatchMe smoke tests

From `example_project/`:

```bash
python -m catchme --help
python -m catchme web --port abc
```

Expected results:

- `--help` prints the command list and examples
- invalid port values fail with a parser error instead of a raw traceback

### 2. Automated tests for CatchMe

From `example_project/`:

```bash
pytest
```

Run a single file when narrowing failures:

```bash
pytest catchme/tests/test_store.py -v
pytest catchme/tests/test_engine.py -v
```

Recommended local quality check:

```bash
ruff check catchme/
ruff format --check catchme/
pytest
```

### 3. Manual app testing for CatchMe

Use this when you want to verify the actual user flow rather than just unit tests.

### Recording flow

1. In terminal A, start the recorder:

```bash
catchme awake
```

2. Interact with a few apps for 1 to 2 minutes:

- switch windows
- type some text
- copy text to the clipboard

3. In terminal B, inspect runtime state:

```bash
catchme ram
catchme disk
```

4. Ask a retrieval question:

```bash
catchme ask -- "What apps did I use in the last few minutes?"
```

### Web flow

1. Start the web server:

```bash
catchme web
```

2. Open `http://127.0.0.1:8765`

3. Verify:

- the dashboard loads
- events appear after `catchme awake` has run
- chat queries return a streamed response

## Troubleshooting

- `ModuleNotFoundError: aifluent`: run `PYTHONPATH=. python -m aifluent.cli ...` from the repo root
- `Model config not found`: create or fix `config/models.yaml`
- `catchme web --port abc` error: expected, the parser now validates port input
- `Quartz` or other native module import errors: install `catchme` from `example_project/` with its package dependencies
- `ask` returns no useful data: make sure `catchme awake` has been running long enough to record events

## Additional Docs

- See `example_project/README.md` for deeper `catchme` documentation.
