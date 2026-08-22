# ADR 0003: Render reports only from canonical immutable bundles

- Status: Accepted
- Date: 2026-08-22

## Context

Proofline needs a downloadable reviewed report without making PDF generation a second analysis
pipeline. A browser/HTML renderer would add a large runtime, mutable layout dependencies, and
opportunities to fetch or recalculate during export. The reserved v1 `EvidenceChainSnapshot` also
omits claims, so its bytes alone cannot bind every finding input displayed in a report.

## Decision

Use one small server-side ReportLab renderer driven only by a frozen `ReportRenderBundle`. The
bundle carries version identifiers, the full `AnalysisResponse`, reviewed `ReportSnapshot`, an
ID-only `InvestorReportProfile`, at most one validated historical series, optional resolved
official-source economic context, explicit live/cached source disclosure, and the narrow
export/deletion disclosure. The profile selects four primary observations and four unique secondary
ratio results by evidence ID; it cannot supply free-form report assertions.

Canonical JSON uses sorted keys, UTF-8, normalized finite Decimal strings, and UTC `Z` timestamps.
For this stricter report boundary, `ReportSnapshot.evidence_chain_sha256` must equal the SHA-256 of
the complete canonical `AnalysisResponse`, including claims. The PDF itself receives a separate
content SHA-256 and strong ETag. ReportLab invariant mode, fixed metadata, stable ordering, escaped
untrusted text, core fonts, and stable Unicode fallbacks make repeated renders byte-identical.

The renderer is pure: it does not access the network, adapters, metric calculation service, clocks,
or storage. Invalid IDs, counts, evidence hash, context, trend comparability, cache disclosure, or
forecast markers reject the bundle before PDF bytes are returned.

Report identity is bound fail-closed: a bundle requires a non-empty single document-issuer set,
that issuer must equal the bundle company, and populated claim entities and selected observation
entity scopes must match. Apple/PCG IDs remain fixture aliases; any other issuer uses a deterministic
hash-derived company ID. A fixed company-qualified title prevents independent report rebranding.
`snapshot.analysis_id` is the `sha256:`-prefixed canonical hash of the supplied `AnalysisResponse`.

The profile requires one explicit currency across the four primary metrics, a single reporting
period end, and unique metric definitions for secondary ratios. A supplied trend must use the same
currency. The PDF presents an executive summary, four sourced primary metrics, secondary ratios,
one optional trend, review risks, narrative-versus-numbers findings, separate no-causation context,
provenance, limitations, reviewer state, and data handling. Generic issuer context requires an
explicit official-source confirmation, public HTTPS, and fixed non-causal relevance/comparability
sentences. With no reviewed context the report says so;
without a validated forecast method, inputs, history, and uncertainty model it omits a forecast
section. No shareholder or ownership section exists in this contract.

The renderer never emits arbitrary model-authored narrative. Claim sentences come from typed metric
fields, findings must equal a fresh deterministic classifier result, and title, limitations,
context/trend narratives, document labels, and source disclosures use exact reviewed vocabularies.
Attributed evidence quotes and spreadsheet display values are preserved only as evidence rather
than treated as Proofline assertions. Canonical JSON rejects non-string mapping keys before sorting
and normalizes signed float zero.

## Consequences

- PDF and reviewed JSON exports share one validated evidence boundary.
- Cached output stays additive report metadata and does not weaken the frozen v1
  `AnalysisResponse.cached_output = false` contract.
- Unsupported core-font characters are shown as `[U+XXXX]` rather than silently disappearing.
- Layout is deliberately limited to one renderer, one historical chart/table, core fonts, and
  fixture-tested sections.
- Session deletion cannot claim secure erasure, provider deletion, or removal of user-downloaded
  exports.
