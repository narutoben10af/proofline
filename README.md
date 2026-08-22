# Proofline

**Every financial claim needs a receipt.**

Proofline is a six-hour hackathon prototype for comparing narrative claims in financial-report PDFs with figures in spreadsheets. Its intended output is an evidence-backed classification for each claim:

- **Supported** — the available spreadsheet evidence agrees with the claim.
- **Uncertain** — the available evidence is missing, ambiguous, or insufficient.
- **Contradicted** — the available spreadsheet evidence conflicts with the claim.

> [!IMPORTANT]
> Proofline is a prototype, not an accounting, audit, investment, or compliance tool. Human review remains required. No production implementation or evaluation results are claimed in this repository yet.

## Why Proofline

The proposed **Proofline Review Desk** turns each review into a compact **Visual Verdict**: a three-state summary, one dominant discrepancy comparison, an optional three-period trend, and a four-step proof trail from claim to cited inputs to deterministic formula to result. PDF and spreadsheet evidence appears progressively when the reviewer asks for it. Proofline identifies evidence and disagreement; it does not invent a cause or make an accounting conclusion.

The product is designed around the DevLeague Lab 1 brief: combine financial PDFs and spreadsheets, surface trends, anomalies, exceptions, and risks, communicate concise insights and recommendations, retain explainable evidence, and make privacy and responsible-AI controls visible. The [full plan](PLAN.md) maps those broad requirements to a deliberately narrow six-hour build.

## Status

The repository now includes a minimal contract-first FastAPI backend plus the isolated Company
Lens and deterministic reporting slice. Versioned JSON contracts, four deterministic Tier 0
metrics, conservative classification, official-source FY2025 economic context fixtures, one
historical series per reviewed company, native PDF/XLSX evidence extraction, deterministic workbook
normalization, and a typed ReportLab PDF renderer are implemented. OCR and live hosted-model
transport remain optional boundaries. The optional server-side Gemma 4 transport is implemented
behind bounded, cited, provider-neutral contracts and stays disabled without a server credential;
see the [API contract notes](docs/api-contracts.md) and [ingestion limits](docs/ingestion.md) for
the stable frontend boundary and limitations.

The temporary Source Library adds strict PDF/XLSX intake under private process-local capabilities,
30-minute idle/two-hour absolute cleanup, and scoped deletion receipts. It uses no database and is
single-process/single-worker only. It is not supported for confidential production input; see
[ADR 0004](docs/architecture/0004-temporary-process-local-source-library.md).
PDFs with forms, name trees, or additional actions are exposed to downstream processing only after
a bounded page-only static derivative is rebuilt and passes the strict validator again. The
unchanged upload is retained in the opaque session directory only as sealed provenance, with its
SHA-256, the derivative SHA-256, sanitizer version, and warning recorded in process-local state;
preview/download and future parser/provider paths receive only the derivative. Session/file deletion
removes both copies. Catalog JavaScript/Launch/external-navigation actions that are not isolated
behind a stripped interactive surface remain rejected.

A standalone, disabled-by-default Supabase Google Auth handoff is documented in
[`docs/supabase-google-auth.md`](docs/supabase-google-auth.md). It does not alter the product shell,
enable a provider, or add credentials; public previews truthfully report sign-in as not configured.

The same FastAPI process also exposes a tool-only, read-only MCP endpoint at `/mcp`. Its exact
standard `search` and `fetch` tools cover only the public reviewed Apple and PCG demo corpus;
they do not expose uploaded document bytes, secrets, private database state, or mutations. See
[the MCP server guide](docs/mcp.md) for the contract, local verification, generic MCP setup, and
ChatGPT Developer Mode steps.

## Intended demo flow

1. Load one approved financial-report PDF and a related spreadsheet or clearly labeled derived fixture.
2. Extract candidate narrative claims with page-level provenance using native text first and narrowly scoped fallbacks.
3. Identify relevant spreadsheet cells and normalize comparable values.
4. Calculate four fixed metrics in deterministic code; AI never supplies authoritative arithmetic.
5. Compare claims with evidence and display the classification, rationale, calculation, and source references for human review.

## Six-hour technical path

- Native PDF text extraction first with PyMuPDF or pdfplumber.
- PaddleOCR PP-StructureV3 only for scanned or failed pages.
- Hosted `gemma-4-26b-a4b-it` through the Gemini API for structured claim extraction and isolated failed-page analysis, validated against a schema.
- One retry, then a cached verified demo result rather than an unvalidated answer.
- Deterministic calculations for revenue growth, operating margin, current ratio, and a clearly labeled project-defined non-GAAP free-cash-flow margin.
- A single FastAPI container serving the API and built React assets, with per-session temporary storage and TTL cleanup; no database is required for the six-hour path.

This is the selected prototype path, not a claim of universal PDF support, OCR superiority, or measured accuracy. See [PLAN.md](PLAN.md) for formulas, fixtures, failure rules, privacy limits, and source links.

## Demo fixtures

- International: Apple FY2025 Form 10-K PDF plus the official structured workbook available from [Apple's filing hub](https://investor.apple.com/sec-filings/sec-filings-details/default.aspx?FilingId=18880179).
- Malaysian: PETRONAS Chemicals Group Berhad FY2025 [financial report](https://www.petronas.com/pcg/sites/default/files/uploads/content/2026/IR%20Suite%202025/PCG%20FR2025%20%5BInteractive%20PDF%5D.pdf) plus a future, minimal project-owned **derived fixture** with page-level attribution. No official structured XLS/CSV has been identified for this fixture, so it must never be described as an official spreadsheet.

Full PDFs will not be committed until reuse terms are checked. Setup-time downloads and minimal attributed factual rows are preferred. Selection of these public filings does not imply issuer endorsement.

## Evidence principles

- Preserve source provenance throughout the workflow.
- Distinguish missing evidence from contradictory evidence.
- Make the comparison rationale inspectable.
- Prefer conservative classifications when extraction or matching is ambiguous.
- Never present the prototype's output as a substitute for professional judgment.

## Privacy boundary

Only public hackathon fixtures may be sent to hosted Gemma 4. According to the current [Gemini API pricing and data-use terms](https://ai.google.dev/gemini-api/docs/pricing), free-tier limits may change and free-tier content may be used to improve Google products; the research did not identify a paid privacy tier for hosted Gemma 4. Proofline therefore makes no production privacy or PDPA-compliance claim and must never send confidential customer statements through this prototype path.

## Repository map

- [`PLAN.md`](PLAN.md) — researched six-hour prototype plan and open build decisions
- [`docs/architecture/`](docs/architecture/) — architecture decision records (ADRs)
- [`docs/decisions/`](docs/decisions/) — retained legacy ADR template from the repository bootstrap
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contribution and pull-request workflow
- [`SECURITY.md`](SECURITY.md) — security policy and private reporting guidance
- [`docs/privacy/`](docs/privacy/) — Malaysian PDPA readiness analysis, non-publishable data-handling draft, data-flow register, incident runbook, and review gate (not legal advice or a compliance claim)

## Getting started

Python 3.12 is the tested runtime. Install
[uv](https://docs.astral.sh/uv/getting-started/installation/), sync the fully resolved lockfile,
run the tests, and start the API:

```bash
uv sync --locked --extra dev
uv run --locked --extra dev pytest
uv run --locked uvicorn proofline.api:app --reload
```

Open `http://127.0.0.1:8000/docs`, check `GET /health`, or submit the request portion of
`tests/fixtures/tier0_analysis.json` to `POST /api/v1/analyses`. Regenerate checked-in schemas with:

```bash
PYTHONPATH=src .venv/bin/python scripts/export_contracts.py
```

`GEMINI_API_KEY` is optional and tests never require a live key or network call. When configured,
the v1 provider calls only the fixed allowlisted Gemini Developer API endpoints for the two
supported Gemma 4 model identifiers. It returns locally schema-validated, cited results and typed
offline/error states; see [the provider boundary](docs/model-provider.md).

The compact fixture-backed lenses are available at `GET /api/v1/company-lenses/apple-fy2025` and
`GET /api/v1/company-lenses/pcg-fy2025`. `POST /api/v1/reports/pdf` accepts the complete immutable
`ReportRenderBundle`; it returns an attachment with `ETag`, `X-Content-SHA256`, and `no-store`.
Use `?output=evidence-json` on the same endpoint for the reviewed canonical JSON fallback. Rendering
never fetches a source, refreshes economic data, recalculates a metric, or creates a forecast.
Apple and PCG are demo fixtures, not a report issuer allowlist: uploaded issuers use a deterministic
company ID and the same typed renderer. The bundle selects four sourced primary observations and
four secondary ratios, enforces one issuer/currency/period boundary, and can explicitly render the
absence of reviewed economic context. It does not render shareholder, ownership, recommendation,
or unsupported forecast assertions.

### Current limitations

- Native PDF pages and structural XLSX cells can be extracted with portable provenance. Explicitly
  labeled row-oriented or transposed workbooks can be normalized into base-unit Tier-0 facts and
  calculation plans; unsupported or ambiguous metadata/layouts remain a reviewed mapping step.
- Only the four Tier 0 metrics are accepted. Arithmetic uses Python `Decimal` and typed allowlisted
  plans; no model-generated code or expressions are executed.
- Fixed prototype tolerances have not yet been validated against the final issuer fixtures.
- There is no database, durable retention, bundled OCR runtime, hosted model call, authentication, or production
  privacy/compliance claim. The separate temporary Source Library accepts narrowly validated PDF/XLSX
  bytes in one running process; its explicit `/api/sessions/{session_id}/analysis` boundary runs
  only the local, reviewed digital-text/XLSX path and never sends uploaded material to a provider.
- Automatic report-bundle publication, narrative claim extraction beyond the small explicit PDF claim
  grammar, arbitrary PDF-table reconstruction, and public upload-normalized contract versioning remain
  future work. Unsupported, scanned, formula-bearing, or ambiguous uploads fail closed for review.
  Session deletion cannot remove PDF or JSON exports already downloaded by users.
  The optional hosted model accepts only explicitly selected, bounded public-fixture evidence and is
  disabled by default; provider-held data is outside session deletion scope.
- `uv.lock` is the fully resolved cross-platform dependency lock; `pyproject.toml` remains the
  human-edited dependency declaration.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md). All material changes should be proposed through a focused pull request.

## License

Licensed under the [MIT License](LICENSE).
