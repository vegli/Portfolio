# AGENTS.md

## Project Stack

- Backend: FastAPI (Python)
- Frontend: Vue 3 + TypeScript + Vite
- Database: PostgreSQL
- Temporary game-session state: Redis (required for the agreed Playground session design; not a general-purpose cache)
- Containerization: Docker / Docker Compose
- Package management:
  - Python: uv
  - Frontend: npm
- Version control: Git

## Project Context

This project is a personal developer portfolio and a practical software engineering project.

The application consists of:
- A public portfolio/CV website presenting my experience, skills, and projects.
- An interactive Playground containing a small card-based technical interview game.
- Interview topics include Backend Engineering, Databases, Networking, System Design, Security, DDD, and Performance.

The project should demonstrate practical skills in backend development, frontend development, API design, databases, testing, architecture, containerization, CI/CD, and deployment.

This should be treated as a real software engineering project rather than a tutorial or demo application.

## Project Documentation

Before changing gameplay behavior or architecture, read the relevant documentation:

- `docs/DOMAIN.md` — domain entities, constraints and invariants.
- `docs/GAME_DESIGN.md` — gameplay flows, use cases and balancing rules.
- `docs/ARCH.md` — system architecture, persistence, REST API and security decisions.

Treat agreed decisions in these documents as the source of truth. If documentation conflicts or appears outdated, point out the discrepancy before making assumptions. Discuss changes to agreed rules before implementing them, and update the relevant documentation alongside approved behavioral changes.

## Engineering Principles

- Prefer simple, maintainable solutions over unnecessary abstractions.
- Avoid overengineering and premature optimization.
- Follow existing patterns and conventions before introducing new ones.
- Introduce new abstractions only when they solve an actual problem.
- Prefer incremental changes and working vertical slices.
- Explain significant architectural or dependency decisions before implementing them.
- Do not add new dependencies without a clear reason.
- When multiple reasonable approaches exist, briefly explain the trade-offs.

## Working With the Developer

- Do not immediately implement large or architectural changes.
- For significant changes, first explain the proposed approach and wait for approval.
- Keep explanations concise, but explain non-obvious decisions.
- Prefer helping the developer understand the implementation rather than hiding complexity behind generated code.

## Coding Standards

- Keep the route handlers thin (as much as the situation allows it, but don't avoid writing longer handlers if it seems they would clarify the code better and reduce general cognitive complexity).
- Do NOT use caching unless explicitly told to, or when the situation absolutely requires it. Yes, we should treat this project as a 'regular' software project, but we are not aiming for the overkill here.
- Redis is explicitly approved for temporary `GameSession` state, **not** as a blanket approval to cache arbitrary data.
- Validate external inputs at system boundaries.
- Reduce the comments to a minimum, unless they clarify the situation. If you find anything that isn’t obvious from the code itself, put it into a comment.
- Reuse existing domain services before creating a parallel implementation.
- Keep domain rules independent of FastAPI routes, ORM models, and Redis serialization when practical.

## Playground Implementation Guardrails

- The backend is authoritative for questions, answer evaluation, effects, score, HP, streak, and remaining time. The Vue frontend handles presentation, animations and interactions.
- Never expose the correct answer in responses before the corresponding submitted answer has been evaluated. Do not send answer explanations in the MVP.
- A game begins with 100 HP and 60 seconds; no pause is available. The first card is drawn automatically; subsequent cards require `Next Card`.
- The frontend may show a local countdown, but the backend validates time on every gameplay action and on state refresh. No periodic polling is required for the MVP.
- `GameSession` is stored as a minimal JSON snapshot in Redis under `game:session:{session_id}`. Static questions, answer options, templates and effect definitions live in PostgreSQL and are initially populated by idempotent seed scripts.
- The proposed Redis TTL is 15 minutes after a successful permitted state-changing action; reads do not refresh the TTL. TTL is cleanup, not the game timer.
- Use Redis optimistic concurrency (`WATCH` / `MULTI` / `EXEC`) or an equivalently safe atomic approach for state-changing operations; prevent double answer scoring and duplicate card draws.
- Anonymous sessions are protected by a cryptographically random game token. The frontend sends it with subsequent requests, and Redis stores only a verifier/hash, not the raw token. Treat the token as a secret.
- No permanent game-session history, leaderboard, user accounts or persistent results are required for the MVP. `Play Again` creates a new session through the same start-game use case.
- Game-over priority: if HP and time both reach zero after processing the same accepted answer, record `HP_DEPLETED`. If the authoritative timer expired before the answer was accepted, reject evaluation and finish with `TIME_EXPIRED`.
- Follow `docs/DOMAIN.md` and `docs/GAME_DESIGN.md` for card rarity, allowed effect rarities, balancing budgets and draw rules; do not duplicate such configuration in unrelated modules.

## REST API Conventions

- Use the agreed conceptual endpoints: `POST /api/v1/games`, `GET /api/v1/games/{id}`, `POST /api/v1/games/{id}/answers`, and `POST /api/v1/games/{id}/cards/next`.
- There is no separate public `restart` or `finish` endpoint for the MVP. Game-over is server-driven.
- Validate session ownership/token, the current phase, current card ID and answer option ID on relevant requests.
- Keep request and response schemas explicit and avoid leaking server-only fields.
- Use consistent structured API errors and appropriate HTTP statuses; refer to `docs/ARCH.md` for the detailed API contract.
- Treat endpoint payloads, status codes and headers in architecture documentation as the agreed design where finalized; flag any unresolved details rather than silently inventing a contract.

## Testing Expectations

- Write focused unit tests for game rules, particularly answer evaluation, streak scoring, effect constraints, timer boundaries and game-over priority.
- Add integration tests for API behavior and Redis concurrency where appropriate.
- Check unauthorized access, invalid phases and duplicate submissions.
- Do not claim tests were run unless they were actually executed.

## GIT workflow

- Do not commit, push, merge, or force-push without approval.
- Do not include unrelated formatting changes.
- Keep migrations and generated files in the same change as the code that requires them.
- Summarize user-visible behavior and validation in the pull request.

## Completion Report

After completing a task, report:

- Summary of changes
- Modified files
- Important implementation decisions
- Commands executed
- Test/build results
- Known limitations or remaining issues
