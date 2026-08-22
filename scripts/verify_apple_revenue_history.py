#!/usr/bin/env python3
"""Verify the Apple annual revenue history and deterministic forecast contract."""

from __future__ import annotations

import csv
import json
import sys
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, getcontext
from pathlib import Path

getcontext().prec = 40

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "financial" / "apple_revenue_history"
RATIO_QUANTUM = Decimal("0.000000000000000001")
DISPLAY_QUANTUM = Decimal("0.001")

EXPECTED_VALUES = {
    "FY2014": Decimal("182795"),
    "FY2015": Decimal("233715"),
    "FY2016": Decimal("215639"),
    "FY2017": Decimal("229234"),
    "FY2018": Decimal("265595"),
    "FY2019": Decimal("260174"),
    "FY2020": Decimal("274515"),
    "FY2021": Decimal("365817"),
    "FY2022": Decimal("394328"),
    "FY2023": Decimal("383285"),
    "FY2024": Decimal("391035"),
    "FY2025": Decimal("416161"),
}


def load_json(name: str):
    with (FIXTURE_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_rows() -> list[dict[str, str]]:
    with (FIXTURE_DIR / "historical_series.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def fiscal_year_number(label: str) -> int:
    assert label.startswith("FY") and len(label) == 6, f"invalid fiscal year: {label}"
    return int(label[2:])


def ratio(current: Decimal, previous: Decimal) -> Decimal:
    assert previous > 0, "year-over-year denominator must be positive"
    return current / previous - Decimal(1)


def rounded_ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIO_QUANTUM, rounding=ROUND_HALF_EVEN)


def rounded_display(value: Decimal) -> Decimal:
    return value.quantize(DISPLAY_QUANTUM, rounding=ROUND_HALF_EVEN)


def validate_sources(rows: list[dict[str, str]], sources: dict) -> None:
    source_by_id = {source["source_id"]: source for source in sources["sources"]}
    assert len(source_by_id) == 4, "expected four source filing blocks"
    assert sources["retrieval_policy"]["redistribution"].startswith(
        "Only project-authored transcriptions"
    )

    for source in source_by_id.values():
        assert source["document_type"] == "Form 10-K"
        assert source["cik"] == "0000320193"
        for url_field in ("source_url", "filing_index_url"):
            assert source[url_field].startswith(
                "https://www.sec.gov/Archives/edgar/data/320193/"
            ), f"non-official source URL: {source[url_field]}"
        for anchor in ("value_anchor", "period_policy_anchor", "restatement_anchor"):
            assert source[anchor], f"{source['source_id']}: missing {anchor}"

    for row in rows:
        source = source_by_id[row["source_id"]]
        assert row["fiscal_year"] in source["covered_fiscal_years"]
        assert row["source_url"] == source["source_url"]
        assert "Consolidated Statements of Operations" in row["source_anchor"]
        assert "page" in row["source_anchor"] and "column" in row["source_anchor"]


def validate_history(rows: list[dict[str, str]]) -> list[Decimal]:
    assert len(rows) == 12, f"expected 12 historical rows, got {len(rows)}"
    years = [fiscal_year_number(row["fiscal_year"]) for row in rows]
    assert years == list(range(2014, 2026)), "history must be ordered and consecutive"

    constant_fields = (
        "series_id",
        "issuer",
        "cik",
        "currency",
        "unit",
        "entity_scope",
        "concept",
        "record_kind",
        "evidence_label",
        "copy_or_derived",
        "period_start_basis",
        "gap_status",
    )
    for field in constant_fields:
        assert len({row[field] for row in rows}) == 1, f"inconsistent {field}"

    first = rows[0]
    assert first["record_kind"] == "historical_actual"
    assert first["evidence_label"] == "fact_source_reported"
    assert first["copy_or_derived"] == "copied"
    assert first["currency"] == "USD" and first["unit"] == "million"
    assert first["entity_scope"] == "consolidated"
    assert first["period_start_basis"] == "derived_from_period_end_and_duration_weeks"
    assert first["gap_status"] == "none"

    values: list[Decimal] = []
    for row in rows:
        fiscal_year = row["fiscal_year"]
        value = Decimal(row["value"])
        assert value == EXPECTED_VALUES[fiscal_year], f"unexpected value for {fiscal_year}"
        values.append(value)

        start = date.fromisoformat(row["period_start"])
        end = date.fromisoformat(row["period_end"])
        weeks = int(row["duration_weeks"])
        assert start == end - timedelta(days=weeks * 7 - 1), (
            f"{fiscal_year}: period start does not match end and duration"
        )
        assert end.weekday() == 5, f"{fiscal_year}: period must end on Saturday"
        assert weeks == (53 if fiscal_year in {"FY2017", "FY2023"} else 52)
        assert row["comparability_note"]

    return values


def validate_analysis(rows: list[dict[str, str]], analysis: dict) -> list[Decimal]:
    assert analysis["series_id"] == rows[0]["series_id"]
    values = [Decimal(row["value"]) for row in rows]
    actual_ratios = [
        ratio(current, previous) for previous, current in zip(values, values[1:], strict=False)
    ]
    expected_rows = analysis["year_over_year"]
    assert len(expected_rows) == len(actual_ratios)

    for row, actual in zip(expected_rows, actual_ratios, strict=False):
        assert row["record_kind"] == "derived_historical"
        assert Decimal(row["expected_ratio"]) == rounded_ratio(actual)

    trend = analysis["trend"]
    cumulative = values[-1] / values[0] - Decimal(1)
    assert Decimal(trend["expected_cumulative_change_ratio"]) == rounded_ratio(cumulative)
    assert trend["positive_year_over_year_periods"] == sum(value > 0 for value in actual_ratios)
    assert trend["negative_year_over_year_periods"] == sum(value < 0 for value in actual_ratios)
    assert trend["zero_year_over_year_periods"] == sum(value == 0 for value in actual_ratios)

    decline_years = [
        row["fiscal_year"] for row, value in zip(rows[1:], actual_ratios, strict=False) if value < 0
    ]
    patterns = {pattern["pattern_id"]: pattern for pattern in analysis["patterns"]}
    assert patterns["reported_decline_years"]["fiscal_years"] == decline_years
    assert patterns["nonstandard_duration_years"]["fiscal_years"] == ["FY2017", "FY2023"]

    largest_index = max(range(len(actual_ratios)), key=lambda index: abs(actual_ratios[index]))
    exception = analysis["exception"]
    assert exception["fiscal_year"] == rows[largest_index + 1]["fiscal_year"]
    assert Decimal(exception["expected_ratio"]) == rounded_ratio(actual_ratios[largest_index])
    assert "No cause is inferred" in exception["interpretation"]
    assert analysis["comparability"]["gap_status"] == "no_missing_annual_periods"
    return actual_ratios


def validate_forecast(rows: list[dict[str, str]], forecast: dict) -> None:
    method = forecast["method"]
    assert forecast["contract_only"] is True
    assert method["method_id"] == "trailing_five_yoy_median_v1"
    assert method["minimum_history_periods"] == 8
    assert "not a confidence interval" in method["uncertainty"]
    assert "not advice" in method["limitations"]

    cases = {case["case_id"]: case for case in forecast["cases"]}
    passing = cases["apple_12_period_history_passes_gate"]
    assert len(passing["input_fiscal_years"]) >= method["minimum_history_periods"]
    assert passing["input_fiscal_years"] == [row["fiscal_year"] for row in rows]
    assert passing["expected_status"] == "forecast_available"

    training_rows = rows[-method["training_actual_periods"] :]
    training_values = [Decimal(row["value"]) for row in training_rows]
    growth = [
        ratio(current, previous)
        for previous, current in zip(training_values, training_values[1:], strict=False)
    ]
    assert len(growth) == method["growth_observations"]
    assert [Decimal(value) for value in passing["expected_growth_ratios"]] == [
        rounded_ratio(value) for value in growth
    ]

    ordered_growth = sorted(growth)
    median_growth = ordered_growth[len(ordered_growth) // 2]
    assert Decimal(passing["expected_median_growth_ratio"]) == rounded_ratio(median_growth)
    assert Decimal(passing["expected_min_growth_ratio"]) == rounded_ratio(ordered_growth[0])
    assert Decimal(passing["expected_max_growth_ratio"]) == rounded_ratio(ordered_growth[-1])

    latest = training_values[-1]
    output = passing["output"]
    assert output["record_kind"] == "forecast"
    assert output["historical_cutoff_fiscal_year"] == rows[-1]["fiscal_year"]
    assert all(row["record_kind"] == "historical_actual" for row in rows)
    assert Decimal(output["point_value"]) == rounded_display(latest * (1 + median_growth))
    assert Decimal(output["scenario_low_value"]) == rounded_display(
        latest * (1 + ordered_growth[0])
    )
    assert Decimal(output["scenario_high_value"]) == rounded_display(
        latest * (1 + ordered_growth[-1])
    )
    assert (
        Decimal(output["scenario_low_value"])
        <= Decimal(output["point_value"])
        <= Decimal(output["scenario_high_value"])
    )

    failing = cases["seven_period_history_fails_gate"]
    assert len(failing["input_fiscal_years"]) < method["minimum_history_periods"]
    assert failing["expected_status"] == "insufficient_history"
    assert failing["expected_error_code"] == "MINIMUM_HISTORY_NOT_MET"
    assert failing["expected_observed_periods"] == len(failing["input_fiscal_years"])
    assert failing["expected_required_periods"] == method["minimum_history_periods"]
    assert failing["output"] is None


def main() -> int:
    rows = load_rows()
    sources = load_json("sources.json")
    analysis = load_json("expected_analysis.json")
    forecast = load_json("forecast_test_fixture.json")

    validate_sources(rows, sources)
    validate_history(rows)
    ratios = validate_analysis(rows, analysis)
    validate_forecast(rows, forecast)

    print(
        f"OK: {len(rows)} annual actuals, {len(ratios)} historical changes, "
        f"{len(sources['sources'])} official filings, {len(forecast['cases'])} forecast cases"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
