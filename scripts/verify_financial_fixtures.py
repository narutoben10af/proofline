#!/usr/bin/env python3
"""Deterministically verify the small FY2025 financial fixture pack."""

from __future__ import annotations

import csv
import json
import sys
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 40
ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "financial"
TOLERANCE = Decimal("1e-18")


def load_json(name: str):
    with (FIXTURE_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_facts():
    with (FIXTURE_DIR / "normalized_facts.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["fact_id"]: row for row in rows}


def value(facts, fact_id: str) -> Decimal:
    return Decimal(facts[fact_id]["value"])


def calculate(metric_id: str, inputs: list[Decimal]) -> Decimal:
    if metric_id == "revenue_growth_yoy":
        assert inputs[1] > 0, "prior revenue denominator must be positive"
        return inputs[0] / inputs[1] - Decimal(1)
    if metric_id in {"operating_margin", "gross_margin"}:
        assert inputs[1] > 0, "revenue denominator must be positive"
        return inputs[0] / inputs[1]
    if metric_id == "current_ratio":
        assert inputs[1] > 0, "current liabilities denominator must be positive"
        return inputs[0] / inputs[1]
    if metric_id == "fcf_margin":
        assert inputs[2] > 0, "revenue denominator must be positive"
        assert inputs[1] >= 0, "capex must be a positive cash-outflow magnitude"
        return (inputs[0] - inputs[1]) / inputs[2]
    raise AssertionError(f"unknown metric_id: {metric_id}")


def compatible(rows, metric_id: str) -> None:
    assert len({row["issuer"] for row in rows}) == 1
    assert len({row["entity_scope"] for row in rows}) == 1
    assert len({row["currency"] for row in rows}) == 1
    assert len({row["unit"] for row in rows}) == 1
    if metric_id == "current_ratio":
        assert len({row["instant"] for row in rows}) == 1
    elif metric_id != "revenue_growth_yoy":
        assert len({(row["period_start"], row["period_end"]) for row in rows}) == 1


def main() -> int:
    facts = load_facts()
    expected = load_json("expected_metrics.json")
    heroes = load_json("hero_cases.json")
    sources = load_json("sources.json")
    source_ids = {source["source_id"] for source in sources["sources"]}

    assert len(facts) == 17, f"expected 17 fact rows, got {len(facts)}"
    assert len(facts) == len(set(facts)), "duplicate fact_id"
    for fact_id, row in facts.items():
        for required in (
            "issuer",
            "concept",
            "entity_scope",
            "currency",
            "unit",
            "value",
            "source_id",
            "source_url",
            "pdf_page",
            "printed_page",
            "table_anchor",
            "row_anchor",
            "fixture_anchor",
            "retrieved_at",
        ):
            assert row[required], f"{fact_id}: missing {required}"
        assert row["source_id"] in source_ids, f"{fact_id}: unknown source_id"
        assert row["evidence_label"] == "fact_source_reported"
        assert row["copy_or_derived"] == "copied"
        assert row["fixture_anchor"].endswith(f"#{fact_id}")
        Decimal(row["value"])

    output_keys = set()
    for output in expected["outputs"]:
        key = (output["issuer"], output["period"], output["metric_id"])
        assert key not in output_keys, f"duplicate expected output: {key}"
        output_keys.add(key)
        rows = [facts[fact_id] for fact_id in output["input_fact_ids"]]
        compatible(rows, output["metric_id"])
        actual = calculate(
            output["metric_id"],
            [Decimal(row["value"]) for row in rows],
        )
        target = Decimal(output["expected_value"])
        assert abs(actual - target) <= TOLERANCE, (
            f"{key}: {actual} != {target} (tolerance {TOLERANCE})"
        )
        assert output["evidence_label"] == "derived_calculation"
        if output["metric_id"] == "fcf_margin":
            assert output.get("non_gaap") is True

    hero = heroes["cases"][0]
    assert hero["kind"] == "genuine_exception"
    margin_2025 = value(facts, "pcg_operating_loss_2025") / value(facts, "pcg_revenue_2025")
    margin_2024 = value(facts, "pcg_operating_profit_2024") / value(facts, "pcg_revenue_2024")
    assert (
        abs((margin_2025 - margin_2024) - Decimal(hero["calculations"]["operating_margin_change"]))
        <= TOLERANCE
    )

    rounding = heroes["cases"][1]
    difference = abs(
        Decimal(rounding["normalized_claim_value_rm_million"]) - value(facts, "pcg_revenue_2025")
    )
    assert difference == Decimal(rounding["absolute_difference_rm_million"])
    assert difference <= Decimal(50)
    assert rounding["classification"] == "supported"

    print(
        f"OK: {len(facts)} reported facts, {len(expected['outputs'])} derived "
        f"metrics, {len(heroes['cases'])} hero cases, {len(source_ids)} sources"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
