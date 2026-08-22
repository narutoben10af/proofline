# Supabase Source Library follow-on plan (not configured)

## Current product truth

The MagicFin project exists, and this repository now contains an unapplied migration plus disabled
adapter seam. Supabase is still not configured or used by the running application. The current
Source Library is one
process-local `SessionRepository`, one app-owned `TemporaryBlobStore`, and one strict
`ValidationService`. Sign-in UI must display **Not configured** and continue to offer the keyless
public demo. There are no committed keys, applied schema changes, deployed functions or
production-security claims in this slice. See [the guarded setup path](../supabase-persistence-setup.md).

The local interfaces deliberately separate capability/CSRF authorization and deletion
orchestration from metadata, blobs and validation. A later reviewed implementation can replace the
repository and blob adapters without changing the two-file Review Desk contract.

## Proposed authenticated architecture

1. Add Supabase Auth passwordless email magic-link/OTP behind a small auth-capability response. The
   browser may receive only the project publishable key. A service-role or secret key must never be
   rendered, bundled, logged or sent to a browser.
2. Replace process capability ownership with the authenticated user ID and an owner-scoped
   `SessionRepository` backed by Postgres. Metadata tables use an explicit `owner_id` column; do not
   rely on the deprecated `owner` convention.
3. Replace `TemporaryBlobStore` with a private Storage bucket. Object keys remain opaque and begin
   with the authenticated owner scope. Policies on `storage.objects` require owner-scoped RLS for
   SELECT, INSERT, UPDATE and DELETE. Any upsert flow must have INSERT, SELECT and UPDATE permission,
   not only INSERT.
4. Keep strict validation and deletion orchestration above the adapters. Upload validation must
   still complete before metadata becomes `Ready`. Deletion receipts must distinguish local
   orchestration from Storage/provider retention and must not claim secure erasure.
5. Treat Data API exposure, SQL grants and RLS as separate controls. New public-schema tables may
   not be automatically exposed by current project defaults, so migrations must include reviewed
   explicit grants as well as enabled RLS and policies.

## Migration sequence and review gates

- Threat-model authenticated upload, object naming, signed-access lifetime, admin/support access,
  webhook/callback replay and deletion failure modes before creating a project or requesting keys.
- Add schema migrations for `source_sessions`, `source_files` and deletion receipts with explicit
  ownership, timestamps, retention state and provider-sent state. Do not migrate raw content into
  Postgres.
- Create a private bucket and test every RLS action with two users, including cross-user list/open,
  remove, delete and upsert denial.
- Add passwordless email only after redirect/origin controls are reviewed. OAuth/token clients must
  accept any successful 2xx response rather than hard-coding 201.
- Keep default auth email templates unless custom SMTP is configured; new free projects cannot
  assume template customization is available.
- Update the UI auth capability from `not configured` to `passwordless email` only after migrations,
  policies, redirect configuration and end-to-end tests are green. This avoids a UI rewrite while
  keeping the present state honest.

No part of this roadmap is a claim that the future configuration is deployed, compliant or ready
for confidential production data.
