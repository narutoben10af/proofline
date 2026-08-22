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
- [ ] `docs/privacy/data-flow-retention.md` covers each new collection, disclosure, provider, region, purpose, retention clock, deletion scope, and exported copy; unknowns are blockers, not inferred facts.
- [ ] User-facing privacy/legal/settings text matches deployed behavior and does not claim consent, confidentiality, provider deletion, Malaysian PDPA compliance, or production readiness.

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
- [ ] Temporary storage has tested idle and absolute TTLs, periodic/startup/shutdown cleanup, bounded deletion tombstones/receipts, safe configured-root validation, and evidence that the app-managed directory is gone.
- [ ] Provider calls set and expose a truthful `source_material_sent_to_provider` state before transfer, including failure/cancellation paths.

## Frontend/API changes

- [ ] The UI and API reject unsupported arbitrary/private uploads and show the public-fixture boundary before processing.
- [ ] Credentials and privileged configuration remain server-only; the browser receives only explicitly public configuration.
- [ ] Source content is escaped and rendered as data, with no unsafe HTML/URL execution or spreadsheet formula export.
- [ ] Session identifiers are not leaked through analytics/referrers and are cleared from client state after deletion.
- [ ] Error views reveal coarse codes and recovery steps, not stack traces, paths, provider payloads, or document content.
- [ ] The deletion receipt labels app-managed scope and exclusions accurately.
- [ ] The file picker says whether bytes remain on-device or cross to a server; selection is not described as upload until transfer occurs.
- [ ] Export messaging explains that downloaded JSON/PDF copies are outside session deletion and avoids spreadsheet formula injection.
- [ ] Assistant output is cited, uncertain where evidence is missing, non-authoritative, and cannot make or imply a consequential solely automated decision.

## Personal-data readiness gate

Complete this section before any private or personal data path is enabled. A checked box needs an accountable owner and linked evidence.

- [ ] The actual operator has documented whether it is controller, processor, or both for each flow and obtained legal review of Act 709 scope and processing conditions.
- [ ] A publishable Bahasa Malaysia and English section 7 notice identifies the controller and real rights/complaints contact, data descriptions/sources/purposes, third-party classes, choices, mandatory/voluntary fields, and consequences.
- [ ] Access, correction, consent-withdrawal/processing-limitation, portability (where technically feasible), and complaint requests have authenticated operating procedures and response records.
- [ ] Hosting/model/OCR/storage/monitoring contracts, subprocessors, locations, retention, security guarantees, incident escalation, and deletion/export support are reviewed.
- [ ] Every transfer outside Malaysia has a recorded section 129 condition and, where applicable, transfer impact assessment and safeguards.
- [ ] The operator has assessed DPO applicability (20,000 data subjects; 10,000 sensitive/financial data subjects; or regular and systematic monitoring) and the 21-day notification step if triggered.
- [ ] The operator has assessed the current 13 registration classes and Commissioner Circular No. 1/2026; sector branding alone is not used to decide applicability.
- [ ] The breach runbook has named incident, privacy/legal, hosting, and provider contacts and can meet the Commissioner and data-subject clocks.
- [ ] A DPIA and human-oversight review covers any personal-data assistant, profiling, or automated-decision feature before enablement.

## Before merge

- [ ] Run the repository hygiene check and the application tests relevant to the changed boundary.
- [ ] Review GitHub's dependency diff when a manifest or lockfile changes.
- [ ] Confirm secret scanning/push protection did not flag the branch; resolve a true alert by rotating/revoking the credential, not by deleting only the latest copy.
- [ ] Record any unverified security assumption in the pull request and open a follow-up before enabling the affected capability.
