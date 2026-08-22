# API and evidence contracts

The first public contract is version `1.0.0`. Checked-in JSON Schemas and OpenAPI are in
`contracts/v1/`. Breaking changes require a new URL/schema version; adding optional fields may be
made within v1 only when old consumers continue to validate.

## Endpoints

- `GET /health` reports service health, contract/registry versions, and whether the optional model
  provider is configured. It never returns a key.
- `POST /api/v1/analyses` accepts validated claims, normalized observations, and typed calculation
  plans. It returns deterministic metric results and conservative findings.
- `POST /api/v1/sessions` accepts either an allowlisted fixture selection or public-data upload
  metadata. `GET /api/v1/sessions/{id}` exposes processing, cached-output, fallback, and typed error
  state. This first slice records intake metadata only; it does not accept document bytes.
- `DELETE /api/v1/sessions/{id}` deletes process-local session metadata and returns a receipt whose
  narrow scope is explicit. It makes no deletion claim about source systems or bytes never stored.

Decimal values cross the JSON boundary as strings so JavaScript consumers do not silently lose
precision. Dates use ISO 8601. Unknown fields are rejected. Source pages are one-based and workbook
cells use uppercase A1 references.

## Stable evidence chain

The encoded lineage is append-only:

`DocumentVersion -> SourceSpan -> FactObservation -> MetricResult -> Finding`

`evidence-chain.schema.json` encodes the complete portable snapshot. `metric-registry.json` exposes
the exact four metric IDs, formula IDs, input roles, applicability notes, and v1 tolerances for
fixture and frontend consumers.

The analysis request begins at claims and observations because document ingestion is deliberately
stubbable in this PR. Every analysis response repeats its documents, source spans, claims, and fact
observations, so a frontend can resolve every finding and metric input without retaining the request
or making another call. Referential-integrity validation rejects dangling document, span, claim, and
observation provenance before analysis. Frontend consumers should key evidence by IDs and must not
infer provenance from display text.

## Typed calculation plans

A plan selects one of four allowlisted metric IDs and maps exact input roles to observation IDs.
There is no expression, code, query, or arbitrary operator field. Missing, duplicate, or unexpected
roles fail closed. Model output is never executed and never controls arithmetic or classification.

## Classification policy

Numeric assertions are `supported` when their absolute difference from the deterministic result is
within the metric's fixed tolerance; otherwise they are `contradicted`. Missing inputs,
comparability failures, denominator exceptions, unresolved capex sign, and direction-only claims
without a baseline are `uncertain`.

Any extraction warning forces `uncertain`, even when arithmetic agrees. Revenue growth additionally
requires explicit start dates, equal period durations, chronological current/prior roles, and
adjacent periods separated by no more than seven days. Period start cannot follow period end.
Decimal input/result exponents are bounded to -50 through 50; range or arithmetic overflow produces
the typed `numeric_range` exceptional state and an `uncertain` finding.

The fixed v1 tolerances are 0.005 for revenue growth, operating margin, and FCF margin, and 0.01 for
current ratio. These are prototype decisions that require fixture review before any production use.

## Processing and fallback disclosure

`SessionStatus` freezes `accepted`, `processing`, `completed`, and `failed` states, along with a
typed processing-error list and `not_checked`, `available`, `in_use`, or `unavailable` cached-output
status. `fallback_disclosure` must state whether cached output was selected and why. The implemented
intake endpoint always returns `accepted` / `not_checked` and explicitly discloses that adapters are
not implemented; it does not simulate progress or a cache hit.

The upload variant is metadata-only and rejects macro-enabled workbook extensions. Both input
variants require an explicit `public_data_confirmed: true`. Signature/size/encryption validation
belongs to the later byte-upload adapter and is not claimed here.

## Reserved extension boundaries

`extension-contracts.schema.json` reserves three typed, non-executable records for the dedicated
economic/reporting track:

- `EconomicContextPoint` requires a sourced indicator, geography, period, Decimal value/unit,
  source URL/date, and the fixed caveat that context does not establish causation.
- `AnalysisHistorySummary` is explicitly session-local and contains only timestamps, IDs,
  classification counts, and cached-output status.
- `ReportSnapshot` is a reviewed deterministic render input linked to an evidence-chain hash,
  finding IDs, context IDs, and limitations. Its contract explicitly excludes forecasts.

No macro dataset, persistence, PDF renderer, or forecasting behavior is implemented in this PR.

## Temporary Source Library (unversioned prototype slice)

The byte-upload boundary is intentionally separate from the metadata-only `/api/v1/sessions`
contract. `POST /api/sessions` creates an access-private process-local review and sets an
independent capability in a Secure, HttpOnly, SameSite=Strict cookie. The response returns the
opaque session ID, current `OPEN` lifecycle status, retention timestamps and a synchronizer CSRF
token. Mutations require the cookie, an exact allowlisted Origin and `X-Proofline-CSRF`.

`POST /api/sessions/{id}/files` accepts one streamed multipart `report_pdf` and one `workbook`.
Listing, metadata, authorized content, removal and session deletion are never static file routes.
See `source-file.schema.json`, `source-session.schema.json`, `source-session-create.schema.json` and
`source-deletion-receipt.schema.json` for the response contracts. Errors use
`{"reason_code": "STABLE_CODE"}` without parser traces or raw input.

`DELETE /api/sessions/{id}` is idempotent for the capability holder. It returns a versioned scoped
receipt and removes source bytes and active session metadata; only the minimal receipt tombstone is
retained in memory for retry, bounded to two hours and 1,000 entries. Later reads return Gone. This
design is single-process/single-worker,
temporary and unsupported for confidential production input. It makes no secure-erasure,
at-rest-encryption, PDPA, provider-deletion or multi-instance claim. Full rationale and limits are
in ADR 0003.

`GET /api/public-demo/{fixture_id}` remains keyless and immutable. The endpoint returns cached
fixture data only when its checked-in SHA-256 matches, with an official-source or project-derived
label. Upload failure never selects this endpoint automatically.
