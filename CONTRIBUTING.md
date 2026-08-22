# Contributing to Proofline

Proofline is currently a hackathon prototype. Keep contributions small, evidence-based, and easy to review.

## Workflow

1. Open or reference an issue for non-trivial work.
2. Create a focused branch from the default branch.
3. Make one coherent change and include documentation or tests where appropriate.
4. Open a pull request using the repository template.
5. Do not merge until required checks and review are complete.

Suggested branch names include `feat/short-description`, `fix/short-description`, `docs/short-description`, and `chore/short-description`.

## Pull-request expectations

- Explain the problem and the chosen scope.
- Separate verified behavior from hypotheses or future plans.
- Describe how the change was checked.
- Call out privacy, security, provenance, and classification implications.
- Include screenshots for visible interface changes when practical.
- Avoid committing real confidential financial documents or credentials.

## Documentation standards

- Cite primary sources for technical or domain claims when available.
- Mark unvalidated proposals as hypotheses, placeholders, or research tasks.
- Record consequential architecture decisions in `docs/architecture/`.
- Update the README only with behavior that exists or is clearly labeled as planned.

## Testing principles

When implementation begins, tests should cover supported, uncertain, and contradicted outcomes, plus missing evidence, unit mismatches, rounding boundaries, malformed inputs, and provenance retention. Until the stack is selected, exact commands remain intentionally unspecified.

## Security and responsible data handling

Read [SECURITY.md](SECURITY.md) before reporting a vulnerability. Use public or synthetic fixtures by default. Remove or redact sensitive information from logs, screenshots, issues, and pull requests.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
