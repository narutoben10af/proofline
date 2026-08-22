from datetime import UTC, date, datetime
from decimal import Decimal

from proofline.contracts import (
    AnalysisHistorySummary,
    ClassificationCounts,
    EconomicContextPoint,
    ProcessingError,
    ReportSnapshot,
    SessionStatus,
)


def test_economic_context_is_sourced_and_not_causal() -> None:
    point = EconomicContextPoint(
        id="context-1",
        indicator="GDP growth",
        geography="Malaysia",
        period={"start": "2025-01-01", "end": "2025-12-31"},
        value=Decimal("0.052"),
        unit="ratio",
        source_url="https://example.test/indicator",
        source_date=date(2026, 8, 22),
    )

    assert point.model_dump(mode="json")["value"] == "0.052"
    assert point.causation_caveat == "Context only; no causal relationship is asserted."


def test_history_and_report_snapshot_are_non_forecast_review_boundaries() -> None:
    counts = ClassificationCounts(supported=2, uncertain=1, contradicted=1)
    history = AnalysisHistorySummary(
        analysis_id="analysis-1",
        session_id="session-1",
        created_at=datetime.now(UTC),
        classification_counts=counts,
        cached_output=False,
    )
    report = ReportSnapshot(
        snapshot_id="snapshot-1",
        analysis_id="analysis-1",
        title="Reviewed Proofline snapshot",
        reviewed_at=datetime.now(UTC),
        classification_counts=counts,
        finding_ids=("finding-1",),
        evidence_chain_sha256="c" * 64,
        economic_context_point_ids=("context-1",),
        limitations=("Prototype output requires human review.",),
    )

    assert history.session_local_only is True
    assert report.review_status == "reviewed"
    assert report.includes_forecast is False


def test_processing_error_and_cached_fallback_state_are_typed() -> None:
    status = SessionStatus(
        session_id="session-error",
        state="failed",
        input={
            "kind": "fixture",
            "fixture_id": "pcg-fy2025",
            "public_data_confirmed": True,
        },
        cached_output_status="available",
        fallback_disclosure="Verified cached output is available but was not selected.",
        errors=(
            ProcessingError(
                code="native_extraction_failed",
                stage="pdf",
                message="Native extraction did not meet the configured quality gate.",
                retryable=True,
            ),
        ),
    )

    assert status.errors[0].stage == "pdf"
    assert status.cached_output_status == "available"
