# Backend

FastAPI foundation and framework-independent domain entities. Requires Python **3.14** and [uv](https://docs.astral.sh/uv/).

Run commands from `backend/`:

```sh
uv sync --locked
cp .env.example .env
uv run uvicorn app.main:app --reload
```

The `.env` copy is optional: the application has working defaults. Environment
variables override `.env` values. Settings are validated at application startup;
restart the server after changing them.

| Setting | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Developer Portfolio & Playground API` | Application title in API documentation |
| `APP_DEBUG` | `false` | Enable detailed debug errors for local development only |

Open <http://127.0.0.1:8000/health> for `{"status":"ok"}` or
<http://127.0.0.1:8000/docs> for interactive API documentation.
The health endpoint checks that the application responds; it does not check external services.
Uvicorn provides server and request logging using its default configuration.

## Validation

```sh
uv run pytest
uv run python -m compileall -q app tests
uv run python -c "from app.main import app; print(app.title)"
```

The health test uses FastAPI's in-process test client; no running server is required.
No static type checker is configured in this phase.

## Files

- `pyproject.toml` defines dependencies, Python compatibility and pytest configuration.
- `uv.lock` pins dependency versions and belongs in version control.
- `.python-version` selects Python 3.14 for uv.
- `.env.example` documents configuration; local `.env` files are ignored by Git.
- `app/main.py` defines the FastAPI application, health response and route.
- `app/config.py` loads and validates settings.
- `app/__init__.py` marks the application package.
- `tests/test_health.py` checks the health response.

The `app/domain/` package contains immutable questions, player state, effects, cards
and session snapshots. Focused invariant tests live in `tests/domain/`.
Run them separately with `uv run pytest tests/domain`.

`app/application/` coordinates StartGame, SubmitAnswer, NextCard and GetGameState
through async repository protocols and injected clock/token/factory dependencies.
Safe immutable views keep domain objects and unanswered correct-answer IDs private.
Application tests use in-memory fakes: `uv run pytest tests/application`.
See `docs/ARCH.md` for CAS retries, TTL policies and token contracts.
The PostgreSQL catalog adapter is implemented. Redis adapters, production token
handling and gameplay HTTP endpoints remain future work.

## PostgreSQL content database

From the repository root: `docker compose up -d --wait`. Compose credentials are
for local development. Only PostgreSQL is containerized in this phase.

From `backend/`:

```sh
uv sync --locked
uv run alembic upgrade head
uv run alembic current
uv run alembic check
# Revert the content schema (deletes content):
uv run alembic downgrade base
```

`DATABASE_URL` overrides the local default without an `APP_` prefix. Both
`postgresql://` and `postgresql+psycopg://` use async Psycopg 3. Importing the app
neither opens connections nor creates tables. Python generates UUID defaults.

Integration tests create and remove a uniquely named schema. Use a dedicated test
database with CREATE SCHEMA permission:

```sh
TEST_DATABASE_URL=postgresql+psycopg://playground:playground@localhost:5432/playground uv run pytest tests/integration -q
uv run pytest
```

Without `TEST_DATABASE_URL`, database tests skip. They cover migration round trips,
metadata consistency, constraints, foreign keys and question deletion cascades.
Catalog loading, starter seeds and association-aware card generation are implemented.

## Catalog integration and starter data

After `uv run alembic upgrade head`, run:

```sh
uv run python -m app.persistence.seed
```

This inserts five questions, twenty options, three templates, eighteen effects and
twenty-four associations using stable UUIDs. Repeated runs preserve existing rows
and insert missing seed rows; they do not reset edits or reactivate content. Conflicts
with other rows' unique codes/positions fail and roll back the seed transaction.

Construct `SQLAlchemyCatalogRepository(create_session_factory(engine))` from
`app.persistence.catalog` to supply the existing application use cases. Each load
uses a read-only repeatable-read transaction, excludes inactive questions/templates,
and validates content before returning immutable domain catalogs. Effects have no
active flag; template associations constrain their eligibility. Invalid content raises
`CatalogFailure`. FastAPI wiring remains outside this phase.

```sh
uv run pytest tests/domain tests/application tests/persistence
TEST_DATABASE_URL=postgresql+psycopg://playground:playground@localhost:5432/playground uv run pytest tests/integration -q
```

Integration tests use isolated temporary schemas, including corruption scenarios
that remove constraints only inside those schemas. Use a dedicated test database.
