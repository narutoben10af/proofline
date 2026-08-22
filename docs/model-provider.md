# Model-provider boundary

Status verified against official Google sources on 2026-08-22. This is an engineering record, not
a promise that pricing, quotas, model availability, or provider data terms will remain unchanged.

## What the names mean

- **Gemma 4 exists.** It is Google's current open-weight Gemma family, separately downloadable and
  deployable under its published model terms. Gemma is not another name for Gemini.
- **Gemini API is a hosted API.** Google documents hosted Gemini API access for exactly
  `gemma-4-31b-it` and `gemma-4-26b-a4b-it`. Proofline allowlists those two identifiers and defaults
  to the latter.
- Google's current pricing table lists Gemma 4 input, output, and context caching as free of charge
  on the free tier, with no paid tier offered. It also says free-tier content is used to improve
  Google's products. Rate limits are model/project-specific and shown in AI Studio. Therefore this
  repository does not call Gemma 4 “free forever,” production-private, or unmetered.

Primary sources:

- [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
- [Run Gemma with the Gemini API](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api)
- [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

## Implemented safety boundary

Without a server-side `GOOGLE_API_KEY`, the adapter reports `not_configured` and sends nothing. With
a key, a live transport is available only on the server. The key is held in a redacting secret
wrapper inside that transport; it is never logged, returned, exposed through OpenAPI, or placed in
browser code. The provider has no filesystem or database capability. It receives only the bounded
evidence excerpts or pages selected and validated by the backend request.

Assistant and extraction contracts reject unknown fields and bound prompts, pages, combined source
text, outputs, retries, and timeouts. A request containing source context must explicitly set
`provider_sent: true`. Successful/fallback assistant output requires evidence citations; every
extracted claim must resolve to a cited source-span ID. Loading, offline, not-configured, error, and
fallback are typed states.

Chart requests use the same evidence-only boundary. The model can propose only a line, bar, or
comparison chart by referencing backend-selected observation or deterministic metric IDs, their
source-span IDs, and a period range. It cannot supply numeric chart values or executable rendering
content. Proofline resolves values locally, recomputes referenced metrics against the deterministic
registry, rejects unknown, forged, or dimensionally mixed evidence, caps series and points, and
emits a cited frontend-safe `ChartSpec`. The assistant has no source editing, upload, or deletion
operation.

`GET /api/v1/providers/model` and `POST /api/v1/providers/model/test` reveal no key or raw provider
error. The connection test sends no document content. Live generation uses exact HTTPS endpoint
allowlisting for Google's documented `generateContent` paths, refuses redirects, uses structured
JSON response schemas and zero temperature, caps request/response bytes and output tokens, enforces
request timeouts, and permits at most two transient-error retries. Remote content is accepted only
after local schema, size, reference, dimension, and citation validation.

The deterministic fixture provider supports reproducible tests and scripted demonstrations. It
returns only injected answers/claims, labels itself as a fixture fallback, refuses unsupported
prompts, and never uses the network.

Before production use, reviewers must separately approve provider terms and data-use tier, explicit
user consent, network egress allowlisting, quota handling, operational telemetry, and
incident/deletion scope. The free tier's stated product-improvement use makes it unsuitable for
private financial documents without a separate reviewed basis and user disclosure.
