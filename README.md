# Developer Portfolio & Playground

A portfolio website with professional experience, skills and projects, alongside a Playground for a card-based technical interview game.

## Stack and implementation status

- **Implemented:** responsive portfolio built with Vue 3, TypeScript and Vite, including product cards, contact details and a PDF CV viewer.
- **Planned:** a card-based technical interview game in the Playground. The current Playground page is a placeholder; gameplay and backend services are not implemented.
- **Backend foundation:** FastAPI application with environment settings and a tested health endpoint, managed with uv and Python 3.14.
- **Domain foundation:** immutable Python domain entities with focused invariant tests.
- **Planned:** pure Python game rules and tests, followed by PostgreSQL for game definitions, Redis for temporary game-session state and Docker Compose.

## Run locally

Requires Node.js **22.12 or later** and npm.

```sh
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite.

## Run the backend

Requires Python **3.14** and [uv](https://docs.astral.sh/uv/).

```sh
cd backend
uv sync --locked
cp .env.example .env
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
npm run typecheck
npm run build
npm run preview
```

The build includes TypeScript checks and produces `frontend/dist/`. Preview serves the production build locally.

For deployment, serve `frontend/dist/` with an SPA fallback to `index.html` for routes such as `/playground`. Serve existing assets directly, including `Veljko_Gligorijevic_CV.pdf`. For subdirectory hosting, configure Vite's `base` before building.

## Project layout

- `frontend/` — portfolio interface, routing and public assets.
- `backend/` — FastAPI foundation, environment settings and endpoint tests.
- [Domain](docs/DOMAIN.md) — entities and invariants.
- [Game design](docs/GAME_DESIGN.md) — gameplay and balancing rules.
- [Architecture](docs/ARCH.md) — persistence, API and security decisions.

Read the design documents before changing gameplay or architecture. Some implementation details remain open in the architecture document.

## License

See [LICENSE](LICENSE).
