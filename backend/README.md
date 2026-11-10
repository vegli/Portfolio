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
PostgreSQL catalog loading, Redis session storage and secure token handling are
implemented. Gameplay HTTP endpoints and application lifespan wiring remain future work.

## PostgreSQL content database

From the repository root: `docker compose up -d --wait`. Compose credentials are
for local development. PostgreSQL and Redis are containerized; the backend runs locally.

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

## Redis sessions and local services

From the repository root:

```sh
docker compose up -d --wait
docker compose ps
docker compose exec postgres pg_isready -U playground -d playground
docker compose exec redis redis-cli ping
```

Compose runs official Redis 8 on `127.0.0.1:6379`. Redis persistence is disabled
(`save ""`, `appendonly no`) because sessions are temporary; restarting Redis loses
sessions. PostgreSQL retains its existing named volume. Local Redis has no password
and must remain bound to localhost. Configure authentication/TLS through `REDIS_URL`
for a separately managed deployment.

If port 6379 is occupied by the older standalone container, inspect it first:

```sh
docker ps -a --filter name=playground-redis
docker inspect playground-redis --format '{{json .Mounts}} {{json .Config.Cmd}}'
```

Do not remove containers or volumes. If the old container can safely be stopped
(after checking its data/persistence requirements), run `docker stop playground-redis`,
then start Compose. Stopping preserves the container and volumes, but volatile Redis
data may be lost. Alternatively, keep it running and change the Compose Redis host
port to an unused port such as 6380, updating `REDIS_URL` and `TEST_REDIS_URL` to match.
No application code automatically stops or removes existing containers.

`REDIS_URL` defaults to `redis://localhost:6379/0` without the `APP_` prefix.
The session TTL is fixed at the agreed 900 seconds, separate from the game timer.
Construct the adapters together with the existing catalog repository:

```python
from app.persistence.redis_sessions import create_redis_client, RedisSessionRepository
from app.security.session_tokens import SecureSessionTokens

redis = create_redis_client(settings.redis_url)
sessions = RedisSessionRepository(redis, catalogs.load_card_content)
tokens = SecureSessionTokens()
# Inject sessions and tokens into existing application use cases.
# The owner must await redis.aclose() and engine.dispose() at shutdown.
```

Reads hydrate referenced PostgreSQL questions/templates, including inactive content
already in a session. Do not edit/delete referenced static definitions while sessions
are live. Rolled effects and answer feedback are preserved, never regenerated.
Malformed/unsupported snapshots or missing definitions raise `PersistenceFailure`;
missing/expired Redis keys return `None`. Tokens are cryptographically generated;
only SHA-256 verifiers enter storage.

Run all tests against local development services from `backend/`:

```sh
TEST_DATABASE_URL=postgresql+psycopg://playground:playground@localhost:5432/playground \
TEST_REDIS_URL=redis://localhost:6379/0 uv run pytest -q
```

Without the corresponding test URL, integration tests skip. Redis tests use unique
UUID keys and delete only their own keys; they never flush the database. PostgreSQL
tests use isolated schemas. Real Redis tests cover WATCH conflicts, simultaneous
answers/draws, expiry during a transaction, absolute TTL preservation/renewal, and
malformed snapshots. Tests set expiration timestamps directly instead of sleeping.
