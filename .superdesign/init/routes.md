# Route inventory

The merged prototype currently renders one React root at `/`; screen state inside `App` selects review, empty, loading, error, cached, deletion dialog, and receipt states. No routing package is installed.

Target client routes use the History API and remain static-host compatible:

- `/` — Home overview and entry to Run Magic.
- `/company` — primary company workspace.
- `/files` — combined Files & Upload verified-fixture flow.
- `/sources` — Source Library and evidence anchors.
- `/history` — session-local review history with clear non-persistence label.
- `/review` — existing Editorial Review Desk and its evidence trail.
- `/reports` — reviewed JSON download and disabled/not-configured PDF state.
- `/profile` — local demo preferences, no fake account.
- `/settings` — display, motion, and data controls.
- `/sign-in` — honest not-configured authentication entry.
- `/privacy` — narrow prototype data/retention disclosures.
- `/legal` — accessible legal and demo limitations.

Unknown paths should render a helpful not-found route with a working Home action.
