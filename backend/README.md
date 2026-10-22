# Backend

Minimal FastAPI foundation. Requires Python **3.14** and [uv](https://docs.astral.sh/uv/).

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

Next: implement and unit-test the pure Python domain model and game rules,
resolving the relevant open decisions in the design documents first.
PostgreSQL and Redis integration follow that work.
