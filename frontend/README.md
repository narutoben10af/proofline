# Proofline frontend

Editorial Ledger implementation of the Proofline Review Desk. It is a React/Vite prototype centered on one Visual Verdict, a four-step proof trail, progressively disclosed evidence, explicit human review, and honest deletion/cached/error states.

## Run

```bash
pnpm install
pnpm dev --host 0.0.0.0 --port 4173 --strictPort
```

Production and verification:

```bash
pnpm test
pnpm run build
pnpm run test:sites
```

## Mock-data boundary

`src/mock-contract.js` is the stable adapter boundary for the forthcoming backend session/finding contract. The bundled values are a human-verified fictional demo fixture; no issuer PDF or workbook is included, uploaded, or parsed. UI components consume only the normalized `reviewFixture` returned by `adaptReviewContract`.

The live Review Desk exports a JSON evidence package; it does not print the DOM or claim to produce a reviewed PDF.

## Screenshots

- `docs/screenshots/review-desk-desktop.jpg` — 1440 × 1024 review state.
- `docs/screenshots/review-desk-320.jpg` — 320px responsive viewport/400%-zoom proxy.
- `docs/screenshots/design-comparison.jpg` — approved concept and browser implementation in one comparison frame.
