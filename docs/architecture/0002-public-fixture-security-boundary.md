# ADR 0002: Enforce a public-fixture-only processing boundary

- Status: Accepted
- Date: 2026-08-22

## Context

Proofline parses complex PDFs and spreadsheets and may send selected source material to hosted OCR or model services. These formats and external boundaries can expose document content, consume substantial resources, or execute unintended behavior if handled as trusted input. The six-hour prototype has no need to accept confidential or arbitrary customer documents.

The interface also promises an explicit delete-session action. That promise must describe only the app-managed state that the implementation can demonstrably remove.

## Decision

The prototype will enforce these boundaries:

1. Only an exact allowlist of reviewed public or synthetic fixtures is accepted. A URL, extension, MIME type, or issuer identity alone does not establish trust.
2. Upload validation checks decoded signatures/container types, rejects encrypted inputs, rejects macros/embedded executable content, and applies explicit byte, complexity, count, and time limits before expensive parsing.
3. Parsers run without formula evaluation or arbitrary network retrieval. Generated session IDs and session-local paths replace user-supplied paths.
4. Hosted model/OCR calls are server-side, bounded, and limited to approved public fixtures. Their outputs remain untrusted; deterministic code owns calculations and classifications.
5. App-managed session data lives in a restrictive per-session temporary directory plus bounded in-memory state. Explicit deletion removes both, is idempotent, and is backed by TTL cleanup.
6. Deletion receipts enumerate the tested app-managed scope and explicitly exclude provider retention, infrastructure backups, network buffers, and other scopes not verified by the prototype.
7. Operational logs contain metadata and coarse error codes only, never document content, extracted values, source-bearing prompts/responses, user filenames, or secrets.

Concrete invariants and severity context live in the repository root `SECURITY.md`. Backend and frontend pull requests apply `docs/security/review-checklist.md` until automated tests supersede each manual check.

## Consequences

- Arbitrary uploads, password entry, private documents, user-supplied URLs, and macro-enabled files are unsupported and fail closed.
- Some valid-but-complex public files will be rejected; this is preferable to silently expanding the demo's exposure.
- The implementation needs explicit validation error codes, cleanup state transitions, and content-safe logging tests.
- Adding accounts, persistent storage, background jobs, confidential uploads, or broader provider use requires a new ADR and threat/data-flow review.
- This decision does not establish PDPA compliance, production readiness, or deletion beyond the verified app-managed scope.
