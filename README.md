# Choremate

Choremate is a local web application for managing shared household chores between two people.

The application helps a couple plan weekly responsibilities, track completed work, and compare planned and actual workload using effort points.

## Course

This project is part of the [AI Dev Tools Zoomcamp](https://aishippingblog.com/p/ai-native-development-specifications), a course focused on specification-driven development and AI-assisted software engineering.

## Stack

- Python
- Django
- SQLite
- HTMX
- pytest and pytest-django
- uv for dependency management

## Project status

The project is currently in the foundation phase. The product scope is documented in [`_docs/plan.md`](_docs/plan.md), and the implementation backlog is tracked primarily in [GitHub issues](https://github.com/cgbarreto/choremate/issues).

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
uv sync --locked
```

Run the test suite:

```bash
uv run pytest
```

Run the development server:

```bash
uv run python manage.py migrate
uv run python manage.py runserver
```

The default configuration is suitable for local development and uses SQLite.
Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, or `DJANGO_ALLOWED_HOSTS` when a
different local configuration is needed.

## Documentation

- [`_docs/plan.md`](_docs/plan.md) — product scope and MVP requirements
- [`_docs/process.md`](_docs/process.md) — development workflow
- [`_docs/agents.md`](_docs/agents.md) — project commands and agent guidance
