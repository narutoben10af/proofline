import json
from decimal import Decimal
from pathlib import Path

import pytest

from proofline.contracts import AnalysisRequest, ExceptionalState
from proofline.service import analyze

FIXTURE = Path(__file__).parent / "fixtures" / "tier0_analysis.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_tier0_fixture_results_and_classifications() -> None:
    fixture = load_fixture()
    response = analyze(AnalysisRequest.model_validate(fixture["request"]))

    assert [result.result for result in response.metric_results] == [
        Decimal(value) for value in fixture["expected"]["results"]
    ]
    assert [finding.classification for finding in response.findings] == fixture["expected"][
        "classifications"
    ]
    assert response.findings[1].evidence_source_span_ids == (
        "span-xlsx-B3",
        "span-xlsx-B2",
    )


@pytest.mark.parametrize(
    ("mutation", "expected_state"),
    [
        (("revenue-prior", "numeric_value", "0"), ExceptionalState.ZERO_OR_NEGATIVE_DENOMINATOR),
        (("revenue-prior", "currency", "EUR"), ExceptionalState.INCOMPARABLE),
        (("revenue-prior", "restated", True), ExceptionalState.INCOMPARABLE),
        (("revenue-prior", "period.duration_weeks", 53), ExceptionalState.INCOMPARABLE),
    ],
)
def test_growth_fails_closed_for_edge_cases(
    mutation: tuple[str, str, object], expected_state
) -> None:
    fixture = load_fixture()["request"]
    observation_id, field, value = mutation
    observation = next(item for item in fixture["observations"] if item["id"] == observation_id)
    if "." in field:
        outer, inner = field.split(".")
        observation[outer][inner] = value
    else:
        observation[field] = value
    request = AnalysisRequest.model_validate({**fixture, "items": fixture["items"][:1]})

    response = analyze(request)

    assert response.metric_results[0].exceptional_state == expected_state
    assert response.findings[0].classification == "uncertain"


def test_fcf_requires_explicit_positive_outflow_sign() -> None:
    fixture = load_fixture()["request"]
    capex = next(item for item in fixture["observations"] if item["id"] == "capex")
    capex["sign_convention"] = "cash_outflow_negative"
    request = AnalysisRequest.model_validate({**fixture, "items": fixture["items"][3:4]})

    response = analyze(request)

    assert response.metric_results[0].exceptional_state == ExceptionalState.UNRESOLVED_SIGN
    assert response.findings[0].classification == "uncertain"


def test_unknown_or_duplicate_plan_roles_are_not_executed() -> None:
    fixture = load_fixture()["request"]
    item = fixture["items"][1]
    item["calculation_plan"]["inputs"][1]["role"] = "operating_profit"
    request = AnalysisRequest.model_validate({**fixture, "items": [item]})

    response = analyze(request)

    assert response.metric_results[0].exceptional_state == ExceptionalState.INVALID_PLAN


def test_observation_concepts_cannot_be_swapped_by_a_plan() -> None:
    fixture = load_fixture()["request"]
    item = fixture["items"][2]
    item["calculation_plan"]["inputs"][0]["observation_id"] = "current-liabilities"
    item["calculation_plan"]["inputs"][1]["observation_id"] = "current-assets"
    request = AnalysisRequest.model_validate({**fixture, "items": [item]})

    response = analyze(request)

    assert response.metric_results[0].exceptional_state == ExceptionalState.INVALID_PLAN
    assert response.findings[0].classification == "uncertain"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("currency", "EUR"),
        ("entity", "Example Subsidiary"),
        ("unit", "percent"),
        ("period.end", "2025-11-30"),
    ],
)
def test_claim_and_evidence_mismatch_is_uncertain(field: str, value: object) -> None:
    fixture = load_fixture()["request"]
    claim = fixture["claims"][0]
    if "." in field:
        outer, inner = field.split(".")
        claim[outer][inner] = value
    else:
        claim[field] = value
    request = AnalysisRequest.model_validate({**fixture, "items": fixture["items"][:1]})

    response = analyze(request)

    assert response.metric_results[0].result == Decimal("0.25")
    assert response.findings[0].classification == "uncertain"


def test_duplicate_observation_ids_are_rejected() -> None:
    fixture = load_fixture()["request"]
    fixture["observations"][1]["id"] = fixture["observations"][0]["id"]

    with pytest.raises(ValueError, match="duplicate observation IDs"):
        AnalysisRequest.model_validate(fixture)


def test_extraction_warning_forces_uncertain() -> None:
    fixture = load_fixture()["request"]
    fixture["claims"][0]["extraction_warnings"] = ["low-confidence numeric extraction"]
    request = AnalysisRequest.model_validate({**fixture, "items": fixture["items"][:1]})

    response = analyze(request)

    assert response.metric_results[0].result == Decimal("0.25")
    assert response.findings[0].classification == "uncertain"


@pytest.mark.parametrize("case", ["reversed", "non_adjacent"])
def test_growth_requires_correct_adjacent_chronology(case: str) -> None:
    fixture = load_fixture()["request"]
    current = next(item for item in fixture["observations"] if item["id"] == "revenue-current")
    prior = next(item for item in fixture["observations"] if item["id"] == "revenue-prior")
    if case == "reversed":
        current["period"], prior["period"] = prior["period"], current["period"]
    else:
        prior["period"] = {
            "start": "2023-01-01",
            "end": "2023-12-31",
            "duration_weeks": 52,
        }
    request = AnalysisRequest.model_validate({**fixture, "items": fixture["items"][:1]})

    response = analyze(request)

    assert response.metric_results[0].exceptional_state == ExceptionalState.INCOMPARABLE
    assert response.findings[0].classification == "uncertain"


def test_extreme_decimal_returns_typed_uncertain_result() -> None:
    fixture = load_fixture()["request"]
    current = next(item for item in fixture["observations"] if item["id"] == "revenue-current")
    current["numeric_value"] = "1e1000000"
    request = AnalysisRequest.model_validate({**fixture, "items": fixture["items"][:1]})

    response = analyze(request)

    assert response.metric_results[0].exceptional_state == ExceptionalState.NUMERIC_RANGE
    assert response.findings[0].classification == "uncertain"


def test_period_rejects_start_after_end() -> None:
    fixture = load_fixture()["request"]
    fixture["claims"][0]["period"]["start"] = "2026-01-01"

    with pytest.raises(ValueError, match="period start must be on or before end"):
        AnalysisRequest.model_validate(fixture)


def test_evidence_references_must_resolve() -> None:
    fixture = load_fixture()["request"]
    fixture["observations"][0]["source_span_id"] = "span-does-not-exist"

    with pytest.raises(ValueError, match="unknown observation source_span_id"):
        AnalysisRequest.model_validate(fixture)
