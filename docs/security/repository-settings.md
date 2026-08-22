# Repository security settings

Repository-host settings cannot be enforced by committed files alone. An administrator should verify these settings for the public repository and record completion in a protected issue or repository configuration log:

- GitHub secret scanning is active and alerts have an owner.
- Push protection is active; bypasses require a documented reason and review. If a real credential is detected, revoke/rotate it before removing it from history or code.
- The dependency graph and Dependabot security alerts are active. Add GitHub's dependency-review action after the first package manifest and lockfile land; require it for pull requests once its signal is verified.
- The `main` branch requires pull requests and the fast `Repository security baseline` check. Restrict force pushes and branch deletion.
- Workflow permissions default to read-only; grant write scopes only to a specific reviewed job.
- Private vulnerability reporting is enabled or `SECURITY.md` points to a verified private contact path.

These checks are operational guidance, not proof that the settings are currently enabled. Public repository secret scanning does not remove the need for local hygiene checks, review, and credential rotation.

## Dependency pinning rule

Choose one package manager per runtime. Commit the manifest and its generated lockfile together, pin direct application dependencies to reviewed versions, preserve lockfile integrity hashes, and update through small pull requests. Do not hand-edit lockfiles. Review transitive and installer/build-script changes, not only top-level version strings. Pin GitHub Actions by full commit SHA and annotate the corresponding release tag for maintainability.
