# Security review checklist for application pull requests

Use this quick checklist on backend and frontend pull requests. Link evidence (test name, file, or screenshot) for each applicable checked item; write `N/A` with a reason instead of checking an assumption.

## Every application pull request

- [ ] The change stays inside the public/synthetic fixture boundary and adds no production-readiness, confidentiality, or compliance claim.
- [ ] New inputs are bounded and fail closed; error/fallback paths do not skip validation or turn ambiguity into a decisive result.
- [ ] No document content, extracted values, source-bearing prompts/responses, user filenames, or secrets enter logs, analytics, screenshots, fixtures, or test output.
- [ ] No secret is committed or exposed through browser-prefixed environment variables, bundles, source maps, API responses, or build logs.
- [ ] New/updated dependencies are direct-version pinned, represented in the ecosystem lockfile with integrity metadata where supported, and reviewed for necessity, maintenance, license, transitive changes, and known vulnerabilities.
- [ ] CI actions are pinned to immutable commit SHAs and receive minimum permissions.
- [ ] Tests use public minimal or synthetic data; no downloaded issuer PDF is committed without a separately reviewed reuse/provenance decision.

## Backend/parser changes

- [ ] File identity is established from decoded signature/container structure, not extension, MIME type, filename, URL, or issuer name alone.
- [ ] Encrypted/password-protected and macro/embedded-executable inputs are rejected before extraction; formulas, external links, and data connections are not evaluated.
- [ ] Explicit file/count/page/object/sheet/row/cell/decompressed-byte/time/concurrency limits cover the new path and have failure tests.
- [ ] Paths use generated session-local identifiers, reject traversal, avoid symlink following, and cannot read/write outside the restrictive session directory.
- [ ] Network retrieval is absent or exact-allowlisted with bounded bytes/time and redirect/private-address defenses.
- [ ] Model/OCR output is schema-validated and cannot execute code, choose tools/URLs, relax policy, or become authoritative arithmetic/classification.
- [ ] Each result stays bound to the correct document version, page/sheet/cell evidence, normalized inputs, formula version, tolerance, and warnings.
- [ ] Deletion stops new work, handles in-flight work, removes disk and memory state, is idempotent, and has a TTL cleanup test.
- [ ] Deletion receipts state only verified app-managed scope and do not imply provider/backups/log deletion.

## Frontend/API changes

- [ ] The UI and API reject unsupported arbitrary/private uploads and show the public-fixture boundary before processing.
- [ ] Credentials and privileged configuration remain server-only; the browser receives only explicitly public configuration.
- [ ] Source content is escaped and rendered as data, with no unsafe HTML/URL execution or spreadsheet formula export.
- [ ] Session identifiers are not leaked through analytics/referrers and are cleared from client state after deletion.
- [ ] Error views reveal coarse codes and recovery steps, not stack traces, paths, provider payloads, or document content.
- [ ] The deletion receipt labels app-managed scope and exclusions accurately.

## Before merge

- [ ] Run the repository hygiene check and the application tests relevant to the changed boundary.
- [ ] Review GitHub's dependency diff when a manifest or lockfile changes.
- [ ] Confirm secret scanning/push protection did not flag the branch; resolve a true alert by rotating/revoking the credential, not by deleting only the latest copy.
- [ ] Record any unverified security assumption in the pull request and open a follow-up before enabling the affected capability.
