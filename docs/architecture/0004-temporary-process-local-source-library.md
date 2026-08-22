# ADR 0004: Use temporary process-local Source Library storage

- Status: Accepted for prototype
- Date: 2026-08-22

## Context

Proofline needs a narrow byte-upload boundary for one report PDF and one evidence workbook per
review. The repository has no user authentication or reviewed production threat model. Adding a
database or object-store identity layer during the hackathon would create a misleading impression
of durable, production-private storage.

ADR 0002 remains authoritative for hosted-model processing: arbitrary uploads are not sent to a
provider in this slice. This ADR permits access-private temporary intake, not confidential hosted
processing.

## Decision

Run one FastAPI process with one worker in one container. Store each review beneath an app-owned
temporary root using an unguessable session ID, an independent capability held only in a Secure,
HttpOnly, SameSite=Strict cookie, and opaque file IDs with canonical `.pdf` or `.xlsx` extensions.
Supplied filenames are display metadata only and are never used as paths.

The capability digest, CSRF digest, lifecycle and minimal file metadata are process-local. The
lifecycle is `OPEN -> PROCESSING -> DELETING -> DELETED` under a per-session lock. Access checks
atomically reject idle or absolute expiry before activity can be refreshed. Deletion first marks
the session `DELETING`, removes the managed directory and active metadata, and retains only a
minimal capability-scoped receipt tombstone so retries return the same receipt.

The implementation exposes narrow `SessionRepository`, `BlobStore` and `ValidationService` seams.
Capability hashing, CSRF/origin checks, lifecycle locking and deletion orchestration remain above
those adapters. The process repository bounds receipt tombstones to two hours and 1,000 entries.
The temporary blob adapter requires an absolute, non-broad, non-symlink root with an ownership
marker and recursively removes only opaque session directories. The future Supabase migration plan
is documented separately; no Supabase adapter or credential is present now.

Idle retention is 30 minutes and absolute retention is two hours. Cleanup runs at startup,
periodically and on graceful shutdown. Startup removes orphaned managed directories because their
process-local capabilities no longer exist. Immutable public fixtures live outside this root.

Mutating routes require an exact allowlisted Origin, same-origin fetch context, the HttpOnly
capability cookie and a synchronizer CSRF token. The API never statically mounts the managed root.
Request size is bounded at the ASGI receive boundary before multipart parsing, then file bytes are
streamed in fixed chunks to an opaque partial path with a smaller role-specific limit. All partial
paths are removed on failure.

PDFs require matching extension, declared MIME, PDF magic/EOF and a strict structural `pypdf`
probe. Encrypted documents, unsupported/malformed structures, active actions, JavaScript (including
escaped PDF names), embedded files/forms, excessive pages/text and timed-out probes fail closed.
XLSX files require matching OOXML MIME/magic and bounded ZIP/XML probes. Encryption, macros,
external relationships, traversal, symlinks, duplicate or unexpected paths, nested archives,
unsupported compression, ZIP-bomb ratios and sheet/row/column/cell/text limits fail closed.
Formula XML may be present but is never evaluated or executed.

Errors expose stable reason codes only. Application code does not log supplied filenames, raw
document content, cells, prompts or provider payloads. API/model keys remain server environment
values and are never part of source contracts or frontend builds.

## Consequences and explicit limits

This design has no database, durable retention, user authentication, at-rest encryption claim,
secure-erasure claim, provider-deletion claim, PDPA-compliance claim or multi-instance correctness
claim. Multiple workers or replicas would have different capability/session memory and are
unsupported. Abrupt container termination relies on the next startup sweep; infrastructure
backups/logs and third-party retention are outside the deletion scope.

The exact successful receipt claim is:

> Deleted from this running container’s application-managed session storage.

The receipt separately excludes immutable fixtures, user/browser downloads, infrastructure
backups/logs and third-party retention, and states whether source material was sent to a provider.

Supabase remains roadmap-only after authentication and threat review: private buckets, RLS and
short-lived signed access may be evaluated then. This ADR makes no production-security claim for
that future design. See [the non-configured follow-on plan](../roadmap/supabase-source-library.md).
