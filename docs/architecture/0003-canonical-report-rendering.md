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
bundle carries version identifiers, the full `AnalysisResponse`, reviewed `ReportSnapshot`, at most
one validated historical series, resolved official-source economic context, explicit live/cached
source disclosure, and the narrow export/deletion disclosure.

Canonical JSON uses sorted keys, UTF-8, normalized finite Decimal strings, and UTC `Z` timestamps.
For this stricter report boundary, `ReportSnapshot.evidence_chain_sha256` must equal the SHA-256 of
the complete canonical `AnalysisResponse`, including claims. The PDF itself receives a separate
content SHA-256 and strong ETag. ReportLab invariant mode, fixed metadata, stable ordering, escaped
untrusted text, core fonts, and stable Unicode fallbacks make repeated renders byte-identical.

The renderer is pure: it does not access the network, adapters, metric calculation service, clocks,
or storage. Invalid IDs, counts, evidence hash, context, trend comparability, cache disclosure, or
forecast markers reject the bundle before PDF bytes are returned.

## Consequences

- PDF and reviewed JSON exports share one validated evidence boundary.
- Cached output stays additive report metadata and does not weaken the frozen v1
  `AnalysisResponse.cached_output = false` contract.
- Unsupported core-font characters are shown as `[U+XXXX]` rather than silently disappearing.
- Layout is deliberately limited to one renderer, one historical chart/table, core fonts, and
  fixture-tested sections.
- Session deletion cannot claim secure erasure, provider deletion, or removal of user-downloaded
  exports.
