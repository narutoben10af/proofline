# MagicFin frontend

MagicFin is the drawing-driven product shell around the merged Editorial Review Desk. It uses the existing warm Editorial Ledger system while adding the complete, responsive product flow requested in the hand sketch: Home, Company, Files & Upload, Source Library, History, Review Desk, Reports, Profile, Settings, Sign in, Privacy, Legal, and a cited assistant.

## Run and verify

```bash
pnpm install --frozen-lockfile
pnpm dev --host 0.0.0.0 --port 4173 --strictPort
```

```bash
pnpm test
pnpm run build
pnpm run test:sites
```

The production build is written to `dist/`; `build` also prepares the existing Sites worker package.

## Live and fixture boundaries

- `src/product-contract.js` is the replaceable product/session/assistant/report adapter boundary.
- `src/mock-contract.js` remains the normalized Review Desk finding contract.
- When Supabase Auth and `VITE_API_BASE_URL` are configured, Files & Upload requires a verified user session and sends the selected PDF/XLSX to the authenticated server pipeline. The returned cited analysis replaces the dashboard, source, Review Desk, and report data; a failed real upload never falls back to the fixture.
- Without that configuration, the local process-only review boundary remains available for development. “Try sample data” is an explicit separate action and never reads selected bytes.
- The assistant is a provider-neutral scripted fixture. Free-form answers are disabled until a server-side provider is configured; no API key belongs in the browser bundle.
- The reviewed JSON export works locally. PDF export exposes loading/error/ready adapter states but defaults to not configured; it never prints the live DOM as a substitute.
- History remains explicitly static demo activity. Sign-in and persistence describe their actual configured state rather than imitating success.

## Interaction and accessibility coverage

The interaction suite covers all primary and secondary routes, Run Magic stages, exact PDF/XLSX fixture handling, JSON and adapter-backed PDF export states, Settings effects, system reduced motion, assistant/source focus isolation, mobile navigation trapping/Escape/restoration, cited hash navigation, browser history, deletion, and brand copy.

The shell uses semantic headings and tables, visible focus, a skip link, non-color status labels, live regions, focus restoration, `inert` background isolation, responsive single-column states, and both CSS and session-level reduced-motion behavior.

## Existing Review Desk evidence

The original Review Desk captures remain under `docs/screenshots/`. No issuer PDF or workbook is committed.
