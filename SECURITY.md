# Security policy

## Prototype status and supported versions

Proofline is an early public-fixture hackathon prototype. It is not a system of record and must not be used as a substitute for accounting, audit, investment, legal, or compliance review. This policy does not claim production readiness, confidentiality for arbitrary uploads, or Malaysian PDPA compliance.

There are no released or supported versions yet. Security fixes apply to the default branch while the project remains in prototype development.

## System and scope

The in-scope prototype accepts only explicitly allowlisted public or synthetic PDF and spreadsheet fixtures, extracts bounded evidence, optionally sends allowlisted source material to a hosted model through a server-side adapter, computes metrics in deterministic code, and retains working data only for a temporary session. It has no authentication, user accounts, persistent database, or multi-tenant document history.

Security-sensitive surfaces include:

- the upload and fixture-selection boundary;
- PDF, OCR, image, and spreadsheet parsers;
- model prompts and schema-validated model responses;
- deterministic calculation and evidence-provenance code;
- per-session temporary storage and deletion;
- browser/API boundaries, logs, build artifacts, and deployment configuration; and
- dependencies, CI workflows, fixtures, and repository history.

## Threat model and trust boundaries

Documents, filenames, archive members, PDF objects, workbook formulas, links, metadata, extracted text, images, and model output are attacker-controlled even when a fixture is publicly hosted. A fixture URL or issuer name does not make its bytes trusted.

Browser requests cross into the server-side application. The application then crosses separate boundaries into native parsers, optional OCR/model providers, temporary storage, and deterministic calculation code. Model providers and hosting services are external processors; only the approved public-fixture demo path may send source content to them.

Repository contributors and deployment operators are trusted to approve fixture provenance, configure secrets, and deploy reviewed revisions, but their files and configuration can still be mistaken or compromised. CI output, issue content, and pull-request artifacts are public disclosure surfaces.

The assets that matter most are model/API credentials, host integrity, availability during the demo, the public-fixture-only boundary, temporary document contents, and the accuracy and provenance of evidence shown to reviewers.

Realistic attacker stories include a crafted file exhausting parser resources, escaping its session directory, triggering unsafe external access, smuggling a macro or formula payload, injecting instructions into model-bound content, leaking source material through logs, or causing evidence from one session/document to be attributed to another. Confidential customer-document processing and authenticated multi-user attacks are outside the supported prototype because those capabilities must not be enabled.

## Security invariants

### Uploads and parsing

- Accept only the explicitly allowlisted public/synthetic fixture types and expected file count. Arbitrary upload support is not part of this prototype.
- Validate the decoded file signature and internal container type; never trust the extension, browser MIME type, filename, or URL alone.
- Enforce bounded file bytes, PDF pages/objects, workbook sheets/rows/cells, decompressed bytes, parser time, model time, OCR work, and concurrency before expensive processing.
- Reject encrypted or password-protected PDFs and workbooks. Do not request, store, or attempt passwords.
- Reject macro-enabled Office formats and any workbook containing VBA or embedded executable content. Do not evaluate formulas, external links, data connections, or model-generated code.
- Treat filenames and archive paths as labels only. Generate server-side random identifiers, prevent traversal/symlink following, and keep each session under its own restrictive temporary directory.
- Network retrieval, if implemented, must use an exact fixture allowlist, bounded downloads, redirects disabled or revalidated, and no access to private/link-local addresses. User-supplied URLs are not supported.
- Parser/model failure must become a clear error, a verified cached public result, or `uncertain`; it must never silently relax validation.

### Model, calculations, and evidence

- Model calls are server-side only. Privileged secrets must never enter client bundles, browser storage, source maps, public fixtures, screenshots, logs, or model prompts.
- Model output is untrusted and schema-validated. It may propose bounded typed inputs, but it cannot execute Python, JavaScript, shell, SQL, formulas, URLs, or arbitrary expression trees.
- Authoritative arithmetic and classification use allowlisted deterministic code. Every decisive result retains document version, page/sheet/cell provenance, normalized inputs, formula version, tolerance, and warnings.
- Content-based prompt injection cannot change tool permissions, fetch arbitrary resources, alter security policy, or turn missing/incomparable evidence into a decisive classification.

### Sessions, deletion, and logging

- Session state is non-persistent and isolated by a cryptographically random identifier that is not accepted as proof of user authorization beyond the single prototype session.
- A delete operation must stop new work, cancel or await in-flight work, remove the entire app-managed session directory and in-memory records, mark the session deleted, and make repeated deletion idempotent. TTL cleanup is a backstop, not a substitute for explicit deletion.
- A deletion receipt states the session identifier, completion time, and tested app-managed scope. It must not claim deletion from provider systems, infrastructure backups, transient network buffers, or logs unless those scopes are independently verified.
- Normal logs contain only event name, coarse status/error code, duration, bounded counts, and a non-reversible request/session correlation value. Never log document bytes/text, extracted passages, spreadsheet values/formulas, prompts containing source material, model responses containing source material, filenames supplied by users, credentials, or full stack traces that embed content.

### Secrets, environment, and dependencies

- Runtime secrets come from the hosting provider's secret manager or local environment. `.env` files remain ignored; `.env.example` contains names and empty or demonstrably non-secret values only.
- Browser-exposed environment-variable prefixes must never be used for model keys or other privileged values. The server must fail closed when a required secret is absent.
- Commit a lockfile for every application package manifest, pin direct dependencies, retain integrity hashes where the ecosystem supports them, and review transitive changes. Pin CI actions to immutable commit SHAs.
- Do not commit issuer PDFs or other downloaded artifacts until reuse rights and provenance are explicitly reviewed. Do not commit confidential, personal, regulated, or credential-bearing inputs under any circumstances.

## Reportable findings and severity context

Report vulnerabilities that violate an invariant above and are reachable in the supported public-fixture demo or its build/deployment path. Especially relevant classes include parser escape or resource exhaustion, path traversal, unsafe temporary files, server-side request forgery, macro/formula execution, document prompt injection that crosses a privilege boundary, secret exposure, cross-session data disclosure, incomplete deletion claims, content logging, dependency/CI compromise, and misleading or mutable evidence provenance.

- **Critical:** compromise of repository/deployment credentials or code execution on the host/CI through the normal supported path.
- **High:** public remote access to privileged secrets or another session's document content; reliable host file/network access from an accepted fixture; or silent evidence substitution that can systematically produce decisive false results.
- **Medium:** bounded but meaningful source-content disclosure, deletion that leaves app-managed session files behind, validation bypass requiring a contributor-approved fixture, or practical denial of service beyond configured limits.
- **Low:** limited information exposure or hardening gaps with no sensitive data, privilege, cross-session, or evidence-integrity impact in the supported demo.

Severity depends on demonstrated reachability and impact. A weakness that requires unsupported confidential uploads, authentication, persistent accounts, or production infrastructure is normally a design gap rather than a vulnerability in the current prototype, unless the code or documentation actually exposes or claims that capability.

## Known limitations and accepted prototype boundaries

- Only approved public or synthetic fixtures are supported. Masking does not make arbitrary or confidential documents safe.
- No confidentiality, retention, training-use, regional-processing, or provider-deletion guarantee is made beyond behavior that is tested and documented.
- No authentication or multi-user authorization boundary exists. Adding accounts, private uploads, persistent storage, or background processing requires a new threat/data-flow review before enablement.
- A lightweight repository check supplements, but does not replace, GitHub secret scanning, push protection, dependency review, code review, parser sandboxing, or runtime tests.
- Availability of the prototype and third-party model/OCR providers is not guaranteed.

## Reporting a vulnerability

Do not disclose suspected vulnerabilities, credentials, confidential documents, or personal data in a public issue.

Use GitHub's private vulnerability reporting feature if enabled. Otherwise, contact the repository owner privately through a verified channel on the owner's GitHub profile and share only the minimum needed to establish a secure reporting path.

Include, where safe, the affected revision/component, minimal reproduction steps, likely impact, suggested mitigation, and whether sensitive data may have been exposed. Receipt or remediation timelines are not guaranteed during the prototype stage.
