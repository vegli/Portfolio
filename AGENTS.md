## Project Stack

- Backend: FastAPI (Python)
- Frontend: Vue 3 + TypeScript + Vite
- Database: PostgreSQL
- Cache: Redis (when needed)
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
- Validate external inputs at system boundaries.
- Reduce the comments to a minimum, unless they clarify the situation. If you find anything that isn’t obvious from the code itself, put it into a comment.
- Reuse existing domain services before creating a parallel implementation.

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