from __future__ import annotations

import hashlib
import json
import socket
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pypdf import PdfReader

from proofline.api import app
from proofline.contracts import AnalysisRequest, AnalysisResponse, ReportSnapshot
from proofline.economic_context import get_company_lens
from proofline.report_contracts import (
    DATA_HANDLING_DISCLOSURE,
    LIVE_SOURCE_DISCLOSURE,
    NO_CAUSATION,
    VERIFIED_CACHED_SOURCE_DISCLOSURE,
    FinancialTrendSeries,
    ReportRenderBundle,
    ResolvedEconomicContextPoint,
    canonical_json_bytes,
    canonical_sha256,
)
from proofline.reports import render_evidence_json, render_pdf
from proofline.service import analyze

FIXTURE = Path(__file__).parent / "fixtures" / "tier0_analysis.json"


def _analysis() -> AnalysisResponse:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))["request"]
    return analyze(AnalysisRequest.model_validate(raw))


def _context() -> ResolvedEconomicContextPoint:
    return ResolvedEconomicContextPoint(
        id="context-us-gdp",
        company="Example Group",
        indicator="U.S. real GDP annual growth",
        geography="United States",
        period={"start": "2025-01-01", "end": "2025-12-31"},
        value="2.1",
        display_value="2.1%",
        unit="percent year over year",
        official_source_url="https://www.bea.gov/sites/default/files/2026-04/gdp4q25-3rd.pdf",
        published_on="2026-04-09",
        retrieved_on="2026-08-22",
        relevance="Broad activity context for the reviewed period.",
        comparability_warning=(
            "National output does not match the reporting entity or fiscal period."
        ),
    )


def _trend() -> FinancialTrendSeries:
    return FinancialTrendSeries(
        id="example-revenue-trend",
        company="Example Group",
        indicator="Revenue",
        unit="USD millions",
        currency="USD",
        points=(
            {
                "period": {"start": "2023-01-01", "end": "2023-12-31", "duration_weeks": 52},
                "value": "80",
                "reporting_basis": "Consolidated annual revenue",
                "evidence_source_span_id": "span-xlsx-C2",
            },
            {
                "period": {"start": "2024-01-01", "end": "2024-12-31", "duration_weeks": 52},
                "value": "90",
                "reporting_basis": "Consolidated annual revenue",
                "evidence_source_span_id": "span-xlsx-C2",
            },
            {
                "period": {"start": "2025-01-01", "end": "2025-12-31", "duration_weeks": 52},
                "value": "100",
                "reporting_basis": "Consolidated annual revenue",
                "evidence_source_span_id": "span-xlsx-B2",
            },
        ),
    )


def _bundle(
    *,
    source_mode: str = "calculated_live",
    source_disclosure: str = LIVE_SOURCE_DISCLOSURE,
    analysis: AnalysisResponse | None = None,
    trend: FinancialTrendSeries | None = None,
) -> ReportRenderBundle:
    response = analysis or _analysis()
    classifications = [finding.classification.value for finding in response.findings]
    point = _context()
    snapshot = ReportSnapshot(
        snapshot_id="reviewed-example-fy2025",
        analysis_id=f"sha256:{canonical_sha256(response)}",
        title="Example Group reviewed evidence report",
        reviewed_at=datetime(2026, 8, 22, tzinfo=UTC),
        classification_counts={
            "supported": classifications.count("supported"),
            "uncertain": classifications.count("uncertain"),
            "contradicted": classifications.count("contradicted"),
        },
        finding_ids=tuple(finding.id for finding in response.findings),
        evidence_chain_sha256=canonical_sha256(response),
        economic_context_point_ids=(point.id,),
        limitations=("Prototype output requires human review.",),
    )
    return ReportRenderBundle(
        company_id="example-group-fy2025",
        company="Example Group",
        analysis=response,
        snapshot=snapshot,
        trend=trend if trend is not None else _trend(),
        economic_context=(point,),
        source_mode=source_mode,
        source_disclosure=source_disclosure,
    )


def _text(pdf: bytes) -> str:
    reader = PdfReader(__import__("io").BytesIO(pdf))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _mutated_bundle(**updates) -> dict:
    raw = _bundle().model_dump(mode="json")
    for key, value in updates.items():
        raw[key] = value
    return raw


def _rehash_analysis(raw: dict) -> None:
    raw["snapshot"]["evidence_chain_sha256"] = canonical_sha256(
        AnalysisResponse.model_validate(raw["analysis"])
    )


def _post_report(raw: dict):
    return TestClient(app).post("/api/v1/reports/pdf", json=raw)


def test_pdf_is_byte_deterministic_and_sections_are_ordered() -> None:
    bundle = _bundle()
    first = render_pdf(bundle)
    second = render_pdf(bundle)
    text = _text(first)

    assert first == second
    headings = (
        "1. Summary and hero finding",
        "2. Historical trend and value table",
        "3. Ordered findings",
        "4. Economic context - no causation",
        "5. Evidence and provenance appendix",
        "6. Methodology and limitations",
        "7. Data handling and export disclosure",
    )
    offsets = [text.index(heading) for heading in headings]
    assert offsets == sorted(offsets)
    assert "PROTOTYPE - HUMAN REVIEW REQUIRED" in text
    assert NO_CAUSATION in text
    assert DATA_HANDLING_DISCLOSURE in " ".join(text.split())


def test_cached_banner_and_disclosure_are_explicit() -> None:
    disclosure = VERIFIED_CACHED_SOURCE_DISCLOSURE
    text = _text(render_pdf(_bundle(source_mode="verified_cached", source_disclosure=disclosure)))
    assert "VERIFIED CACHED ANALYSIS" in text
    assert disclosure in text


def test_missing_cache_disclosure_is_rejected() -> None:
    raw = _bundle().model_dump(mode="json")
    raw["source_mode"] = "verified_cached"
    raw["source_disclosure"] = ""
    with pytest.raises(ValidationError, match="source_disclosure"):
        ReportRenderBundle.model_validate(raw)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda raw: raw["analysis"]["findings"][0].update({"claim_id": "missing-claim"}),
            "unknown finding claim_id",
        ),
        (
            lambda raw: raw["snapshot"].update({"finding_ids": ["missing-finding"]}),
            "snapshot finding IDs",
        ),
        (
            lambda raw: raw["snapshot"]["classification_counts"].update({"supported": 99}),
            "classification counts",
        ),
        (
            lambda raw: raw["snapshot"].update({"evidence_chain_sha256": "a" * 64}),
            "evidence hash",
        ),
        (
            lambda raw: raw["snapshot"].update({"economic_context_point_ids": ["missing-context"]}),
            "snapshot context IDs",
        ),
        (
            lambda raw: raw["trend"]["points"][0].update(
                {"evidence_source_span_id": "missing-span"}
            ),
            "unknown trend evidence span ID",
        ),
    ],
)
def test_integrity_mismatches_are_rejected(mutate, message: str) -> None:
    raw = _bundle().model_dump(mode="json")
    mutate(raw)
    with pytest.raises(ValidationError, match=message):
        ReportRenderBundle.model_validate(raw)


def test_claim_changes_are_covered_by_the_evidence_hash() -> None:
    raw = _bundle().model_dump(mode="json")
    raw["analysis"]["claims"][0]["source_span_id"] = "span-pdf-2"
    with pytest.raises(ValidationError, match="evidence hash"):
        ReportRenderBundle.model_validate(raw)


def test_report_requires_a_hero_finding() -> None:
    raw = _bundle().model_dump(mode="json")
    raw["analysis"]["findings"] = []
    raw["snapshot"]["finding_ids"] = []
    raw["snapshot"]["classification_counts"] = {
        "supported": 0,
        "uncertain": 0,
        "contradicted": 0,
    }
    raw["snapshot"]["evidence_chain_sha256"] = canonical_sha256(
        AnalysisResponse.model_validate(raw["analysis"])
    )
    with pytest.raises(ValidationError, match="at least one reviewed finding"):
        ReportRenderBundle.model_validate(raw)


def test_uncited_causal_language_in_generated_finding_text_is_rejected() -> None:
    raw = _bundle().model_dump(mode="json")
    raw["analysis"]["findings"][0]["rationale"] = "The variance was driven by inflation."
    _rehash_analysis(raw)
    with pytest.raises(ValidationError, match="deterministic classification output"):
        ReportRenderBundle.model_validate(raw)


@pytest.mark.parametrize(
    "unsafe_text",
    (
        "Inflation caused the variance.",
        "The variance occurred because inflation rose.",
        "Inflation led to the variance.",
        "We recommend buying shares.",
        "Investors should buy shares.",
        "Revenue will rise next year.",
        "The reviewer must hold the shares.",
        "This is investment advice.",
        "Inflation triggered the variance",
        "stems directly from inflation",
        "Investors may accumulate shares",
        "Revenue may rise in the coming year",
        "shares appear undervalued",
    ),
)
def test_endpoint_rejects_causal_advisory_imperative_and_forecast_text(
    unsafe_text: str,
) -> None:
    raw = _bundle().model_dump(mode="json")
    raw["snapshot"]["limitations"] = [unsafe_text]

    response = _post_report(raw)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize(
    ("mutate", "rehash"),
    (
        (
            lambda raw: raw["analysis"]["claims"][0].update(
                {"text": "Inflation caused the variance."}
            ),
            True,
        ),
        (
            lambda raw: raw["analysis"]["findings"][0].update(
                {"rationale": "The variance was due to inflation."}
            ),
            True,
        ),
        (
            lambda raw: raw["analysis"]["findings"][0].update(
                {"suggested_investigation": "Revenue will rise next year."}
            ),
            True,
        ),
        (
            lambda raw: raw["analysis"]["metric_results"][0].update(
                {"warnings": ["Investors should sell shares."]}
            ),
            True,
        ),
        (
            lambda raw: raw["analysis"]["findings"][0].update(
                {"warnings": ["We recommend buying shares."]}
            ),
            True,
        ),
        (
            lambda raw: raw["analysis"]["documents"][0].update(
                {"version_label": "Projected revenue outlook"}
            ),
            True,
        ),
        (
            lambda raw: raw["snapshot"].update({"title": "Buy Apple shares now"}),
            False,
        ),
        (
            lambda raw: raw["economic_context"][0].update(
                {"relevance": "Prices increased because demand rose."}
            ),
            False,
        ),
        (
            lambda raw: raw["economic_context"][0].update(
                {"comparability_warning": "Revenue will rise next year."}
            ),
            False,
        ),
        (
            lambda raw: raw["trend"].update({"indicator": "Recommended revenue outlook"}),
            False,
        ),
        (
            lambda raw: raw["trend"]["points"][0].update({"reporting_basis": "Projected revenue"}),
            False,
        ),
        (
            lambda raw: raw.update(
                {
                    "source_mode": "verified_cached",
                    "source_disclosure": "Revenue will rise next year.",
                }
            ),
            False,
        ),
    ),
)
def test_endpoint_rejects_policy_bypasses_across_rendered_fields(mutate, rehash: bool) -> None:
    raw = _bundle().model_dump(mode="json")
    mutate(raw)
    if rehash:
        _rehash_analysis(raw)

    response = _post_report(raw)

    assert response.status_code == 422


def test_endpoint_rejects_cross_company_and_mixed_issuer_provenance() -> None:
    relabeled = _bundle().model_dump(mode="json")
    relabeled["company_id"] = "apple-fy2025"
    relabeled["company"] = "Apple Inc."
    relabeled["snapshot"]["title"] = "Apple Inc. reviewed evidence report"
    relabeled["trend"]["company"] = "Apple Inc."
    relabeled["trend"]["indicator"] = "Total net sales"
    for point in relabeled["trend"]["points"]:
        point["reporting_basis"] = "Apple consolidated annual net sales"
    apple = get_company_lens("apple-fy2025")
    assert apple is not None
    relabeled["economic_context"] = [apple.economic_context[0].model_dump(mode="json")]
    relabeled["snapshot"]["economic_context_point_ids"] = [apple.economic_context[0].id]
    response = _post_report(relabeled)
    assert response.status_code == 422
    assert "issuer must match bundle company" in response.text

    mixed = _bundle().model_dump(mode="json")
    mixed["analysis"]["documents"][1]["issuer"] = "Other Issuer"
    _rehash_analysis(mixed)
    response = _post_report(mixed)
    assert response.status_code == 422
    assert "documents must use one issuer" in response.text

    empty = _bundle().model_dump(mode="json")
    empty["analysis"]["documents"] = []
    _rehash_analysis(empty)
    response = _post_report(empty)
    assert response.status_code == 422
    assert "at least one issuer-bearing document" in response.text


def test_endpoint_binds_company_id_and_claim_entity() -> None:
    company_id_mismatch = _bundle().model_dump(mode="json")
    company_id_mismatch["company_id"] = "apple-fy2025"
    response = _post_report(company_id_mismatch)
    assert response.status_code == 422
    assert "registered company" in response.text

    entity_mismatch = _bundle().model_dump(mode="json")
    entity_mismatch["analysis"]["claims"][0]["entity"] = "Other Issuer"
    _rehash_analysis(entity_mismatch)
    response = _post_report(entity_mismatch)
    assert response.status_code == 422
    assert "claim entity must match bundle company" in response.text


def test_endpoint_binds_snapshot_analysis_id_to_canonical_analysis() -> None:
    raw = _bundle().model_dump(mode="json")
    raw["snapshot"]["analysis_id"] = "arbitrary-analysis-id"

    response = _post_report(raw)

    assert response.status_code == 422
    assert "analysis_id must identify the canonical analysis hash" in response.text


def test_invalid_context_and_forecasts_are_rejected() -> None:
    context = _context().model_dump(mode="json")
    context["official_source_url"] = "http://example.test/not-official"
    with pytest.raises(ValidationError, match="official source URL"):
        ResolvedEconomicContextPoint.model_validate(context)

    snapshot = _bundle().snapshot.model_dump(mode="json")
    snapshot["includes_forecast"] = True
    with pytest.raises(ValidationError, match="includes_forecast"):
        ReportSnapshot.model_validate(snapshot)


def test_short_and_mixed_basis_trends_are_rejected() -> None:
    raw = _trend().model_dump(mode="json")
    raw["points"] = raw["points"][:2]
    with pytest.raises(ValidationError, match="at least 3"):
        FinancialTrendSeries.model_validate(raw)

    raw = _trend().model_dump(mode="json")
    raw["points"][1]["reporting_basis"] = "Standalone revenue"
    with pytest.raises(ValidationError, match="one reporting basis"):
        FinancialTrendSeries.model_validate(raw)


def test_exceptional_metrics_render_without_numeric_formatting() -> None:
    analysis = _analysis().model_dump(mode="json")
    analysis["metric_results"][0]["result"] = None
    analysis["metric_results"][0]["exceptional_state"] = "missing_input"
    analysis["findings"][0].update(
        {
            "classification": "uncertain",
            "rationale": "A deterministic comparison was not possible: missing_input.",
            "tolerance": None,
            "warnings": [],
            "suggested_investigation": (
                "Resolve the input exception and verify the cited source evidence."
            ),
        }
    )
    response = AnalysisResponse.model_validate(analysis)
    text = _text(render_pdf(_bundle(analysis=response)))
    assert "Exceptional state: missing_input" in text


def test_chart_and_value_table_use_the_same_validated_points() -> None:
    text = _text(render_pdf(_bundle()))
    for year, value in (("2023", "80"), ("2024", "90"), ("2025", "100")):
        assert year in text
        assert value in text


def test_xml_like_long_and_unicode_source_text_is_safe() -> None:
    raw = _analysis().model_dump(mode="json")
    raw["source_spans"][0]["source"]["quote"] = (
        '<tag attr="x"> Montréal & 中 😊 Inflation caused the variance; analyst said buy. '
        + "A" * 500
    )
    response = AnalysisResponse.model_validate(raw)
    text = _text(render_pdf(_bundle(analysis=response)))
    assert "<tag attr=" in text
    assert "Montréal" in text
    assert "[U+4E2D]" in text
    assert "[U+1F60A]" in text
    assert "Inflation caused the variance; analyst said buy." in " ".join(text.split())


def test_renderer_never_fetches_or_recalculates(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("renderer attempted external work")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert render_pdf(_bundle()).startswith(b"%PDF")


def test_reviewed_json_fallback_is_canonical_and_complete() -> None:
    bundle = _bundle()
    exported = render_evidence_json(bundle)
    assert exported == canonical_json_bytes(bundle) + b"\n"
    parsed = json.loads(exported)
    assert parsed["analysis"]["claims"]
    assert parsed["snapshot"]["review_status"] == "reviewed"


def test_pdf_endpoint_headers_hash_filename_and_no_store() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/reports/pdf",
        json=_bundle().model_dump(mode="json"),
    )
    digest = hashlib.sha256(response.content).hexdigest()
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["etag"] == f'"{digest}"'
    assert response.headers["x-content-sha256"] == digest
    assert response.headers["x-report-bundle-sha256"] == canonical_sha256(_bundle())
    assert response.headers["content-disposition"] == (
        'attachment; filename="proofline-example-group-fy2025-reviewed-example-fy2025.pdf"'
    )


def test_same_endpoint_preserves_json_evidence_export_fallback() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/reports/pdf?output=evidence-json",
        json=_bundle().model_dump(mode="json"),
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"].endswith('.json"')
    assert response.json()["data_handling_disclosure"] == DATA_HANDLING_DISCLOSURE


def test_generated_policy_language_is_narrow_and_non_causal() -> None:
    text = _text(render_pdf(_bundle())).lower()
    for phrase in (
        "caused",
        "because",
        "driven by",
        "led to",
        "resulted in",
        "explains",
        "recommend buying",
        "should buy",
        "will rise",
        "pdpa compliant",
    ):
        assert phrase not in text
    assert "secure erasure" in text
    assert "does not provide secure erasure" in text


def test_decimal_and_timestamp_canonicalization() -> None:
    first = canonical_json_bytes(
        {"value": __import__("decimal").Decimal("1.2300"), "at": "2026-08-22T00:00:00Z"}
    )
    second = canonical_json_bytes(
        {"at": "2026-08-22T00:00:00Z", "value": __import__("decimal").Decimal("1.23")}
    )
    assert first == second
    offset = timezone(timedelta(hours=8))
    assert canonical_json_bytes({"at": datetime(2026, 8, 22, 8, 0, 0, 123400, offset)}) == (
        b'{"at":"2026-08-22T00:00:00.1234Z"}'
    )


def test_canonical_json_rejects_non_string_mapping_keys_deterministically() -> None:
    for value in ({"1": "string", 1: "number"}, {1: "number", "1": "string"}):
        with pytest.raises(TypeError, match="canonical mappings require string keys"):
            canonical_json_bytes(value)


def test_canonical_float_signed_zero_is_normalized() -> None:
    positive = {"x": 0.0}
    negative = {"x": -0.0}

    assert canonical_json_bytes(positive) == canonical_json_bytes(negative)
    assert canonical_sha256(positive) == canonical_sha256(negative)
