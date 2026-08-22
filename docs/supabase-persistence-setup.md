# Supabase persistence setup — reviewed, not applied

## Current truth

The MagicFin Supabase project `qvxohnlboefomtjecxdh` exists in `ap-southeast-1`, but this repository
has not linked the CLI, applied the migration, configured Auth, requested credentials, or deployed
an Edge Function. `SOURCE_LIBRARY_PERSISTENCE_BACKEND=process-local` remains the default. Sign-in
must continue to report **Not configured** until the activation checklist is complete.

No statement here is a production-security, confidential-data, secure-erasure or compliance claim.

## What is prepared

- `supabase/migrations/20260822054654_source_library_persistence.sql` creates metadata-only
  `analysis_sessions`, `documents`, `source_spans`, `analysis_snapshots` and bounded
  `deletion_receipts` tables.
- The migration creates a private `proofline-source-library` bucket and owner-scoped policies for
  Storage SELECT, INSERT, UPDATE and DELETE. The object path is exactly
  `{auth.uid()}/{session_id}/{document_id}`.
- Public-schema Data API grants are explicit and separate from RLS. `anon` has no access.
- `src/proofline/supabase_persistence.py` supplies user-JWT PostgREST and private-Storage adapters.
  It never auto-activates them; the current process-local Source Library stays active.
- `supabase/tests/source_library_rls.sql` proves that user A cannot read or delete user B's session,
  document or Storage object in a disposable local database.

Postgres stores locators, hashes, counts, statuses and lifecycle timestamps—not raw document text,
cell values, prompts or source bytes.

## Local review path

Use the repository-pinned Python environment and Supabase CLI 2.115.0 or a subsequently reviewed
version. Docker is required for the local Supabase stack.

```bash
supabase start
supabase db reset
psql postgresql://postgres:postgres@127.0.0.1:54322/postgres \
  -v ON_ERROR_STOP=1 -f supabase/tests/source_library_rls.sql
supabase db advisors
supabase migration list --local
```

Also run the repository's full Python, Ruff, fixture, frontend, Sites and security suites. Inspect
Security Advisor output rather than dismissing it. A local Docker stack is disposable and is not
the real MagicFin project.

## Guarded production apply path

Do not run these steps until the migration diff, RLS tests and application adapter have been
reviewed and the coordinator issues a separate guarded apply instruction.

1. Authenticate the CLI without committing its local state.
2. Link only project ref `qvxohnlboefomtjecxdh` and verify the target region/project identity.
3. Inspect local versus remote migration history and the exact SQL diff.
4. Apply the reviewed migration once; do not deploy an Edge Function in the same action.
5. Run Security Advisor plus two-real-user SELECT/INSERT/UPDATE/DELETE and Storage tests.
6. Configure exact Auth Site URL/redirect allowlists and passwordless email.
7. Activate the adapter only after backend deletion/TTL orchestration and frontend Auth integration
   are separately reviewed.

## Keys and Auth

- Browser: project URL plus a publishable key (`sb_publishable_...`) only. A publishable key is not
  authorization; the signed-in user's JWT and RLS provide ownership enforcement.
- Backend: a secret key (`sb_secret_...`) only in server secret management. It maps to elevated
  `service_role` access and bypasses RLS, so every maintenance operation must authorize and scope
  its target before use. Never expose it in a browser, `VITE_*` variable, repository, log or error.
- Prefer current publishable/secret keys; legacy `anon`/`service_role` JWT keys are compatibility
  credentials, not the target design.
- Magic Link and email OTP use `signInWithOtp`. Redirect destinations must be allowlisted. New Free
  projects using default SMTP cannot customize Auth email templates; custom SMTP is required first.
- OAuth token clients must accept any successful 2xx response (`response.ok`), not hard-code 201.

## Storage and RLS invariants

The bucket remains private. Downloads require the user's JWT under RLS or a deliberately short-lived
signed URL from reviewed backend code. Every metadata table has RLS enabled and ownership checks use
`(select auth.uid()) = owner_id`. UPDATE policies contain both `USING` and `WITH CHECK`.

Document upsert has INSERT, SELECT and UPDATE privileges, with ownership and immutable path shape
enforced by RLS, composite foreign keys and checks. Column grants prevent browser code from changing
session/snapshot `provider_sent`; the backend sets `provider_sent=true` immediately before any
provider transfer, including attempts that later fail.

## TTL and deletion receipts

The intended defaults remain 30 minutes idle, two hours absolute and two hours receipt retention.
A reviewed backend maintenance job must find expired sessions using the server-only secret and run
the same ordered deletion coordinator as an explicit user deletion:

1. atomically move the session to `DELETING` and preserve its existing `provider_sent` value;
2. enumerate and delete application-managed private Storage objects;
3. remove source spans, snapshots, document rows and the session row only after object deletion;
4. write a `complete` or `partial` receipt with per-category counts/bytes and a two-hour
   `retained_until` timestamp;
5. prune expired receipts.

The receipt scope excludes immutable fixtures, user/browser downloads, infrastructure backups/logs
and third-party retention. Provider deletion is not claimed.

## Current Supabase references checked

Verified on 2026-08-22 against the current Supabase documentation and changelog:

- [Storage access control](https://supabase.com/docs/guides/storage/security/access-control) —
  private-object RLS and INSERT + SELECT + UPDATE for upsert.
- [Storage bucket access models](https://supabase.com/docs/guides/storage/buckets/fundamentals) —
  private downloads require an authenticated request or signed URL.
- [Securing the Data API](https://supabase.com/docs/guides/api/securing-your-api) — explicit grants
  and RLS are separate controls; new-table exposure defaults are changing.
- [API keys](https://supabase.com/docs/guides/api/api-keys) — publishable keys are client-safe;
  secret keys are backend-only and bypass RLS.
- [Passwordless email](https://supabase.com/docs/guides/auth/auth-email-passwordless) — Magic Link
  and OTP configuration, expiry and redirect requirements.
- [Supabase changelog](https://supabase.com/changelog.md) — 2026 Data API exposure, OAuth 2xx and
  Free-plan email-template changes.
