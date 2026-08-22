# Extractable component candidates

## Existing

- `EvidenceDisclosure({ type, title, subtitle, children, defaultOpen })`: accessible evidence accordion; keep as reusable disclosure.
- `DeleteDialog({ onCancel, onConfirm })`: reusable destructive confirmation after adding a complete focus trap.
- `StatusSummary()`: reusable three-state finding strip driven by normalized counts.
- `ProofTrail()`: reusable deterministic evidence sequence driven by normalized steps.
- `ReviewActions({ onDecision })`: reusable review decision/export cluster.

## Target

- `AppShell({ route, children, onNavigate, onOpenAssistant })`
- `SourceCard({ source, onOpen })`
- `TrendFigure({ series, activeMetric, onOpenTable })`
- `AssistantPanel({ state, messages, onOpenCitation, onClose })`
- `CitationDrawer({ citation, onClose, onOpenEvidence })`
- `RunMagicProgress({ stage, stages, onCancel })`
- `RouteState({ kind, title, body, action })`

All target components consume typed/normalized fixture adapters. Provider, storage, Source Library, macro context, and server PDF endpoints plug in behind those adapters without changing the presentational contract.
