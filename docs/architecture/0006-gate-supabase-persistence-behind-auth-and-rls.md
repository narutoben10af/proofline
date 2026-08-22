# ADR 0006: Gate Supabase persistence behind reviewed Auth and RLS

- Status: Proposed; code and migration are not deployed
- Date: 2026-08-22

## Context

The temporary Source Library is deliberately process-local and cannot provide durable ownership,
multi-instance coordination or authenticated private Storage. A MagicFin Supabase project now
exists, but the application has not completed Auth integration, migration review, or cross-user
policy verification against that project.

## Decision

Keep `process-local` as the default and active backend. Add a disabled Supabase persistence seam,
a reviewable SQL migration and a private-bucket policy design. Activation requires all of:

1. reviewed passwordless Supabase Auth and redirect handling;
2. local migration reset plus two-user RLS tests;
3. reviewed production migration and Security Advisor output;
4. server-only deletion/TTL/provider-transfer orchestration;
5. a separate guarded instruction to apply the migration.

The browser may receive only a current `sb_publishable_...` key and a user Auth session. A
`sb_secret_...` key is backend-only and bypasses RLS, so it cannot be placed in browser variables,
bundles, logs or public configuration. User requests use the publishable key plus the user's access
token; Postgres and Storage RLS remain the authorization boundary.

Postgres stores metadata only: user-owned analysis sessions, document metadata, source locators and
analysis snapshot hashes/counts. Raw PDFs and workbooks use a private Storage bucket with the exact
object shape `{auth.uid()}/{session_id}/{document_id}`. Ownership uses `owner_id`; no policy relies
on mutable user metadata or the deprecated Storage `owner` field.

Deletion is ordered and retryable: mark `DELETING`, capture `provider_sent`, remove every private
Storage object, remove child/session metadata, then record the bounded receipt. Any failure records
`partial` and must not make a broader deletion claim. TTL cleanup uses the same orchestration. The
design does not claim secure erasure, deletion from backups/logs or providers, compliance, or
production readiness.

## Consequences

The checked-in adapter is production-shaped but intentionally not wired into current API routes.
This prevents an incomplete Auth setup from weakening the capability-isolated local flow. The
existing `SessionRepository`, `TemporaryBlobStore` and strict validation service remain the active
fallback until the activation gates pass.
