# Generic issuer pipeline gap matrix

Audit base: `cf87b612d844356f2e2ce1baf677a116cc8e8543` (`main` / `origin/main` on
2026-08-22).

Additional read-only inputs:

- deterministic ingestion commit `ef4856edf5c551e05662b17506aed4133fe152af`
- temporary storage commit `a1e516ffdbc0cf7d67c995725fbaff43c95ee530`
- provider-boundary commit `1c96eec44a280bf302a6e35f137cee30df6cad27`
- merged economic/report code on `main`
- frontend adapter and source-library integration contracts on the commits above

| Pipeline stage | What exists | Generic-issuer gap | Consequence | This slice |
| --- | --- | --- | --- | --- |
| Upload/storage | The storage branch validates bounded PDF/XLSX packages and retains opaque process-local files behind capability/CSRF controls. | Storage has no processing callback or public byte-stream handoff into ingestion, and is not merged into `main`. | A safe upload can become `Ready`, but cannot become evidence or facts. | No storage merge; preserve a byte-oriented normalizer seam that a later orchestrator can call after authorization. |
| PDF ingestion | `ef4856e` extracts bounded native text with page citations and optional injected OCR. | Output is page text, not structured statement rows; sparse/scanned pages require external OCR. | PDF narrative can be cited, but deterministic financial facts cannot generally be recovered from arbitrary PDF tables. | Port the generic adapter unchanged; treat PDF pages as evidence, not inferred metric inputs. |
| XLSX ingestion | `ef4856e` validates packages, rejects macros, does not execute formulas, and emits cited non-empty cells. | No issuer, scope, period, currency, scale, concept, sign, or restatement binding. Cached formula absence is only a cell warning. | Extracted numbers are unsafe for comparison or calculation. | Port the adapter and add deterministic, layout-neutral matrix normalization. |
| Entity binding | `DocumentVersion.issuer` and `FactObservation.entity_scope` exist. | No resolver binds uploaded content to either field; multiple candidates are not handled. | Cross-entity mixing is possible if callers manufacture facts. | Require one explicit issuer and one explicit entity-scope value; fail closed on missing/conflicting values. |
| Period binding | `Period` supports duration and instant facts; metrics enforce adjacency/comparability. | No date/header parser maps table axes to periods. | A number cannot be assigned safely to current/prior roles. | Resolve ISO dates and unambiguous FY/calendar-year headers on either table axis; preserve inference warnings. |
| Currency/unit binding | Facts carry ISO currency and a unit string; metrics reject unequal strings. | No scale parser converts thousands/millions/billions into a canonical numeric basis; symbols are ambiguous. | Equal economics with different display scales compare incorrectly; unknown symbols can be misclassified. | Require explicit ISO currency and scale, normalize all monetary facts to currency base units, and retain original display/provenance. |
| Concept/sign binding | Tier-0 registry supports revenue, operating profit, current assets/liabilities, operating cash flow, and capex. | No conservative label vocabulary or duplicate-resolution policy. | Wrong line items can silently feed formulas. | Use a small generic alias registry, exact normalized-label matching, deterministic sign handling, and reject duplicate concept/period candidates. |
| Provenance/confidence | `SourceSpan` cites a page or cell. Provider contracts require claim citations. | `FactObservation` has only one source span and no extraction confidence/warnings. | Metadata/header evidence and normalization uncertainty are lost. | Add a normalization envelope with all contributing span IDs, confidence, and structured warnings while retaining the value-cell span as the primary fact citation. |
| Fact contract semantics | `FactObservation` is the required input to the Tier-0 calculator. | Its required `fixture_status` field is named for demos and permits only `official`/`derived`; there is no upload-normalized provenance state. | Upload-derived facts must currently use the semantically closest legacy value, `derived`. | Preserve calculator compatibility in this slice; a versioned contract migration remains necessary before exposing normalized facts as a public API. |
| Metric planning | Tier-0 registry and deterministic calculator exist and fail closed on missing, incomparable, sign, and denominator states. | Calculation plans are hand-authored fixture data. | Uploaded facts never reach deterministic metric inputs. | Generate plans only for uniquely resolved, comparable inputs; omit unsafe plans and emit warnings. |
| Claims/findings | Classification is deterministic once a cited claim and metric result exist. The provider branch can produce cited claims but is not merged. | No offline generic claim extraction exists; live model inference is out of scope. | Arbitrary uploads cannot yet generate review findings without an injected/human claim. | Do not infer claims. Expose normalized facts/plans for the existing analysis service or a later reviewed/provider claim seam. |
| Reports | Merged report code deterministically renders a complete, reviewed `ReportRenderBundle`. | No orchestration builds a report bundle from an upload session, normalized facts, claims, findings, and review state. | Report generation is available but not end-to-end wired. | No report changes; normalization output is compatible with existing `FactObservation` and `MetricCalculationPlan`. |
| Demo fixtures | Apple/PCG economic lenses and session fixture IDs are explicitly demo-only. Frontend uses a Northstar mock adapter. | Fixture selectors and economic-context lookup are closed enumerations, not issuer discovery. | Demo data must not be mistaken for generic processing. | Add no issuer files or name conditionals; synthetic tests use unrelated issuers/currencies/layouts. |

## Acceptance boundary for this slice

The implementation is successful when two structurally different synthetic workbooks for
different issuers and ISO currencies produce canonical base-unit facts and safe Tier-0 plans,
and conflicting metadata or duplicate fact candidates produce no unsafe output. It does not
claim universal PDF-table understanding, claim extraction, upload orchestration, or automatic
report publication.
