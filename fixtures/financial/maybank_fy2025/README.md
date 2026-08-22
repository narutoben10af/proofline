# Maybank FY2025 bank fixture

This pack adds a Malaysian bank example without reusing industrial-company
ratio assumptions. It contains small, source-backed transcriptions from Malayan
Banking Berhad's audited FY2025 Group financial statements and deterministic
bank-appropriate outputs. Apple and PCG remain the existing non-bank examples.

No issuer PDF or workbook is committed. `sources.json` records Maybank's
issuer-designated investor-relations announcement, Bursa document-submission
reference, public attachment URL, and exact PDF/printed-page/table/row anchors.

## Scope, units, and periods

| Field | Policy |
| --- | --- |
| Issuer | Malayan Banking Berhad (MAYBANK) |
| Entity type | Bank |
| Scope | Maybank Group consolidated; never mixed with Bank standalone columns |
| Currency | Malaysian ringgit (MYR) |
| Statement unit | RM thousands (`RM'000`) |
| Summary unit | RM millions; transcriptions use primary-statement RM thousands where available |
| Income period | Calendar financial year ended 31 December 2025, with FY2024 comparative |
| Position/ratio instant | 31 December 2025, with 31 December 2024 comparative |

The fixture includes operating revenue, net operating income, profit before
taxation and zakat, total assets, net loans/advances/financing to customers,
deposits from customers, investment accounts of customers, reported CET1, and
reported issuer loan-to-deposit ratio (LDR). Every CSV row is copied and marked
`fact_source_reported`; all project metrics are separate JSON derivatives.

## Exact source anchors

- PDF page 30 / printed page 28, **Statements of Financial Position**, Group
  FY2025/FY2024 columns: total assets; loans, advances and financing to
  customers; deposits from customers; investment accounts of customers.
- PDF page 31 / printed page 29, **Income Statements**, Group FY2025/FY2024
  columns: operating revenue; net operating income; profit before taxation and
  zakat.
- PDF page 243 / printed page 241, **Note 59(b) Capital Adequacy**, Group
  FY2025/FY2024 columns: CET1 Capital Ratio.
- PDF page 5 / printed page 3, **Five-Year Group Financial Summary**, Group
  FY2025/FY2024 columns: reported LDR and its footnote definition.
- PDF page 14 / printed page 12, **Analysis of Financial Statements > Review of
  FY2025 Financial Position > Total Assets**, first paragraph: the checked
  narrative claim.

The primary statements present FY2024 comparatives without a restated label.
The five-year summary labels FY2022 restated for MFRS 17, outside this fixture's
comparison. Business-segment FY2024 figures elsewhere were restated for a 2025
structural change; this fixture does not use segment data.

## Bank-appropriate metrics

All arithmetic uses decimal inputs. Ratios are stored as ratios (`0.01` means
1%) unless the output explicitly says `percentage_point`.

| Metric | Formula | Interpretation boundary |
| --- | --- | --- |
| Operating revenue growth | `operating revenue FY2025 / FY2024 - 1` | Gross reported operating revenue, not industrial sales. |
| Net operating income growth | `net operating income FY2025 / FY2024 - 1` | Closest pack-level revenue equivalent after interest/insurance structure. |
| PBT growth | `PBT FY2025 / FY2024 - 1` | Uses profit before taxation and zakat. |
| Pre-tax return on average assets | `PBT / average(FY2025 assets, FY2024 assets)` | Project-defined annual flow over average balance; not issuer-reported ROA. |
| Net loans-to-customer-funding proxy | `net customer loans / (deposits + investment accounts)` | Project-defined proxy; not Maybank's reported LDR. |
| Customer funding to assets | `(deposits + investment accounts) / total assets` | Project-defined funding mix ratio. |
| CET1 ratio | Reported percent divided by 100 | Direct regulatory capital ratio, not industrial equity ratio. |

Current ratio, operating margin, gross margin, inventory days, and the project's
industrial FCF margin are deliberately not calculated. Bank balance sheets do
not classify liquidity and working capital like industrial issuers, and bank
cash flows, customer deposits, regulatory capital, and financial assets are
core operations. Applying those industrial ratios would create false
comparability.

## Genuine exception and definition trap

FY2025 operating revenue fell 3.732882%, while net operating income rose
2.728869%. The pack labels this an opposite-direction exception without making
a causal claim.

Maybank reports FY2025 LDR of 93.8% and defines it using **gross** loans,
advances and financing over deposits plus investment accounts. The project
proxy uses the **net** customer-loans statement row and produces 92.611173%.
The 1.188827 percentage-point difference is expected evidence of a definition
mismatch, not an error to smooth away.

## Narrative claim

The report says Group total assets were RM1,053.6 billion and decreased by
RM21.7 billion or 2.0% YoY. Exact statement values are RM1,053.583593 billion
and RM1,075.321956 billion. The exact decrease of RM21.738363 billion and
2.021568% both round to the claim's precision, so `narrative_claims.json`
classifies the claim as supported. No cause is inferred.

## Multi-issuer genericity

- `entity_type`, `entity_scope`, `currency`, `unit`, `period_type`, source IDs,
  and fact IDs are explicit; another bank can use the same contract without
  pretending its labels or definitions match Maybank's.
- Metric applicability is entity-type gated. Industrial Apple/PCG metrics stay
  separate from bank capital, funding, and asset-quality metrics.
- Reported ratios preserve issuer definitions. A cross-issuer dashboard must
  compare only ratios with aligned numerator, denominator, scope, and
  regulatory basis; otherwise it must display a definition mismatch.
- The verifier includes acceptance, industrial-metric rejection, LDR-definition
  mismatch, and Group/Bank scope-mismatch test cases.

## Verification

From the repository root:

```sh
python3 scripts/verify_maybank_bank_fixtures.py
pytest tests/test_maybank_bank_fixtures.py
```

The verifier is offline and standard-library-only. It validates source hosts
and anchors, exact facts, period/scope/unit compatibility, decimal metric
outputs, the direction-split hero case, the LDR definition trap, the rounded
narrative claim, and applicability test cases.
