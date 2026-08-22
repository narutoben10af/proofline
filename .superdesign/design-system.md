# Proofline Editorial Ledger design system

## Product and screen

Proofline Review Desk helps a financial analyst verify whether a narrative claim agrees with cited figures. The primary screen is a focused review brief, not a dashboard. Its hierarchy is fixed: compact three-state summary, one dominant Visual Verdict, four-step proof trail, progressively disclosed PDF and spreadsheet evidence, then human review and deletion controls.

## Visual direction

The approved direction is **Editorial Ledger**: an annual-report reading desk with the precision of a financial workpaper. It draws general inspiration from Beautiful UI's exact interface primitives, Transitions.dev's continuity and purposeful state feedback, and Mobbin's mature review patterns without reproducing proprietary screens.

- Base surface: warm paper `#f7f4ee`; elevated reading surface `#fffdf8`; secondary wash `#efeae1`.
- Ink: `#191815`; secondary ink `#625f58`; fine rule `#d8d2c8`.
- Contradicted: vermilion `#b52d24` with pale wash `#f6e2de`.
- Supported: moss `#2f704c` with pale wash `#e3eee6`.
- Uncertain: ochre `#9a6512` with pale wash `#f4ead4`.
- Display typography: freely available Source Serif 4 or Georgia fallback; compact, confident, sentence case.
- UI/data typography: freely available Inter or system sans fallback; tabular figures for metrics.
- Corners are 2–6px, never pill-heavy. No gradients. Shadows are nearly absent; use rules and surface tint first.
- Desktop uses an 8/4 editorial grid: broad verdict/proof column and narrow evidence rail. Tablet and mobile collapse to one reading column.

## Components and hierarchy

- Header: quiet product wordmark and review context; deletion is visible but secondary.
- Summary: one grouped horizontal strip with Supported, Uncertain, and Contradicted counts; not three floating cards.
- Visual Verdict: narrative value and deterministic value are large, balanced figures. The discrepancy sits between them and owns the contradiction color.
- Proof trail: numbered vertical sequence for claim, cited inputs, deterministic formula, and result. Source labels remain attached to each step.
- Evidence: PDF excerpt and spreadsheet cells are closed by default and reveal in place. Avoid permanent split panes on small screens.
- Trend: at most one three-period line chart; it is subordinate to the discrepancy.
- Actions: Confirm finding and Mark for investigation are explicit human decisions. Loading, empty, error, and deletion states preserve the same calm editorial layout.

## Motion and accessibility

- Only animate disclosure height/opacity and status confirmation, 140–180ms ease-out.
- Under `prefers-reduced-motion: reduce`, disable transitions and smooth scrolling.
- Maintain WCAG AA contrast, visible 2px focus outlines, logical DOM/tab order, semantic buttons, headings, tables, and live regions for state changes.
- Never encode verdict state by color alone; always pair color with label and icon from the selected icon library.

## Explicit exclusions

No dashboard navigation, chatbot, model picker, raw model reasoning, decorative motion, fabricated security/privacy claims, or issuer documents/assets. Mock content must be labeled demo data at the code boundary.
