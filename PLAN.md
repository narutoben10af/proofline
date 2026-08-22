# Proofline product and build plan

> **Prototype plan, not a capability claim.** Proofline is a six-hour hackathon build. This plan separates fixed decisions from placeholders and does not claim universal PDF support, production privacy or PDPA compliance, issuer endorsement, or accuracy that has not been measured.

## 1. Product thesis

**Tagline:** Every financial claim needs a receipt.

Proofline asks a sharper question than a generic report summarizer: **does the financial narrative agree with the underlying figures?** It compares selected narrative claims in a PDF with spreadsheet evidence and presents a compact **Proofline Review Desk** and **Visual Verdict**:

- **Supported** — comparable evidence agrees under documented rules.
- **Uncertain** — evidence is missing, ambiguous, incomparable, or extraction failed.
- **Contradicted** — comparable evidence conflicts under documented rules.

Opening a finding shows the original claim, PDF page, spreadsheet sheet/cells, normalized values, deterministic formula, rationale, caveats, and a suggested next investigation. The system identifies the disagreement; it does not infer or invent its cause.

## 2. Lab 1 requirements and product response

The authoritative source is the shared [DevLeague Problem Statements — Lab 1 briefing](https://docs.google.com/document/d/1Wf_rjjnO3IZRY03W3IcOrQ9__-0NLa8hI6pVjL7GZAg/edit?tab=t.0), described in the brief as an Experian-powered AI financial-report analysis challenge.

| Brief requirement | Proofline response for the six-hour build |
| --- | --- |
| Analyze financial PDFs and spreadsheets | One known PDF/spreadsheet pair end to end, plus a second geography through verified fixtures or cached expected results |
| Detect trends, anomalies, exceptions, and risks | Four fixed deterministic metrics; surface a trend, anomaly/exception, and narrative–number contradiction |
| Produce concise summaries and recommendations | A short evidence-bound rationale and next investigation; no invented cause or autonomous financial advice |
| Make conclusions explainable | Page, sheet, cell, normalized inputs, formula, and classification reason shown together |
| Provide a usable interface | Upload/processing flow, compact three-state Review Desk, Visual Verdict, progressive evidence, privacy notice, and deletion receipt |
| Address privacy, Malaysian PDPA, and responsible AI | Public fixtures only for hosted services, basic masking, ephemeral session handling, explicit limitations, and human review |

Success is a polished narrow workflow that genuinely works, not a general financial-analysis platform.

## 3. Users, jobs, and value

### Primary demo user

A financial analyst, reviewer, or diligence team member who needs to find claims worth investigating and trace each result back to source evidence.

### Core job

“Show me where the financial narrative and the numbers agree or disagree, and give me enough evidence to verify it quickly.”

### Value proposition

- Faster triage of a long report.
- Evidence beside every result instead of an opaque summary.
- Clear separation of extracted facts, deterministic calculations, and AI-assisted suggestions.
- Conservative uncertainty when evidence is not strong enough.

### Review Desk user flow

1. The reviewer selects an allowlisted public PDF and its official workbook or clearly labeled derived fixture.
2. A processing view reports native extraction, narrowly scoped fallbacks, schema validation, and deterministic calculations without implying that every page succeeded.
3. The Review Desk presents a compact supported/uncertain/contradicted summary and prioritizes one genuine discrepancy, exception, or insufficient-evidence case as the Visual Verdict.
4. Selecting the verdict reveals a four-step proof trail: **claim → cited inputs → deterministic formula → result**. PDF highlighting and spreadsheet cells appear progressively, not as crowded permanent panels.
5. The reviewer confirms, rejects, or investigates the finding; the prototype does not automate a consequential decision.
6. The reviewer deletes the session and receives a deletion receipt describing the tested deletion scope honestly.

### Visual hierarchy constraints

- Show one dominant discrepancy comparison visual.
- Show at most one historical chart, and only with three or more comparable periods.
- Keep raw source text, cell detail, and technical warnings behind progressive disclosure.
- Do not add a model picker, raw code view, Benford analysis as the hero, crowded permanent panels, or unsupported privacy theatrics.

## 4. Six-hour scope

### Must have

- One known PDF and one known spreadsheet processed end to end.
- The four fixed metrics in section 7.
- At least one trend, one anomaly/exception, and one narrative–number contradiction.
- Evidence for every finding: page plus sheet/cell references where applicable.
- Supported, uncertain, and contradicted states in the Review Desk.
- Public-data notice, basic sensitive-data masking, delete-session control, and cached demo fallback.
- Expected-result fixture checked before the demo.

### Explicitly cut

- General chatbot, forecasting, authentication, persistent database, and unattended decisions.
- Arbitrary spreadsheet formats, universal PDF handling, and broad OCR.
- Multiple currencies/accounting standards beyond what the selected fixtures require.
- Experian integration unless credentials and a usable API are already available.
- Any accuracy, security, compliance, or production-readiness claim.

## 5. Exact six-hour schedule

| Time | Deliverable | Exit check |
| --- | --- | --- |
| 0:00–0:30 | Freeze four metrics, expected demo answers, fixtures, and two-minute script | One supported, one uncertain/anomalous, and one contradicted example are written down |
| 0:30–1:15 | Build upload/processing shell, Review Desk shell, public-data notice, delete-session control/receipt, and cached fallback | Happy path and fallback can be navigated without live parsing |
| 1:15–2:30 | Parse one known workbook and native-text PDF; preserve page/sheet/cell provenance | Expected source locations are recovered from both inputs |
| 2:30–3:30 | Add schema-validated claim extraction and deterministic metric engine | AI returns structured candidates; code alone computes metric values |
| 3:30–4:30 | Complete Visual Verdict and progressive evidence detail | A genuine discrepancy/exception/insufficient-evidence case is dominant; rationale never exceeds evidence |
| 4:30–5:15 | Test malformed input, missing data, masking, model/OCR failure, session deletion, and expected results | Failures become `uncertain`, cached verified output, or a clear error |
| 5:15–6:00 | Rehearse pitch; simplify; capture screenshots/recording backup | Two-minute demo runs twice and all visible numbers match expected fixtures |

## 6. Fixtures and provenance

### International fixture — Apple FY2025

Use the Apple FY2025 Form 10-K PDF and official structured workbook available through the [official filing hub](https://investor.apple.com/sec-filings/sec-filings-details/default.aspx?FilingId=18880179). Supporting official sources:

- [Form 10-K PDF](https://d18rn0p25nwr6d.cloudfront.net/CIK-0000320193/c24e7a28-5254-4dfa-9447-62aaa3c24bb1.pdf)
- [SEC Companyfacts JSON](https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json)
- [SEC EDGAR API documentation and fair-access guidance](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)

The filing hub's Excel file is the structured demo source. Respect SEC fair-access guidance for any API or bulk requests.

### Malaysian fixture — PETRONAS Chemicals Group Berhad FY2025

PETRONAS Chemicals Group Berhad is a non-bank operating-company fixture, avoiding ratios that are structurally poor fits for banks.

- [Official FY2025 Financial Report PDF](https://www.petronas.com/pcg/sites/default/files/uploads/content/2026/IR%20Suite%202025/PCG%20FR2025%20%5BInteractive%20PDF%5D.pdf)
- [Official reports hub](https://www.petronas.com/pcg/investor-relations/reports)
- [Official FY2025 release and HTML financial table](https://www.petronas.com/pcg/media/media-releases/fy2025-results-reflect-challenging-market-pcg-prioritises-operational-and)

No official structured XLS/CSV was identified during research. If needed, create only a minimal project-owned CSV/JSON of audited line items with attribution and PDF page anchors. Label it **derived fixture**, never “official spreadsheet.”

### Reuse policy

- Do not commit full PDFs publicly until reuse terms are checked.
- Prefer setup-time downloads and minimal attributed factual rows.
- Record URL, retrieval date, reporting period, units, currency, scope, page/sheet/cell, and whether a row is official or derived.
- Use of public filings does not imply issuer endorsement.

## 7. Versioned deterministic metric registry

All authoritative arithmetic runs in deterministic code. Gemma may extract candidate inputs or claims, but never supplies the final calculation.

Each registry entry has a stable metric ID, semantic version, display name, deterministic formula identifier, required input concepts, unit/period/scope constraints, denominator policy, tolerance policy, applicability tags, and test fixtures. Findings store the exact registry version used so later rule changes do not rewrite history.

### Tier 0 — required for the demo

| Metric | Formula | Required caveats |
| --- | --- | --- |
| Revenue growth YoY | `Revenue_t / Revenue_t-1 - 1` | Period length (including 52/53-week years), restatements, scope and currency changes, zero/negative prior revenue |
| Operating margin | `Operating profit or loss / Revenue` | Issuer definition, impairments or unusual items, segment/group scope, zero/negative revenue |
| Current ratio | `Current assets / Current liabilities` | Reporting date, classification changes, zero/negative liabilities, poor applicability to banks |
| Free-cash-flow margin | `(Net cash from operating activities - cash purchases of PPE/capex) / Revenue` | **Project-defined non-GAAP metric**; show formula, capex sign convention, scope, period, zero/negative revenue |

Never silently compare unlike currencies, periods, scopes, units, restated bases, or definitions. If comparability cannot be established, return `uncertain`.

### Tier 1 — optional stretch

Implement at most **gross margin** and **inventory days**, and only when the chosen fixture exposes clean, comparable inputs. They must use the same versioned registry, deterministic Decimal functions, provenance, applicability tags, and edge-case tests as Tier 0. Tier 1 work cannot displace a reliable Tier 0 demo.

### Tier 2 and Tier 3 — roadmap only

- **Tier 2:** broader sector-specific liquidity, leverage, efficiency, cash-conversion, and return metrics after cross-industry applicability research and labeled evaluation.
- **Tier 3:** management-accounting measures that depend on internal cost allocation, budgets, operational drivers, or non-public ledgers.

The registry must label metrics as broadly comparable, sector-limited, entity-specific, or management-accounting-only. Banks remain outside the initial fixture scope because the Tier 0 set is structurally unsuitable for them.

## 8. Contradiction and uncertainty rules

### Normalization record

Every comparison records original display value, parsed numeric value, currency, unit/magnitude, period start/end, duration, entity/scope, restatement status, sign convention, and source location.

### Decision sequence

1. Require a claim with sufficient entity, metric, period, and direction/value context.
2. Find candidate evidence with compatible identity, scope, period, currency, and units.
3. Calculate the applicable metric in code from cited inputs.
4. Apply a documented tolerance appropriate to display precision. **The actual tolerance is a pre-build decision and must be fixture-tested; it must not be improvised during the demo.**
5. Classify:
   - `supported` when comparable evidence agrees within tolerance;
   - `contradicted` when comparable evidence conflicts beyond tolerance; or
   - `uncertain` for missing, ambiguous, low-confidence, incomparable, failed, zero-denominator, or unresolved-sign cases.
6. Display the source inputs, formula, normalized result, tolerance, and reason.

Qualitative causation claims are out of scope unless directly evidenced; Proofline may recommend an investigation but must not manufacture a cause.

## 9. Parsing, OCR, and model path

### PDF extraction cascade

1. Extract native text first with PyMuPDF or pdfplumber.
2. Detect scanned or failed pages using explicit quality checks.
3. Apply PaddleOCR PP-StructureV3 only to those pages.
4. Use hosted Gemma 4 image analysis only for isolated failures; validate output against the page and schema.
5. Fall back to cached, human-verified demo JSON when the live path fails.

PaddleOCR is the likely China-origin OCR project the user recalled (from Baidu, not Xiaomi). Sources: [official documentation](https://www.paddleocr.ai/main/en/index.html), [PP-StructureV3 guide](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md), and [Apache-2.0 repository](https://github.com/PaddlePaddle/PaddleOCR). This selection is a six-hour implementation choice, not a “best OCR” claim.

Post-hackathon candidates to benchmark include PaddleOCR-VL 1.6 and MinerU. Their adoption remains a placeholder until a representative benchmark measures extraction and provenance quality.

### Gemma 4

Use `gemma-4-26b-a4b-it` through the Gemini API for the prototype. Official sources: [Gemma overview](https://ai.google.dev/gemma/docs/core), [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4), [Gemma on Gemini API guide](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api), and [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing).

The cited model card/API guide describe multimodal input, function calling, and context up to 256K. Use a function declaration plus Zod or Pydantic validation for structured extraction. Retry once on invalid output; then use cached verified fixtures or report a clear failure. Never let model output become authoritative arithmetic, classification, or uncited evidence.

Gemma 4 is the configured prototype default behind a narrow server-side provider interface such as `extract_claims(input, schema, context)`. Later providers must implement the same bounded contract and validation. There is no model picker in the prototype UI. Do not describe access as free or unlimited: quotas, terms, pricing, and data-use conditions can change and must be checked at deployment time.

## 10. Architecture and data flow

```text
Public PDF -----------------> native text + page spans --+
       \-> failed pages -> PaddleOCR/Gemma fallback -----+-> candidate claim schema
                                                        |
Official workbook / derived fixture -> normalized facts +-> deterministic metric engine
                                                        |
                          comparison policy <-----------+
                                    |
                 finding + evidence + calculation + warnings
                                    |
                       Review Desk + Visual Verdict
```

Prototype components:

- **Session/UI:** accepts approved files, shows status/privacy notice, renders the compact Review Desk/Visual Verdict, progressively reveals evidence, and issues a deletion receipt.
- **Document adapter:** page-aware native extraction and narrow failure detection.
- **OCR/model adapter:** isolated fallback with timeout, quota, one retry, and schema validation.
- **Workbook adapter:** reads known sheets/cells/formulas/cached values and emits normalized facts.
- **Metric engine:** a versioned allowlist of precompiled Decimal functions with explicit exceptional states.
- **Matcher/policy:** connects claims to comparable facts and applies contradiction rules.
- **Evidence store:** in-memory or session-temporary records only for the prototype; no persistent database.
- **Cached demo:** versioned, human-verified expected JSON for a reliable presentation fallback.

### Safe calculation boundary

Reject model-generated executable Python, SQL, shell, or JavaScript. A model may emit only a typed calculation plan or a tiny allowlisted expression tree whose operators, metric IDs, inputs, and units are validated before dispatch to precompiled Decimal functions. Unknown nodes, unexpected fields, excessive depth, non-finite values, and disallowed concepts fail closed to `uncertain` or a clear error.

Validate upload signatures as well as extensions, enforce file/count/page/cell/size/time limits, reject encrypted inputs, and reject macro-enabled workbooks for the prototype. Never log document contents, extracted passages, cell values, model prompts containing source material, or secrets.

### Demo hosting and storage

- Run one FastAPI container that serves both the API and built React assets.
- Use app-managed per-session temporary directories with random IDs, restrictive permissions, explicit lifecycle state, and TTL cleanup. No database is in the six-hour critical path.
- Use public fixtures only and deploy the container to Railway or an equivalent container host. See [FastAPI deployment concepts](https://fastapi.tiangolo.com/deployment/concepts/) and [Railway Dockerfile deployment](https://docs.railway.com/guides/dockerfiles).
- Sites may host a visual prototype or internal shell, but it is not the native Python/OCR backend.
- Standard Cloudflare Workers are not the parser host. Cloudflare can later provide an edge/frontend/gateway layer subject to documented [Workers limits](https://developers.cloudflare.com/workers/platform/limits/).
- Post-hackathon accounts, history, and private documents may use Supabase Auth, private Storage, and Postgres with RLS after a real threat/data-flow review. Official references: [Storage access control](https://supabase.com/docs/guides/storage/security/access-control) and [Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security).

Consequential decisions belong in `docs/architecture/`.

## 11. Provisional schemas

```ts
type SourceRef =
  | { kind: "pdf"; documentId: string; page: number; quote: string }
  | { kind: "spreadsheet"; workbookId: string; sheet: string; cell: string; displayValue: string };

type FinancialClaim = {
  id: string;
  text: string;
  entity: string | null;
  metric: "revenue_growth_yoy" | "operating_margin" | "current_ratio" | "fcf_margin";
  period: { start?: string; end: string; durationWeeks?: number };
  assertedValue?: number;
  assertedDirection?: "up" | "down" | "flat";
  unit?: string;
  currency?: string;
  source: SourceRef;
  extractionWarnings: string[];
};

type NormalizedFact = {
  concept: string;
  numericValue: number;
  displayValue: string;
  unit: string;
  currency?: string;
  period: { start?: string; end: string; durationWeeks?: number };
  entityScope: string;
  restated: boolean | null;
  source: SourceRef;
  fixtureStatus: "official" | "derived";
};

type Finding = {
  claimId: string;
  classification: "supported" | "uncertain" | "contradicted";
  rationale: string;
  metric: { name: string; formula: string; inputs: NormalizedFact[]; result?: number; tolerance?: number };
  evidence: SourceRef[];
  warnings: string[];
  suggestedInvestigation?: string;
};
```

These contracts are provisional until they pass the two fixtures and failure cases.

### Immutable evidence and history chain

Persist or serialize history as append-only records linked in this order:

```text
DocumentVersion -> SourceSpan -> FactObservation -> MetricResult -> Finding
```

- `DocumentVersion` identifies content hash, issuer, source URL, retrieval time, reporting basis, and version label.
- `SourceSpan` anchors an immutable page region or workbook cell/range to that version.
- `FactObservation` records the raw display value plus normalized value, unit, currency, period, scope, and restatement status.
- `MetricResult` records registry ID/version, cited observations, Decimal result, exceptional state, and calculation timestamp.
- `Finding` records the policy version, comparison target, label, rationale, warnings, and reviewer action without mutating ancestors.

The UI must distinguish **as published** from **latest restated** views. Never splice a restated observation into an as-published chain without an explicit view change. A trend requires at least three comparable points under the same documented basis; otherwise show a point comparison or `uncertain`, not a trend line.

Forecasting is roadmap-only and lives in a separate UI from historical findings. Any future forecast must use a documented deterministic baseline, backtesting, prediction intervals, explicit assumptions, and separate actual/forecast provenance. AI narrative cannot substitute for these controls.

## 12. Privacy, PDPA, security, and responsible AI

### Hard prototype boundary

Only public hackathon fixtures may be sent to hosted Gemma 4. Current [Gemini API pricing/data-use information](https://ai.google.dev/gemini-api/docs/pricing) says free-tier pricing and rate limits can change, and free-tier content may be used to improve Google products; research did not identify a paid privacy tier for hosted Gemma 4. Never upload confidential customer statements through this path.

### Controls to implement

- Public-data notice and explicit fixture allowlist.
- Basic masking before display/logging; do not imply this makes arbitrary documents safe.
- Server-side model calls only; `GEMINI_API_KEY` comes from environment configuration.
- `.env.example` contains variable names and safe non-secret defaults only; `.env` stays ignored.
- Store deployed secrets in the hosting provider's secret manager, separate development/staging/production environments, and enable repository secret scanning and push protection where available. See [GitHub push protection](https://docs.github.com/en/code-security/secret-scanning/introduction/about-push-protection).
- Never place a model key, service-role key, database credential, or other privileged secret in React assets, browser storage, source maps, logs, screenshots, or public fixtures.
- Apply quotas, timeouts, and one retry at the server-side provider boundary.
- Minimal logs without document text or spreadsheet values.
- Ephemeral session files and a visible delete-session control; verify deletion behavior.
- No training, storage, compliance, or confidentiality assurance beyond what is tested and documented.
- Human review, evidence inspection, and conservative uncertainty.

PDPA is a design constraint, not a certification claim. Before any non-public data use, perform a real data-flow/retention assessment, establish purpose and lawful handling, choose an appropriate processing tier, document subprocessors and cross-border transfers, and implement enforceable deletion/access controls.

## 13. Testing and acceptance criteria

### Fixture tests

- All four metrics match independently verified expected values.
- One supported, one uncertain, and one contradicted case render with correct evidence.
- PDF page and workbook sheet/cell provenance match manual inspection.
- Derived Malaysian rows are labeled `derived` and include attribution/page anchors.
- The hero finding is a genuine mismatch, exception, or insufficient-evidence result from the fixture. If a synthetic variant is ever used, every affected screen and narration labels it prominently as synthetic; never silently alter a real issuer report.

### Edge and failure tests

- 52/53-week period, restatement, scope/currency mismatch, impairments, capex sign, and zero/negative denominator.
- Missing sheet/cell, formula without usable cached value, merged cells, malformed file, scanned page, and extraction quality failure.
- Invalid model JSON, timeout, rate limit, failed OCR, unavailable network, and cached fallback.
- Typed-plan/expression-tree rejection, macro-enabled and encrypted inputs, mismatched signatures, size/complexity limits, and assurance that logs contain no document content.
- Secret does not reach client bundle/logs; public-data notice appears; masking and delete-session controls behave as documented.

### Demo acceptance criteria

- End-to-end known fixture completes or switches clearly to cached verified output.
- Every decisive label has inspectable comparable evidence and a deterministic calculation.
- Ambiguity never becomes a fabricated match or contradiction.
- Two rehearsed runs reproduce the expected visible results.
- No UI text claims universal support, issuer endorsement, production privacy, PDPA compliance, or unmeasured accuracy.

## 14. Key risks

| Risk | Mitigation |
| --- | --- |
| Extraction drops context, units, or page identity | Retain source spans; inspect known pages; route failures conservatively |
| Similar labels create false matches | Require compatible entity/metric/period/scope; otherwise `uncertain` |
| Rounding creates false contradictions | Fixture-tested tolerance shown in evidence detail |
| Restatement or 52/53-week basis distorts comparison | Store basis explicitly; block comparison when unresolved |
| Capex sign produces wrong FCF | Normalize cash-purchase convention and show formula/inputs |
| Model emits plausible but wrong structure | Schema validation, source verification, one retry, verified cache |
| API rate limit or network breaks demo | Timeouts and cached expected JSON |
| Confidential data reaches a free hosted tier | Public fixture allowlist; explicit warning; no customer data |
| Reviewer over-trusts output | Evidence-first UI, human review, no invented cause, prominent prototype limits |
| Source reuse is unclear | Setup-time downloads; do not commit PDFs before terms check |

## 15. Two-minute demo script

1. **Hook:** “Reports become dangerous when confident commentary contradicts the numbers.”
2. Introduce Proofline: “Every financial claim needs a receipt.”
3. Select the approved public PDF and structured fixture; point out the public-data boundary and session deletion.
4. Show processing: native text, structured values, schema-validated claim extraction, deterministic calculations.
5. Reveal the compact Review Desk and its supported, uncertain, and contradicted summary.
6. Open the red contradiction: show the exact statement, PDF page, cells, normalized inputs, formula, result, and tolerance.
7. Explain that Proofline flags disagreement without inventing a reason; show the next investigation.
8. Open the uncertain case to demonstrate conservative behavior.
9. Delete the session.
10. Close: “Other tools summarize the report. Proofline tells you whether the report deserves to be trusted.”

If live processing fails, state prominently that the app is using versioned, human-verified cached demo output; do not disguise the fallback. Never modify an issuer document to manufacture the hero contradiction without equally prominent synthetic labeling.

## 16. Pull-request roadmap

1. **Bootstrap:** minimal README/license and default branch required to create the repository.
2. **Docs foundation:** this plan, contribution/security policies, ADRs, and templates.
3. **Fixture contracts:** download instructions, attribution manifest, derived-fixture generator, and expected JSON; no full PDFs until terms review.
4. **Deterministic metric engine:** schemas, normalization, four metrics, exceptional states, and unit tests.
5. **Parsing adapters:** workbook/native PDF path with provenance and narrow PaddleOCR fallback.
6. **Gemma adapter:** server-side function call, validation, timeout/quota/retry, and cache fallback.
7. **Review Desk UI:** compact summary, Visual Verdict, optional three-period chart, proof trail, progressive evidence, deletion receipt, warnings, and accessibility.
8. **Demo hardening:** integration tests, screenshots/recording, script, known limitations, and verification report.

Every PR must state validation performed, evidence/classification impact, privacy/security impact, and any unverified assumptions.

### Backend-first implementation after this plan PR merges

Do not begin backend implementation before the plan PR is reviewed and merged. Then sequence implementation as follows:

1. Freeze versioned schemas, the immutable evidence chain, metric-registry shape, and API contracts.
2. Implement the fixture manifest, parser, provenance anchors, and normalizer.
3. Implement precompiled Decimal metrics and exceptional-state tests.
4. Implement the narrow server-side Gemma provider adapter with typed/schema validation and cached fallback.
5. Implement deterministic matching and classification policy.
6. Complete unit, fixture, failure, security-boundary, and integration tests.
7. Only then build the React Review Desk against the frozen API contracts.

## 17. Long-term roadmap placeholders

These are hypotheses, not commitments:

- Benchmark PaddleOCR-VL 1.6, MinerU, and other extractors on representative financial pages.
- Expand metric and claim coverage only after labeled evaluation.
- Support more spreadsheet layouts, currencies, accounting bases, and languages.
- Add review collaboration, overrides, audit history, and exportable evidence packs.
- Add scheduled monitoring and version-to-version report comparison.
- Evaluate private deployment/model options before confidential data.
- Add enterprise identity, authorization, retention policies, regional processing, and integrations.
- Explore forecasting only as a separately labeled analytical feature with its own validation.
- Evaluate deterministic forecasting baselines with backtests, intervals, and explicit assumptions before any forecast UX.
- Consider Experian integration only with documented product fit, credentials, permissions, and data terms.

## 18. Pre-build decisions still required

- [ ] Confirm reuse terms and retrieval method for both fixture sets.
- [ ] Record the exact workbook tabs/cells and PDF pages used in the demo.
- [ ] Approve expected results and the fixture-tested contradiction tolerance.
- [ ] Choose PyMuPDF or pdfplumber after a short comparison on the actual pages.
- [ ] Choose the UI/runtime stack and validate server-side secret handling.
- [ ] Define extraction-quality gates that trigger OCR, Gemma fallback, or `uncertain`.
- [ ] Define and verify masking and session-deletion behavior.

## 19. Source index

- [DevLeague Problem Statements — Lab 1](https://docs.google.com/document/d/1Wf_rjjnO3IZRY03W3IcOrQ9__-0NLa8hI6pVjL7GZAg/edit?tab=t.0)
- [Apple FY2025 filing hub](https://investor.apple.com/sec-filings/sec-filings-details/default.aspx?FilingId=18880179)
- [Apple FY2025 Form 10-K PDF](https://d18rn0p25nwr6d.cloudfront.net/CIK-0000320193/c24e7a28-5254-4dfa-9447-62aaa3c24bb1.pdf)
- [SEC Apple Companyfacts JSON](https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json)
- [SEC EDGAR APIs and fair access](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [PETRONAS Chemicals Group FY2025 Financial Report](https://www.petronas.com/pcg/sites/default/files/uploads/content/2026/IR%20Suite%202025/PCG%20FR2025%20%5BInteractive%20PDF%5D.pdf)
- [PETRONAS Chemicals Group reports hub](https://www.petronas.com/pcg/investor-relations/reports)
- [PETRONAS Chemicals Group FY2025 release](https://www.petronas.com/pcg/media/media-releases/fy2025-results-reflect-challenging-market-pcg-prioritises-operational-and)
- [PaddleOCR documentation](https://www.paddleocr.ai/main/en/index.html)
- [PaddleOCR PP-StructureV3 guide](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md)
- [PaddleOCR repository and license](https://github.com/PaddlePaddle/PaddleOCR)
- [Gemma overview](https://ai.google.dev/gemma/docs/core)
- [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
- [Gemma on Gemini API](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api)
- [Gemini API pricing and data use](https://ai.google.dev/gemini-api/docs/pricing)
