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
historical series per reviewed company, and a typed ReportLab PDF renderer are implemented. Parsing
and live hosted-model transport remain intentionally stubbed; see the [API contract
notes](docs/api-contracts.md) for the stable frontend boundary and limitations.

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

`GEMINI_API_KEY` is optional and tests never require a live model. The v1 provider defaults to
configured Gemma 4 but intentionally stops before network transport; it is a narrow interface for a
later reviewed adapter.

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

- Inputs must already be normalized facts with provenance IDs; PDF/workbook adapters are protocols,
  not broad parsers yet.
- Only the four Tier 0 metrics are accepted. Arithmetic uses Python `Decimal` and typed allowlisted
  plans; no model-generated code or expressions are executed.
- Fixed prototype tolerances have not yet been validated against the final issuer fixtures.
- There is no database, document-byte upload, OCR, hosted model call, frontend, or production
  privacy/compliance claim in this slice. Session endpoints retain and delete process-local intake
  metadata only; they do not yet run processing adapters. Session deletion cannot remove already
  downloaded PDF or JSON exports.
- `uv.lock` is the fully resolved cross-platform dependency lock; `pyproject.toml` remains the
  human-edited dependency declaration.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md). All material changes should be proposed through a focused pull request.

## License

Licensed under the [MIT License](LICENSE).
