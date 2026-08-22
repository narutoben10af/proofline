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
- `GET /api/v1/providers/model` exposes redacted readiness. `POST /api/v1/providers/model/test`
  performs a no-document connection probe when configured. Neither reveals a credential or raw
  upstream error.
- `POST /api/v1/assistant`, `POST /api/v1/assistant/chart`, and `POST /api/v1/extractions` expose
  bounded, provider-neutral contracts. The live adapter returns `not_configured`, `offline`,
  `error`, or a locally validated cited result.
- `GET /api/v1/company-lenses/{company_id}` returns one compact, fixture-backed historical series,
  up to four default economic context points, and separately disclosed additional context for an
  allowlisted reviewed company. Every point uses an official source and carries the exact sentence
  `Context only; no causal relationship is asserted.`
- `POST /api/v1/reports/pdf` validates and renders a complete immutable `ReportRenderBundle`. The
  PDF response is an attachment with a strong content hash/ETag and `Cache-Control: no-store`.
  `?output=evidence-json` preserves the reviewed canonical JSON evidence export on the same
  endpoint; it never triggers a fetch or recalculation.

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

The dedicated reporting slice implements stricter additive contracts without changing these
published v1 reserved records. `ResolvedEconomicContextPoint` adds company, display value,
publication and retrieval dates, relevance, comparability warning, official HTTPS source
validation, and default/additional visibility. `FinancialTrendSeries` permits at most one series in
a bundle and requires at least three unique chronological points on one reporting basis.

`ReportRenderBundle` contains the full `AnalysisResponse`, reviewed `ReportSnapshot`, an ID-only
investor report profile, zero or one validated trend, optional resolved context, source
mode/disclosure, and the exact narrow data-handling disclosure. The profile selects exactly four
primary observations and four unique secondary ratios from the hashed analysis. For reporting, the
snapshot's `evidence_chain_sha256` is deliberately validated against
canonical bytes of the **full AnalysisResponse**, including claims. This stricter report boundary
prevents claim text or asserted-value changes from escaping the hash even though the earlier
portable `EvidenceChainSnapshot` omits claims.

The typed ReportLab renderer uses only core fonts and deterministic invariant mode. It escapes
XML-like source text and represents unsupported core-font glyphs as stable `[U+XXXX]` markers. It
does not fetch official sources, recalculate analysis, refresh context, or render forecasts.

The report policy boundary does not attempt to enumerate unsafe phrases. Every non-evidence text
slot uses renderer-authored structured text or an exact reviewed vocabulary: fixed metric claim
sentences, deterministic classifier findings, one fixed company-bound title, one limitation,
registered context/trend labels, and fixed live/cached disclosures. Explicitly attributed PDF
quotes and spreadsheet display values remain verbatim evidence in the provenance appendix. Every
report must contain at least one document, all documents must have the same issuer, that issuer must
equal `bundle.company`, and any claim entity and selected observation entity scope must match the
same company. Apple/PCG are fixture aliases only; other issuers use a deterministic hash-derived
company ID. Selected primary metrics must use one explicit currency and one reporting-period end,
and a trend must use that currency. `snapshot.analysis_id` is exactly `sha256:<canonical AnalysisResponse
hash>`, so it cannot be relabeled independently. Canonical mappings reject non-string keys before
sorting and normalize both float `0.0` and `-0.0` to the same representation.

The renderer has no issuer-name conditionals and is regression-tested with synthetic GBP and JPY
issuers. It renders no ownership/shareholder claim and no forecast section because those sourced,
reviewed typed contracts do not exist in v1. If reviewed economic context is absent, the report
states that fact and keeps the exact no-causation caveat. Generic issuer context requires an
explicit official-source confirmation, a public HTTPS URL, and fixed reviewed non-causal narrative.

Deletion applies only to application-managed session storage. It does not provide secure erasure,
delete data held by providers, or remove PDF or JSON exports already downloaded by users.

## Hosted model boundary

See [Model-provider boundary](model-provider.md). Source-bearing requests require the literal
`provider_sent: true`; it is a machine-auditable declaration, not an inferred consent claim.
Assistant answers require citations, and every extracted claim must reference a cited source span.
Unknown fields, oversized prompts/pages/outputs, unsupported models, and excessive timeout/retry
configuration fail closed. The server transport has no filesystem or database access and receives
only evidence explicitly included in the bounded request.

The chart endpoint accepts a backend-selected set of normalized observations and deterministic
metric results. Gemma may propose only `line`, `bar`, or `comparison`, a safe title/description,
stable evidence IDs, source-span IDs, and an exact period range. It cannot supply chart values,
JavaScript, Vega expressions, HTML, source mutations, upload actions, or deletion actions. The
backend resolves every point value from the supplied normalized observations or deterministic
metric results, rejects unknown IDs and mixed issuer/unit/currency/period bases, caps output at four
series and 24 total points, and returns Decimal strings with citations and
`authoritative_values: deterministic_backend`.
