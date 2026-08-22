# Component inventory

The current frontend is a small React app with no external component library beyond Phosphor Icons. Existing reusable component candidates live inline in `frontend/src/App.jsx`:

- `Header`: product wordmark, current review context, delete control.
- `StatusSummary`: supported/uncertain/contradicted finding counts.
- `VisualVerdict`: dominant claimed-versus-calculated comparison.
- `ProofTrail`: four-step claim → inputs → formula → result sequence.
- `EvidenceDisclosure`: accessible disclosure button and evidence region.
- `EvidenceRail`: quoted PDF claim and semantic spreadsheet evidence table.
- `ReviewActions`: JSON export and human decision controls.
- `DeleteDialog`: modal deletion confirmation with Escape and focus restoration supplied by its parent.

New shell primitives should remain dependency-light and use semantic HTML: `AppShell`, `PrimaryNav`, `StatusTag`, `SourceCard`, `TrendFigure`, `AssistantPanel`, `CitationDrawer`, `StateNotice`, and `RoutePage`. Use Phosphor Icons for interface icons and never draw substitute icons with CSS.

The current component signatures are all local and prop-based. Preserve the existing Review Desk behaviors while moving it behind the `/review` shell route. Normalize backend-shaped data through adapter modules before it reaches presentation components.
