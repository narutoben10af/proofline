# Magic Assistant Edge Function

`magic-assistant` is a deployable Supabase Edge Function boundary for authenticated, cited chart
proposals. It is not deployed by this repository and is not live without a Supabase backend,
RLS-authorized normalized evidence, and a server-side `GEMINI_API_KEY` Edge Function secret.

## Security contract

- Supabase gateway JWT verification must remain enabled (the default). The function also validates
  the bearer token through Supabase Auth before reading evidence.
- Database reads use only the project publishable/legacy anon key plus the caller's bearer token.
  They therefore remain subject to that user's RLS policies. The function never reads a service or
  secret Supabase key and never uses `user_metadata` for authorization.
- Requests contain only schema version, a question of at most 1,000 characters, one opaque `src-…`
  session ID, and at most 12 opaque `file-…` source IDs. These bounds mirror the dynamic upload
  contracts on current main. Fixture IDs, UUID-shaped placeholders, file URLs, source edits,
  uploads, and deletion commands are rejected as unknown or out-of-scope input.
- The model receives the bounded question plus normalized evidence metadata and stable IDs. It does
  not receive raw file URLs, file bytes, model credentials, or authoritative numeric values.
- Gemma may return only a `line`, `bar`, or `comparison` proposal with safe text, observation IDs,
  source IDs, and an exact period range. Local validation rejects invented IDs, unmatched citations,
  mixed issuer/currency/unit/period bases, more than four series, or more than 24 points.
- The response contains proposal IDs only. The frontend must resolve actual values through its
  authenticated RLS-backed evidence path. It must never interpret model output as chart values.
- Google calls use exactly the two allowlisted Gemma 4 `generateContent` endpoints, refuse
  redirects, and enforce byte, output-token, timeout, and retry caps. Errors are typed and redacted.

## Storage migration boundary

Current main keeps dynamic uploads and their deterministic normalized observations in the FastAPI
process-local source library. Those records are not yet available through Supabase RLS. Until the
storage owner maps the same `src-…` session IDs, `file-…` source IDs, and `fact:…` observation IDs
into `public.magic_assistant_evidence`, the function returns:

```json
{
  "state": "not_configured",
  "code": "not_configured",
  "retryable": false,
  "disclosure": "No evidence or question was sent to Google Gemma 4."
}
```

The future relation must be readable by `authenticated`, protected by owner-scoped RLS, preserve
those opaque dynamic IDs exactly, and expose only these columns:

`session_id`, `source_id`, `observation_id`, `issuer`, `concept`, `period_start`, `period_end`,
`duration_weeks`, `unit`, and `currency`.

If implemented as a view, it must use `security_invoker = true`; its base tables must retain RLS. Do
not add a service-role fallback. Cross-user and unknown evidence should be indistinguishable to the
caller.

## Local checks

Install Deno 2, then run from this directory:

```sh
deno task check
```

The tests mock Supabase Auth, RLS REST reads, and Google. They never require a project, Docker, a
real user token, a real model key, or a network call.

To serve against a reviewed local Supabase stack later, keep JWT verification enabled and place
uncommitted values in a local env file outside Git:

```sh
supabase functions serve magic-assistant --env-file supabase/functions/.env.local
```

Required runtime values are `SUPABASE_URL`, a publishable key supplied by the platform,
`GEMINI_API_KEY`, and a comma-separated `MAGIC_ASSISTANT_ALLOWED_ORIGINS`. `GEMMA_MODEL` is optional
and defaults to `gemma-4-26b-a4b-it`.

## Deployment handoff (not performed)

After the project, JWT settings, RLS relation, allowed origins, provider terms, and secret ownership
are reviewed:

```sh
supabase functions deploy magic-assistant --use-api
```

Set `GEMINI_API_KEY` only in Edge Function secret management. Never commit it, place it in browser
configuration, or expose a Supabase service/secret key. Deployment and secret creation are
deliberately outside this PR.
