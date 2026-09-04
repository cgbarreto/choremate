# Choremate

Choremate is a local web application for managing shared household chores between two people.

The application helps a couple plan weekly responsibilities, track completed work, and compare planned and actual workload using effort points.

## Stack

- Python
- Django
- SQLite
- HTMX
- pytest and pytest-django
- uv for dependency management

## Project status

The project is currently in the setup and architecture phase. The product scope is documented in [`_docs/plan.md`](_docs/plan.md).

## Requirements

- Python 3.14 or newer
- `uv`

The project uses a local virtual environment and does not require installing project dependencies into the system Python environment.

## Development setup

Create the virtual environment if it does not exist:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install and synchronize dependencies:

```bash
uv sync
```

Run the test suite:

```bash
uv run pytest
```

## Documentation

- [`_docs/plan.md`](_docs/plan.md) — product scope and MVP requirements
- [`_docs/process.md`](_docs/process.md) — development workflow
- [`_docs/agents.md`](_docs/agents.md) — project commands and agent guidance
