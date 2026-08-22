#!/usr/bin/env python3
"""Verify the source-backed Maybank FY2025 bank fixture pack."""

from __future__ import annotations

import csv
import json
import sys
from decimal import ROUND_HALF_EVEN, Decimal, getcontext
from pathlib import Path

getcontext().prec = 40

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "financial" / "maybank_fy2025"
RATIO_QUANTUM = Decimal("0.000000000000000001")

EXPECTED_FACTS = {
    "maybank_operating_revenue_2025": Decimal("66369232"),
    "maybank_operating_revenue_2024": Decimal("68942785"),
    "maybank_net_operating_income_2025": Decimal("30379501"),
    "maybank_net_operating_income_2024": Decimal("29572506"),
    "maybank_pbt_2025": Decimal("14333794"),
    "maybank_pbt_2024": Decimal("13701565"),
    "maybank_total_assets_2025": Decimal("1053583593"),
    "maybank_total_assets_2024": Decimal("1075321956"),
    "maybank_customer_loans_2025": Decimal("676981380"),
    "maybank_customer_loans_2024": Decimal("662740860"),
    "maybank_customer_deposits_2025": Decimal("698210227"),
    "maybank_customer_deposits_2024": Decimal("712915459"),
    "maybank_investment_accounts_2025": Decimal("32782974"),
    "maybank_investment_accounts_2024": Decimal("28981847"),
    "maybank_cet1_ratio_2025": Decimal("16.041"),
    "maybank_cet1_ratio_2024": Decimal("15.765"),
    "maybank_issuer_ldr_2025": Decimal("93.8"),
    "maybank_issuer_ldr_2024": Decimal("90.7"),
}


def load_json(name: str):
    with (FIXTURE_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_facts() -> dict[str, dict[str, str]]:
    with (FIXTURE_DIR / "normalized_facts.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["fact_id"]: row for row in rows}


def value(facts: dict[str, dict[str, str]], fact_id: str) -> Decimal:
    return Decimal(facts[fact_id]["value"])


def rounded_ratio(number: Decimal) -> Decimal:
    return number.quantize(RATIO_QUANTUM, rounding=ROUND_HALF_EVEN)


def calculate(metric_id: str, inputs: list[Decimal]) -> Decimal:
    if metric_id in {
        "operating_revenue_growth_yoy",
        "net_operating_income_growth_yoy",
        "profit_before_tax_growth_yoy",
    }:
        assert inputs[1] > 0, f"{metric_id}: prior-period denominator must be positive"
        return inputs[0] / inputs[1] - Decimal(1)
    if metric_id == "pre_tax_return_on_average_assets":
        average_assets = (inputs[1] + inputs[2]) / 2
        assert average_assets > 0, "average assets must be positive"
        return inputs[0] / average_assets
    if metric_id == "net_loans_to_customer_funding_proxy":
        funding = inputs[1] + inputs[2]
        assert funding > 0, "customer funding must be positive"
        return inputs[0] / funding
    if metric_id == "customer_funding_to_assets":
        assert inputs[2] > 0, "total assets must be positive"
        return (inputs[0] + inputs[1]) / inputs[2]
    if metric_id == "cet1_capital_ratio_reported":
        return inputs[0] / 100
    if metric_id == "cet1_change_percentage_points":
        return inputs[0] - inputs[1]
    raise AssertionError(f"unknown bank metric: {metric_id}")


def validate_sources(facts: dict[str, dict[str, str]], sources: dict) -> None:
    assert len(sources["sources"]) == 1
    source = sources["sources"][0]
    assert source["source_id"] == "maybank_fy2025_financial_statements"
    assert source["official_announcement_url"].startswith("https://maybank.listedcompany.com/")
    assert source["source_url"].startswith("https://maybank.listedcompany.com/newsroom/")
    assert source["bursa_reference_number"] == "DCS-01042026-00004"
    assert "must not be committed" in source["retrieval"]
    assert len(source["anchors"]) == 5

    for fact_id, row in facts.items():
        assert row["source_id"] == source["source_id"], f"{fact_id}: unknown source"
        assert row["source_url"] == source["source_url"]
        for field in (
            "pdf_page",
            "printed_page",
            "table_anchor",
            "row_anchor",
            "column_anchor",
        ):
            assert row[field], f"{fact_id}: missing {field}"


def validate_facts(facts: dict[str, dict[str, str]]) -> None:
    assert len(facts) == len(EXPECTED_FACTS), "missing or duplicate fact rows"
    assert set(facts) == set(EXPECTED_FACTS)
    for fact_id, expected in EXPECTED_FACTS.items():
        row = facts[fact_id]
        assert Decimal(row["value"]) == expected, f"{fact_id}: unexpected value"
        assert row["issuer"] == "Malayan Banking Berhad"
        assert row["entity_type"] == "bank"
        assert row["entity_scope"] == "group_consolidated"
        assert row["currency"] == "MYR"
        assert row["evidence_label"] == "fact_source_reported"
        assert row["copy_or_derived"] == "copied"
        assert row["retrieved_at"] == "2026-08-22"
        if row["period_type"] == "annual_duration":
            assert row["period_start"] and row["period_end"] and not row["instant"]
        else:
            assert row["instant"] and not row["period_start"] and not row["period_end"]


def compatible(rows: list[dict[str, str]], metric_id: str) -> None:
    assert len({row["issuer"] for row in rows}) == 1
    assert len({row["entity_type"] for row in rows}) == 1
    assert len({row["entity_scope"] for row in rows}) == 1
    assert len({row["currency"] for row in rows}) == 1
    if metric_id not in {"cet1_capital_ratio_reported", "cet1_change_percentage_points"}:
        assert len({row["unit"] for row in rows}) == 1


def validate_metrics(facts: dict[str, dict[str, str]], expected: dict) -> None:
    outputs = {output["metric_id"]: output for output in expected["outputs"]}
    assert len(outputs) == 8
    for metric_id, output in outputs.items():
        rows = [facts[fact_id] for fact_id in output["input_fact_ids"]]
        compatible(rows, metric_id)
        actual = calculate(metric_id, [Decimal(row["value"]) for row in rows])
        target = Decimal(output["expected_value"])
        if output["unit"] == "percentage_point":
            assert actual == target, f"{metric_id}: {actual} != {target}"
        else:
            assert rounded_ratio(actual) == target, f"{metric_id}: {actual} != {target}"

    hero = expected["hero_case"]
    operating_growth = Decimal(outputs["operating_revenue_growth_yoy"]["expected_value"])
    net_growth = Decimal(outputs["net_operating_income_growth_yoy"]["expected_value"])
    assert operating_growth < 0 < net_growth
    assert hero["classification"] == "opposite_direction"
    assert Decimal(hero["operating_revenue_growth"]) == operating_growth
    assert Decimal(hero["net_operating_income_growth"]) == net_growth
    assert "not a causal explanation" in hero["interpretation"]

    trap = expected["definition_trap"]
    proxy = calculate(
        "net_loans_to_customer_funding_proxy",
        [
            value(facts, "maybank_customer_loans_2025"),
            value(facts, "maybank_customer_deposits_2025"),
            value(facts, "maybank_investment_accounts_2025"),
        ],
    )
    reported = value(facts, "maybank_issuer_ldr_2025") / 100
    difference_pp = (reported - proxy) * 100
    assert Decimal(trap["issuer_reported_ldr_ratio"]) == reported
    assert Decimal(trap["project_net_loans_proxy_ratio"]) == rounded_ratio(proxy)
    assert Decimal(trap["difference_percentage_points"]) == rounded_ratio(difference_pp)
    assert proxy != reported


def validate_claim(facts: dict[str, dict[str, str]], claims: dict) -> None:
    assert len(claims["claims"]) == 1
    claim = claims["claims"][0]
    assets_2025 = value(facts, "maybank_total_assets_2025") / Decimal(1_000_000)
    assets_2024 = value(facts, "maybank_total_assets_2024") / Decimal(1_000_000)
    decrease = assets_2024 - assets_2025
    decrease_percent = (assets_2024 - assets_2025) / assets_2024 * 100
    one_decimal = Decimal("0.1")
    normalized = claim["normalized_claims"]
    assert assets_2025.quantize(one_decimal, rounding=ROUND_HALF_EVEN) == Decimal(
        normalized["total_assets_2025_rm_billion"]
    )
    assert decrease.quantize(one_decimal, rounding=ROUND_HALF_EVEN) == Decimal(
        normalized["absolute_decrease_rm_billion"]
    )
    assert decrease_percent.quantize(one_decimal, rounding=ROUND_HALF_EVEN) == Decimal(
        normalized["decrease_percent"]
    )
    assert claim["classification"] == "supported"
    assert claim["pdf_page"] == 14 and claim["printed_page"] == 12
    assert claim["causal_scope"] == "No causal clause is evaluated or inferred."


def validate_test_cases(test_cases: dict) -> None:
    cases = {case["case_id"]: case for case in test_cases["cases"]}
    assert len(cases) == 5
    accepted = cases["bank_metrics_accept_group_facts"]
    assert accepted["entity_type"] == "bank" and accepted["expected_status"] == "accepted"

    for case_id in (
        "current_ratio_rejected_for_bank_fixture",
        "fcf_margin_rejected_for_bank_fixture",
    ):
        case = cases[case_id]
        assert case["expected_status"] == "not_applicable"
        assert case["expected_error_code"] == "INDUSTRIAL_METRIC_NOT_APPLICABLE_TO_BANK"

    mismatch = cases["issuer_ldr_definition_mismatch_detected"]
    assert mismatch["expected_status"] == "definition_mismatch"
    assert mismatch["expected_error_code"] == "GROSS_VS_NET_LOANS_DEFINITION_MISMATCH"

    scope = cases["group_and_bank_scope_mixing_rejected"]
    assert len(set(scope["input_scopes"])) > 1
    assert scope["expected_error_code"] == "ENTITY_SCOPE_MISMATCH"


def main() -> int:
    facts = load_facts()
    sources = load_json("sources.json")
    expected = load_json("expected_bank_metrics.json")
    claims = load_json("narrative_claims.json")
    test_cases = load_json("metric_tests.json")

    validate_sources(facts, sources)
    validate_facts(facts)
    validate_metrics(facts, expected)
    validate_claim(facts, claims)
    validate_test_cases(test_cases)

    print(
        f"OK: {len(facts)} reported bank facts, {len(expected['outputs'])} metrics, "
        f"{len(claims['claims'])} checked claim, {len(test_cases['cases'])} contract tests"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
