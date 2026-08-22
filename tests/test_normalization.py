from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook

from proofline.contracts import MetricId
from proofline.metrics import calculate_metric
from proofline.normalization import normalize_financial_workbook
from proofline.parsing.workbook import StructuralXlsxAdapter


def _xlsx(rows: list[list[object]], title: str) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _calculate_all(result):
    observations = {fact.observation.id: fact.observation for fact in result.facts}
    return {
        item.plan.metric_id: calculate_metric(
            f"result:{item.plan.metric_id.value}", item.plan, observations
        )
        for item in result.metric_inputs
    }


def test_row_oriented_eur_statement_normalizes_base_units_and_tier0_inputs() -> None:
    content = _xlsx(
        [
            ["Issuer", "Alpine Robotics SE"],
            ["Entity scope", "Alpine Robotics SE consolidated"],
            ["Currency", "EUR"],
            ["Units", "thousands"],
            ["Restatement basis", "not restated"],
            [],
            ["Line item", 2024, 2025],
            ["Revenue", 1_000, 1_200],
            ["Operating profit", 150, 240],
            ["Total current assets", 400, 500],
            ["Total current liabilities", 200, 250],
            ["Net cash from operating activities", 260, 320],
            ["Capital expenditures", "(80)", "(100)"],
        ],
        "Consolidated statement",
    )
    cells = StructuralXlsxAdapter().extract_cells(content, "alpine-upload")

    result = normalize_financial_workbook(cells, "alpine-upload")

    assert result.issuer == "Alpine Robotics SE"
    assert result.entity_scope == "Alpine Robotics SE consolidated"
    assert result.currency == "EUR"
    assert len(result.facts) == 12
    assert {item.plan.metric_id for item in result.metric_inputs} == set(MetricId)
    current_revenue = next(
        fact
        for fact in result.facts
        if fact.observation.concept == "revenue" and fact.observation.period.end.year == 2025
    )
    assert current_revenue.observation.numeric_value == Decimal("1200000")
    assert current_revenue.observation.unit == "EUR base units"
    assert current_revenue.confidence == Decimal("0.90")
    assert len(current_revenue.provenance_span_ids) >= 8
    assert {warning.code for warning in current_revenue.warnings} == {"calendar_period_inferred"}

    calculated = _calculate_all(result)
    assert calculated[MetricId.REVENUE_GROWTH_YOY].result == Decimal("0.2")
    assert calculated[MetricId.OPERATING_MARGIN].result == Decimal("0.2")
    assert calculated[MetricId.CURRENT_RATIO].result == Decimal("2")
    assert calculated[MetricId.FCF_MARGIN].result == Decimal("0.1833333333333333333333333333")


def test_transposed_myr_statement_uses_same_generic_registry_without_issuer_rules() -> None:
    content = _xlsx(
        [
            ["Reporting entity", "Kestrel Logistics Berhad"],
            ["Scope", "Kestrel Logistics Berhad consolidated group"],
            ["Reporting currency", "MYR"],
            ["Scale", "millions"],
            ["Restatement status", "restated"],
            [],
            [
                "Period",
                "Net sales",
                "Operating income",
                "Current assets",
                "Current liabilities",
                "Operating cash flow",
                "Purchase of property, plant and equipment",
            ],
            ["2024-12-31", 800, 80, 300, 150, 120, -40],
            ["2025-12-31", 920, -115, 360, 180, 150, -50],
        ],
        "Metrics across columns",
    )
    cells = StructuralXlsxAdapter().extract_cells(content, "kestrel-upload")

    result = normalize_financial_workbook(cells, "kestrel-upload")

    assert result.issuer == "Kestrel Logistics Berhad"
    assert result.currency == "MYR"
    assert len(result.facts) == 12
    assert len(result.metric_inputs) == 4
    assert not any(fact.warnings for fact in result.facts)
    current_revenue = next(
        fact
        for fact in result.facts
        if fact.observation.concept == "revenue" and fact.observation.period.end.year == 2025
    )
    assert current_revenue.observation.numeric_value == Decimal("920000000")
    assert current_revenue.confidence == Decimal("1.00")

    calculated = _calculate_all(result)
    assert calculated[MetricId.REVENUE_GROWTH_YOY].result == Decimal("0.15")
    assert calculated[MetricId.OPERATING_MARGIN].result == Decimal("-0.125")
    assert calculated[MetricId.CURRENT_RATIO].result == Decimal("2")
    assert calculated[MetricId.FCF_MARGIN].result == Decimal("0.1086956521739130434782608696")


def test_conflicting_currency_metadata_fails_closed_before_fact_creation() -> None:
    content = _xlsx(
        [
            ["Company", "Delta Components Ltd"],
            ["Entity scope", "Delta Components Ltd consolidated"],
            ["Currency", "GBP"],
            ["Units", "thousands"],
            ["Restatement basis", "not restated"],
            ["Reporting currency", "USD"],
            ["Line item", 2024, 2025],
            ["Revenue", 100, 110],
        ],
        "Conflicting metadata",
    )
    cells = StructuralXlsxAdapter().extract_cells(content, "delta-upload")

    result = normalize_financial_workbook(cells, "delta-upload")

    assert result.facts == ()
    assert result.metric_inputs == ()
    assert "currency_ambiguous" in {warning.code for warning in result.warnings}


def test_duplicate_concept_period_values_are_omitted_and_do_not_feed_metrics() -> None:
    content = _xlsx(
        [
            ["Issuer", "Harbor Foods NV"],
            ["Entity scope", "Harbor Foods NV consolidated"],
            ["Currency", "EUR"],
            ["Units", "base units"],
            ["Restatement basis", "not restated"],
            ["Line item", 2024, 2025],
            ["Revenue", 100, 110],
            ["Net sales", 101, 111],
        ],
        "Duplicate rows",
    )
    cells = StructuralXlsxAdapter().extract_cells(content, "harbor-upload")

    result = normalize_financial_workbook(cells, "harbor-upload")

    assert not any(fact.observation.concept == "revenue" for fact in result.facts)
    assert not any(
        item.plan.metric_id == MetricId.REVENUE_GROWTH_YOY for item in result.metric_inputs
    )
    assert {warning.code for warning in result.warnings} >= {
        "fact_ambiguous",
        "no_financial_facts",
    }


def test_four_digit_financial_value_is_not_misread_as_a_period_header() -> None:
    content = _xlsx(
        [
            ["Issuer", "Alpine Robotics SE"],
            ["Entity scope", "Alpine Robotics SE consolidated"],
            ["Currency", "EUR"],
            ["Units", "millions"],
            ["Restatement basis", "not restated"],
            ["Line item", 2024, 2025],
            ["Revenue", 12_300, 13_400],
            ["Operating loss profit", 2_345, -678],
            ["Total current assets", 7_800, 8_900],
            ["Total current liabilities", 4_500, 5_600],
        ],
        "Consolidated statement",
    )
    cells = StructuralXlsxAdapter().extract_cells(content, "four-digit-value")

    result = normalize_financial_workbook(cells, "four-digit-value")

    operating = {
        fact.observation.period.end.year: fact.observation.numeric_value
        for fact in result.facts
        if fact.observation.concept == "operating_profit"
    }
    assert operating == {2024: Decimal("2345000000"), 2025: Decimal("-678000000")}
    assert {item.plan.metric_id for item in result.metric_inputs} >= {
        MetricId.OPERATING_MARGIN,
        MetricId.CURRENT_RATIO,
        MetricId.REVENUE_GROWTH_YOY,
    }
