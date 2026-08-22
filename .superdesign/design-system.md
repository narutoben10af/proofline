# MagicFin Editorial Ledger design system

## Product and screen

MagicFin helps a financial reviewer compare company-report claims with cited figures. The Review Desk remains the evidence source of truth, while a friendly product shell adds Home, Company, Files & Upload, Source Library, History, Reports, account/settings entries, privacy/legal information, and a provider-neutral cited assistant. The Company workspace is not an equal-weight dashboard: one dominant trend and its accessible table lead; compact source cards, factual summary, review priorities, evidence flags, and exports support it.

## Visual direction

The approved direction is **Editorial Ledger with a small amount of magic**: an annual-report reading desk with the precision of a financial workpaper and the friendliness of a polished modern product. It draws general inspiration from Beautiful UI's exact interface primitives, Transitions.dev's continuity and purposeful state feedback, and Mobbin's mature review patterns without reproducing proprietary screens.

- Base surface: warm paper `#f7f4ee`; elevated reading surface `#fffdf8`; secondary wash `#efeae1`.
- Ink: `#191815`; secondary ink `#625f58`; fine rule `#d8d2c8`.
- Contradicted: vermilion `#b52d24` with pale wash `#f6e2de`.
- Supported: moss `#2f704c` with pale wash `#e3eee6`.
- Uncertain: ochre `#9a6512` with pale wash `#f4ead4`.
- Display typography: freely available Source Serif 4 or Georgia fallback; compact, confident, sentence case.
- UI/data typography: freely available Inter or system sans fallback; tabular figures for metrics.
- Corners are 4–10px, never pill-heavy. A faint warm glow may clarify the primary action or active state, but evidence surfaces remain flat and legible. Shadows are subtle; rules and surface tint come first.
- Desktop uses a compact navigation rail and broad editorial workspace. Tablet collapses the rail; mobile uses a top bar and one reading column with no horizontal scroll.

## Components and hierarchy

- Shell navigation: Home, Company, Files & Upload, Source Library, History, Review Desk, and Reports; profile/settings/sign-in/privacy/legal live in a compact utility section.
- Company header: entity, exact period, fixture/cache status, Run Magic action, and clear file/upload entry.
- Source cards: filename/type, period or date, provenance/validation state, and explicit open/review action; never anonymous File 1–4 placeholders.
- Trend: one visually dominant company trend plus an always-available semantic table. Chart values, units, periods, and source anchors must match.
- Assistant: dismissible side panel on desktop and full-screen sheet on mobile; cited source drawer opens on demand. `Calculated result` is distinct from `Assistant analysis`.
- Header: quiet product wordmark and review context; deletion is visible but secondary.
- Summary: one grouped horizontal strip with Supported, Uncertain, and Contradicted counts; not three floating cards.
- Visual Verdict: narrative value and deterministic value are large, balanced figures. The discrepancy sits between them and owns the contradiction color.
- Proof trail: numbered vertical sequence for claim, cited inputs, deterministic formula, and result. Source labels remain attached to each step.
- Evidence: PDF excerpt and spreadsheet cells are closed by default and reveal in place. Avoid permanent split panes on small screens.
- Review Desk trend: at most one three-period chart, subordinate to its discrepancy. Company may use one primary multi-period trend only.
- Actions: Confirm finding and Mark for investigation are explicit human decisions. Loading, empty, error, and deletion states preserve the same calm editorial layout.

## Motion and accessibility

- Animate route continuity, panel/drawer entry, evidence disclosure, chart reveal, upload/session stages, and review confirmation at roughly 140–220ms ease-out. Motion must clarify hierarchy, remain interruptible, and never delay evidence access.
- Under `prefers-reduced-motion: reduce`, disable transitions and smooth scrolling.
- Maintain WCAG AA contrast, visible 2px focus outlines, logical DOM/tab order, semantic buttons, headings, tables, and live regions for state changes.
- Never encode verdict state by color alone; always pair color with label and icon from the selected icon library.

## Explicit exclusions

No trading terminal, stock search, market notifications, investment advice, buy/sell language, causal claims, model picker, raw model reasoning, decorative spectacle, fabricated security/privacy claims, browser API keys, or issuer documents/assets. The assistant may only show verified scripted fixture content until a server provider is configured. Mock content must be labeled at the code and UI boundaries.
