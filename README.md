# Developer Portfolio & Playground

A portfolio website with professional experience, skills and projects, alongside a Playground for a card-based technical interview game.

## Stack and implementation status

- **Portfolio:** responsive Vue 3 + TypeScript + Vite interface with product cards, contact details and a PDF CV link.
- **Playground:** Start Game and secure refresh restoration work through FastAPI, PostgreSQL and Redis. Questions/options, HP, score and an authoritative-state-based countdown are displayed; answering and next-card interactions are deferred.
- **Backend:** pure Python game rules, application use cases, catalog/session adapters, secure tokens, migrations and idempotent seeds. Python 3.14 and uv.
- **Local services:** PostgreSQL 17 and Redis 8 through Docker Compose.

## Run locally

Requires Node.js **22.12 or later** and npm.

```sh
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite.

## Run the backend

Requires Python **3.14** and [uv](https://docs.astral.sh/uv/). Start the services
from the repository root with `docker compose up -d --wait`.

```sh
cd backend
uv sync --locked
cp .env.example .env
uv run alembic upgrade head
uv run python -m app.persistence.seed
uv run uvicorn app.main:app --reload
```

Copying `.env.example` is optional; defaults work without it. Environment variables
override `.env` values. Open <http://127.0.0.1:8000/health> for the health status
and <http://127.0.0.1:8000/docs> for API documentation.

Run tests from `backend/` with `uv run pytest`.
See [backend instructions](backend/README.md) for settings and import checks.

## Validate and build

Run from `frontend/`:

```sh
npm test
npm run typecheck
npm run build
npm run preview
```

The build includes TypeScript checks and produces `frontend/dist/`. Preview serves the production build locally.

Vite proxies `/api` to `http://127.0.0.1:8000` during local development.
Open `/playground` in the frontend to start a game.

For deployment, route `/api/` to FastAPI over the same HTTPS origin and serve `frontend/dist/` with an SPA fallback to `index.html` for routes such as `/playground`. Serve existing assets directly, including `Veljko_Gligorijevic_CV.pdf`. For subdirectory hosting, configure Vite's `base` before building.

## Project layout

- `frontend/` — portfolio interface, routing and public assets.
- `backend/` — FastAPI transport, application/domain layers, persistence, migrations, seeds and tests.
- [Domain](docs/DOMAIN.md) — entities and invariants.
- [Game design](docs/GAME_DESIGN.md) — gameplay and balancing rules.
- [Architecture](docs/ARCH.md) — persistence, API and security decisions.

Read the design documents before changing gameplay or architecture. Some implementation details remain open in the architecture document.

## License

See [LICENSE](LICENSE).
