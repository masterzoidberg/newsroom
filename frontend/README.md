# Frontend

The standalone frontend is an implemented React + TypeScript workspace compiled
to static assets and served from the same origin as FastAPI. It includes the
authenticated responsive workspace, evidence/provenance views, monitoring,
research, reports/alerts, operator settings, and the installable PWA shell with
offline fallback behavior. Do not reuse the Hermes Dashboard SDK; v1
interaction patterns remain reference material only.

Run these checks from this directory:

```powershell
npm run lint
npm run typecheck
npm run build
```

`lint` and `typecheck` currently run TypeScript's no-emit check; `build` runs
that check and the Vite production build. The frontend supports Phase 29
evidence and acceptance work, but browser/PWA behavior, phone access, and
installed-system qualification remain separate release gates.
