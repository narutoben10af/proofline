# Authenticated live upload pipeline

## Release truth

This repository contains a deployable authenticated pipeline. It is active only when the backend
has complete Supabase configuration and the frontend was built with the matching public Auth and
API origins. A static frontend build, an unapplied migration, or missing credentials is not a live
upload deployment.

No service-role or model key belongs in a browser variable, JavaScript bundle, response, log, or
repository file.

## Data path

1. The browser obtains a verified Supabase user session and sends only that user's access token to
   the configured API origin.
2. The API verifies the token through Supabase Auth; it never trusts a browser-supplied owner ID.
3. `create_analysis_session` derives the owner and fixed idle/absolute expiry in Postgres.
4. The API accepts one PDF and one XLSX, applies byte/type/structure limits, and sanitizes supported
   interactive PDFs. Unsupported, encrypted, macro-bearing, external-link, ambiguous, or formula
   inputs fail closed.
5. `register_source_document` creates an owner-scoped `Checking` locator. Only then does the API
   write the validated canonical bytes to the private bucket path
   `{owner_id}/{session_id}/{document_id}`. A backend-only operation marks the exact hash and byte
   count `Ready`.
6. Analysis downloads those exact private objects under the user's RLS context, validates them a
   second time, extracts native PDF text first, normalizes workbook facts, and performs only
   allowlisted deterministic calculations.
7. OCR runs only when an absolute configured Tesseract executable exists and native mapping cannot
   complete. Missing OCR, OCR runtime failure, and low-confidence OCR return distinct safe errors.
8. `persist_completed_analysis` atomically replaces the session's source-span rows, normalized
   owner-scoped `magic_assistant_evidence`, and cited `AnalysisResponse` snapshot. The browser gets
   that same response; the dashboard, Files & Sources, Review Desk, and report views adapt it without
   substituting fixture data.

## Configuration boundary

Backend secret manager:

```text
SOURCE_LIBRARY_PERSISTENCE_BACKEND=supabase
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
SUPABASE_SECRET_KEY=sb_secret_...
SOURCE_LIBRARY_ALLOWED_ORIGINS=https://<public-site-origin>
OCR_TESSERACT_COMMAND=/absolute/path/to/tesseract   # optional
```

Frontend build configuration:

```text
VITE_SUPABASE_URL=https://<project-ref>.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
VITE_SUPABASE_GOOGLE_AUTH_ENABLED=true
VITE_API_BASE_URL=https://<api-origin>
```

`VITE_*` must never contain `SUPABASE_SECRET_KEY`, `GEMINI_API_KEY`, or another elevated secret.

## Deployment gate

Apply both ordered Supabase migrations, run the SQL RLS suite against a disposable database, deploy
the API container, then build the frontend with the exact API/Auth origins. Deploy only the tested
commit SHA. A release is complete only after a signed-in user uploads a real non-fixture PDF/XLSX
pair and confirms all of the following from the returned live response:

- both private document rows are `Ready` and owned by that user;
- the response has `cached_output=false`, uploaded document UUIDs, cited spans, normalized facts,
  deterministic metric results, and findings;
- `analysis_snapshots` and `magic_assistant_evidence` contain only that owner's session rows;
- the dashboard, source cards, Review Desk, and report show the uploaded issuer and values;
- changing a workbook value changes the returned metric and never restores demo data;
- another authenticated user cannot read the session, documents, objects, spans, snapshot, or
  assistant evidence.

If any item cannot be observed, report the deployment as incomplete rather than calling it live.
