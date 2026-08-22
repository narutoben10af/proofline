# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## MagicFin product-shell decisions

- The user-facing product name is exactly `MagicFin`. Do not rename the repository or rewrite historical records.
- Preserve the warm Editorial Ledger palette and evidence-first typography, while making the shell friendly, modern, and lightly magical rather than corporate-first.
- Treat the supplied hand sketch as the information-architecture source of truth and the supplied chat/chart/source screenshot only as an interaction-anatomy reference. Never copy its dark palette, branding, trading language, or proprietary details.
- The product shell includes Home, Company, Files & Upload, Source Library, History, Review Desk, Reports, profile, settings, sign-in, privacy/data controls, and accessible legal information.
- Company has one dominant trend with a semantic table, compact truthful source cards, factual summary, review priorities, evidence flags, export states, and a dismissible cited assistant.
- `Run Magic` means deterministic fixture stages: validate sources, extract claims, calculate metrics, link evidence, and flag discrepancies. Motion is brief, reduced-motion-safe, and never delays evidence access.
- The assistant is provider-neutral and subordinate to evidence. Label deterministic output `Calculated result` and fixture prose `Assistant analysis`; expose citations and honest not-configured/offline/error/demo states. Never ship a browser API key or imply a live provider.
- Backend, authentication, storage, PDF export, and persistence gaps must be visible as demo/disabled states. Do not claim uploads, accounts, deletion, privacy, or persistence that the prototype does not implement.
