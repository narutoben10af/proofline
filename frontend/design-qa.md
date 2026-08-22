# MagicFin product-shell design QA

## Source visual truth

- User hand-drawn information architecture: persistent product navigation, company/period header, compact files, one dominant trend, summary/review priorities, report access, and assistant utility.
- User chat/chart/sources reference: interaction anatomy only—dismissible conversation, analytical canvas, and on-demand citation evidence. Its dark palette, branding, trading language, and proprietary details were not copied.
- Approved Editorial Ledger reference: `docs/screenshots/editorial-ledger-reference.jpg` supplies the warm palette, strong typography, fine rules, and evidence-first hierarchy.
- Superdesign draft `64b3b7fd-d4e4-4222-9fde-bb3f9d7e6578` was used as an additional implementation check, not as a replacement for the user references.

## Fidelity decisions

- The compact left rail follows the sketch but removes overlapping dashboard destinations. Company has one visual center: a source-linked revenue trend with an accessible table.
- Four source cards expose filename/type, period or date, provenance, validation status, anchor, and review action. They are subordinate to the trend rather than equal-weight dashboard tiles.
- The factual summary, review priorities, evidence flag, export state, and cited assistant stay secondary to evidence review. “Recommendation,” investment rating, forecasts, and causal language are absent.
- The assistant opens as a dismissible panel; citations open a nested drawer and deep-link to focusable Review Desk evidence. `Calculated result` and `Assistant analysis` remain visibly distinct.
- MagicFin’s brief “magic” language appears in the five deterministic Run Magic stages. Motion clarifies state changes and is disabled by the system preference or the session Settings control.

## Browser and responsive checks

The implementation was compared at desktop and 320px widths against both user references and the Editorial Ledger reference. The desktop canvas preserves the sketch’s hierarchy without becoming a cramped three-column terminal. On mobile, navigation becomes an accessible off-canvas panel and the assistant occupies the available viewport.

Checks include:

- no horizontal overflow at 320px;
- primary actions remain visible in single-column layouts and at 400% zoom equivalent;
- the assistant composer remains in normal sticky flow rather than covering conversation evidence;
- mobile navigation and nested drawers support Escape, focus trapping/restoration, and background `inert` isolation;
- source anchors receive focus after citation navigation and workbook evidence opens when directly linked;
- no external font request, console error, fixed-height workspace shell, or hidden primary action.

## Trust and error review

- File handling accepts only the exact verified demo pair and states that bytes are not read, uploaded, or retained.
- History is labeled static fixture activity and never implies persistence.
- JSON works; PDF remains adapter-backed and truthfully unavailable unless a server endpoint returns ready.
- Assistant provider-not-configured, offline, loading, error/retry, and verified demo states are explicit. There is no Gemini/Gemma label or browser key.
- Profile/sign-in/storage/privacy copy describes only implemented local behavior. Deletion produces a narrow session receipt and does not claim server deletion.
- Every verdict includes text/icons; the dark ochre warning token passes normal-text contrast; rules are not the sole semantic boundary.

The automated suite covers 18 critical route, state, export, focus, reduced-motion, fixture, deletion, and brand interactions. Production and Sites builds are verified separately.

**final result: passed**
