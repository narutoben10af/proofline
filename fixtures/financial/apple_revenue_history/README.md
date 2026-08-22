# Apple FY2014–FY2025 revenue history

This pack is a small, source-backed annual series for deterministic dashboard
and forecasting demos. It contains Apple Inc. consolidated total net sales for
12 fiscal years, copied from four official SEC-hosted Forms 10-K. Only
project-authored CSV/JSON derivatives are committed; no issuer PDF, workbook,
or filing copy is redistributed.

## Series contract

| Field | Definition |
| --- | --- |
| Series | `apple_total_net_sales_fy2014_fy2025` |
| Concept | Consolidated total net sales |
| Currency / unit | USD millions; nominal reported amounts; no FX or inflation adjustment |
| Period | Apple's 52- or 53-week fiscal year ending on the last Saturday of September |
| History | FY2014–FY2025, 12 consecutive annual observations, no gaps |
| Value status | `historical_actual`, `fact_source_reported`, `copied` |
| Forecast status | Separate JSON test contract; never mixed into the historical CSV |

`period_start` is derived from the reported period end and duration; the
revenue value itself is copied. Each row records the exact filing, printed
page, table, row, and year-column anchor. `sources.json` supplies the accession
number, filing-index retrieval route, fiscal-period policy anchor, and
restatement/reclassification disclosure anchor.

## Official source blocks

- FY2014–FY2016: Apple FY2016 Form 10-K, Item 8, **Consolidated
  Statements of Operations**, printed page 39, `Net sales` row.
- FY2017–FY2019: Apple FY2019 Form 10-K, Item 8, **Consolidated
  Statements of Operations**, printed page 29, `Total net sales` row.
- FY2020–FY2022: Apple FY2022 Form 10-K, Item 8, **Consolidated
  Statements of Operations**, printed page 29, `Total net sales` row.
- FY2023–FY2025: Apple FY2025 Form 10-K, Item 8, **Consolidated
  Statements of Operations**, printed page 29, `Total net sales` row.

The source URLs point directly to SEC EDGAR HTML. This makes retrieval lawful
and reproducible without publishing issuer binaries. Automated retrieval must
follow the SEC fair-access policy and identify its client; the verifier is
offline and does not download anything.

## Comparability and gaps

- There are no missing annual observations. The fixture deliberately does not
  fill or interpolate quarterly, segment, product, geographic, per-week, or
  currency-normalized data.
- FY2017 and FY2023 each span 53 weeks. All other included fiscal years span 52
  weeks. Growth is calculated from reported annual totals without normalizing
  the extra week, and both years are emitted as comparability exceptions.
- In FY2019 Apple adopted Topic 606 using the full retrospective method. Apple
  says it did not restate prior total net sales because the effect was not
  material; it did reclassify FY2018/FY2017 Products and Services sales. This
  pack uses only the consolidated total and preserves the disclosure rather
  than silently adjusting any value.
- Apple filings also note certain prior-period reclassifications. Each
  three-year block therefore uses the comparative values printed in its cited
  filing. Cross-block comparisons retain this caveat.
- The FY2025 filing's retrospective segment-disclosure adoption does not alter
  the consolidated statement total used here.

## Deterministic analysis outputs

`expected_analysis.json` defines every formula and expected result. From
FY2015–FY2025, eight changes are positive and three are negative; the reported
decline years are FY2016, FY2019, and FY2023. FY2021 is the largest absolute
year-over-year change in the finite series at 33.2593847330746954%. These are
descriptive classifications only. No cause, persistence, valuation, or advice
is inferred.

## Forecast-test contract

`forecast_test_fixture.json` defines `trailing_five_yoy_median_v1` without
changing shared application code:

1. Require at least eight compatible, consecutive annual historical periods.
2. Use the latest six actuals to calculate five year-over-year growth ratios.
3. Apply the median growth ratio to the latest actual for the point output.
4. Apply the minimum and maximum of those same five ratios for a deterministic
   scenario range.
5. Label the output `forecast` and retain FY2025 as the historical cutoff.

The scenario range is not a confidence or prediction interval. The method
ignores causal drivers, structural breaks, inflation, FX, and 52/53-week
normalization. A seven-period case proves that the explicit minimum-history
gate returns `MINIMUM_HISTORY_NOT_MET` even when a caller could otherwise
compute several growth rates.

## Verification

From the repository root:

```sh
python3 scripts/verify_apple_revenue_history.py
```

The standard-library verifier checks source allowlisting, exact source/value
mapping, annual continuity and duration, decimal calculations, trend and
exception outputs, historical/forecast separation, the forecast algorithm,
scenario ordering, and the insufficient-history case.
