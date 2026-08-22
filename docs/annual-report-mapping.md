# Annual-report mapping boundary

Proofline can map a validated annual-report PDF and companion XLSX workbook without an
issuer-specific adapter. The workbook remains the authoritative normalized input for arithmetic.
The PDF mapper only corroborates a typed Tier-0 plan and creates a bounded, resolving page citation.

## Deterministic flow

1. Safe admission validates the uploaded files. If admission produced a static page-only PDF
   derivative, analysis reads that derivative and propagates its warning; it never reads the retained
   original.
2. The structural workbook adapter rejects formulas, warnings, ambiguous identity metadata, and
   incomplete fact mappings before calculations.
3. Long-report discovery reads at most 500 pages, 25 MiB of PDF bytes, 12,000 text characters per
   page, 4 MiB of discovery text, and ten seconds of elapsed discovery work. It retains at most 32
   high-scoring pages under the existing 250-page parser-selection ceiling.
4. Generic statement titles, concept labels, issuer text, currency declarations, entity scope, and
   reporting years select candidates. Conflicting issuer, currency, period, narrative value, or
   provenance signals fail closed.
5. A table claim is created only when every workbook observation is found in its concept-local
   report block. The model does not author numbers, formulas, code, or mapping rules.
6. The response embeds the claims, observations, documents, and PDF/workbook source spans needed
   to resolve every returned citation.

## Local unchanged-report probe

The three source PDFs are local, git-ignored evaluation inputs. They are not committed or
redistributed because public availability does not establish reuse rights. Companion workbooks used
for this probe were generated locally from the manifest's reviewed source anchors and were also not
committed.

| Unchanged PDF | Result | Reason |
| --- | --- | --- |
| `pcg_fy2025_financial_report.pdf` | Three dynamic, uncertain findings | Safe admission rebuilt the interactive report as a static page-only derivative. Revenue growth, operating margin, and current ratio were corroborated on one selected statement page, every claim resolved to a PDF span, and the sanitizer warning correctly forced `uncertain`. FCF margin remained omitted because its numerator and denominator are split across different report pages and the current claim contract has one primary PDF span. |
| `maybank_fy2025_financial_statements.pdf` | Fail closed | Safe admission accepted the unchanged report. The workbook normalized source-backed rows, then the generic bank-style applicability gate rejected operating-company Tier-0 metrics. |
| `cimb_group_fy2025_financial_statements.pdf` | Fail closed | Safe admission accepted the unchanged report. The source uses bank-specific `Net income` rather than a safe generic revenue concept, so workbook normalization refused to invent a Tier-0 revenue mapping. |

These are interoperability outcomes, not issuer fixtures or expected-value fallbacks. The same mapper
and thresholds were used for all three files.

## Honest limitations

- This first slice supports embedded digital text. It does not silently OCR sparse pages. Low OCR
  confidence supplied by an adapter is preserved as an extraction warning and forces `uncertain`.
- A single native parser call cannot be forcibly interrupted in-process. The elapsed-time guard stops
  between calls; broader arbitrary-upload support should isolate parsing in a killable worker.
- Multi-page table reconstruction is intentionally not inferred. A metric is omitted when its PDF
  corroboration cannot be represented without collapsing distinct page anchors.
- Bank-specific performance metrics need a separately reviewed registry; bank income labels are not
  relabeled as operating-company revenue.
- Narrative recognition is deliberately narrow, and conflicting or wrong-period statements fail
  closed instead of selecting a convenient sentence.
- The mapper is not an audit, accounting opinion, forecasting system, or substitute for reviewed
  source work.
