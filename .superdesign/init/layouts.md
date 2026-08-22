# Layout inventory

## Existing Review Desk

Source: `frontend/src/App.jsx` and `frontend/src/styles.css`.

The current layout is a sticky top bar followed by an editorial two-column grid:

```jsx
<div className="app-shell">
  <a className="skip-link" href="#review-content">Skip to review</a>
  <Header />
  <main id="review-content" className="review-layout">
    <div className="review-main">
      <StatusSummary />
      <VisualVerdict />
      <ProofTrail />
      <ReviewActions />
    </div>
    <EvidenceRail />
  </main>
</div>
```

Desktop uses `minmax(0, 1.95fr) minmax(330px, .95fr)`. Below 980px the evidence rail stacks below the review. Below 680px status, comparison, proof metadata, and actions become single-column. There are no fixed-height panes.

## Target MagicFin shell

Use a compact persistent rail at desktop sizes and a broad, naturally scrolling workspace. The Company route has: company/period header → compact source row → dominant trend/table → factual summary and review priorities. Chat and citations are overlays/panels, not permanent equal-width columns. Tablet collapses the rail; mobile uses a top bar and single-column content, with assistant as a full-screen sheet.
