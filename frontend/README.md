# Portfolio frontend

Vue 3, TypeScript, Vite, and Vue Router. Requires Node.js 22.12+ and npm.

```sh
cd frontend
npm ci
npm run dev
```

Validation and production preview:

```sh
npm run typecheck
npm run build
npm run preview
```

The homepage contains the Navbar, Hero, About, Products, Experience, Skills, Projects and Contact sections. `/playground` is a placeholder only. No backend is required.

Global design tokens and responsive styles live in `src/styles/main.css`. Inter is self-hosted in `public/fonts` under the accompanying SIL Open Font License. There are no external font requests.

View CV opens `public/Veljko_Gligorijevic_CV.pdf` in a new tab. The asset URL respects Vite's deployment base path. No social links have been added.

Production hosting must serve `index.html` for frontend routes such as `/playground` (Vue Router uses HTML5 history). Deploy the `dist/` output after building.

Manual checks: desktop and mobile layouts; keyboard menu toggle and Escape; menu closing on selection; homepage section links from both routes; browser back/forward; direct `/playground` refresh; reduced-motion preference; CV opening in a new tab.
