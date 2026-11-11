# Portfolio frontend

Vue 3, TypeScript, Vite, and Vue Router. Requires Node.js 22.12+ and npm.

```sh
cd frontend
npm ci
npm run dev
```

Validation and production preview:

```sh
npm test
npm run typecheck
npm run build
npm run preview
```

The homepage contains the Navbar, Hero, About, Products, Experience, Skills, Projects and Contact sections. The portfolio works without a backend. `/playground` starts/restores games using the
FastAPI backend and seeded PostgreSQL/Redis services (see `backend/README.md`).

Global design tokens and responsive styles live in `src/styles/main.css`. Inter is self-hosted in `public/fonts` under the accompanying SIL Open Font License. There are no external font requests.

View CV opens `public/Veljko_Gligorijevic_CV.pdf` in a new tab. The asset URL respects Vite's deployment base path. No social links have been added.

Production hosting must serve `index.html` for frontend routes such as `/playground` (Vue Router uses HTML5 history). Deploy the `dist/` output after building.

Manual checks: desktop and mobile layouts; keyboard menu toggle and Escape; menu closing on selection; homepage section links from both routes; browser back/forward; direct `/playground` refresh; reduced-motion preference; CV opening in a new tab.

## Playground integration

Run FastAPI on `127.0.0.1:8000`; Vite proxies `/api` there. Open
`http://localhost:5173/playground` (or the URL printed by Vite). Start Game displays
the first question, four read-only options, HP, score and remaining time. There are
no answer or next-card actions in this phase.

The API client uses explicit TypeScript models and checks incoming response shapes.
Only `{game_id, session_token}` is saved in tab-scoped `sessionStorage`, allowing a
page refresh to restore the same session. The token is sent only in `X-Game-Token`,
never a URL. Storage is cleared after unavailable/finished sessions; temporary errors
retain it for Retry session. If storage is blocked, the page continues in memory
with a notice. Storage is readable by same-origin JavaScript: avoid unsafe HTML and
untrusted scripts. This is anonymous session access, not account authentication.

The local countdown uses `performance.now()` and conservatively subtracts request
duration from the returned milliseconds. At zero it requests authoritative state;
there is no periodic polling. Failed confirmation offers a manual retry rather than
an automatic retry loop. A finished session receives only a short message, not a
full results screen.

Vitest/jsdom tests run with `npm test`. With the backend and Vite already running,
the optional Chromium smoke test verifies start, refresh and mobile overflow:

```sh
npx playwright install chromium
npm run test:browser
```

Minimal Linux installations may also need `npx playwright install-deps chromium`
(system packages), or an official Playwright container matching the installed version.
Set `PLAYGROUND_SMOKE_URL` if Vite runs at another origin. Use local development
services: the test creates a session that expires through the normal Redis TTL.
Traces are disabled to avoid recording credentials. Browser artifacts are ignored.

Production must route `/api/` to FastAPI before the SPA fallback, using the same
HTTPS origin. No wildcard CORS is configured. Deployment itself remains out of scope.
