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
    GENERIC_CONTEXT_COMPARABILITY,
    GENERIC_CONTEXT_RELEVANCE,
    LIVE_SOURCE_DISCLOSURE,
    NO_CAUSATION,
    VERIFIED_CACHED_SOURCE_DISCLOSURE,
    FinancialTrendSeries,
    ReportRenderBundle,
    ResolvedEconomicContextPoint,
    canonical_json_bytes,
    canonical_sha256,
    generic_company_id,
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
        report_profile={
            "reporting_period": {
                "start": "2025-01-01",
                "end": "2025-12-31",
                "duration_weeks": 52,
            },
            "primary_observation_ids": (
                "revenue-current",
                "operating-profit",
                "current-assets",
                "operating-cash-flow",
            ),
            "secondary_metric_result_ids": tuple(
                result.id for result in response.metric_results[:4]
            ),
        },
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


def _synthetic_issuer_bundle(company: str, currency: str) -> ReportRenderBundle:
    raw = _bundle().model_dump(mode="json")
    raw["company"] = company
    raw["company_id"] = generic_company_id(company)
    raw["snapshot"]["title"] = f"{company} reviewed evidence report"
    raw["snapshot"]["economic_context_point_ids"] = ["context-synthetic-gdp"]
    raw["economic_context"] = [
        {
            "id": "context-synthetic-gdp",
            "company": company,
            "indicator": "Real GDP annual growth",
            "geography": "Reporting market",
            "period": {"start": "2025-01-01", "end": "2025-12-31"},
            "value": "2.4",
            "display_value": "2.4%",
            "unit": "percent year over year",
            "official_source_url": "https://www.oecd.org/economy/",
            "official_source_confirmed": True,
            "published_on": "2026-01-31",
            "retrieved_on": "2026-08-22",
            "relevance": GENERIC_CONTEXT_RELEVANCE,
            "comparability_warning": GENERIC_CONTEXT_COMPARABILITY,
            "caveat": NO_CAUSATION,
            "default_visible": True,
        }
    ]
    for document in raw["analysis"]["documents"]:
        document["issuer"] = company
    for claim in raw["analysis"]["claims"]:
        claim["entity"] = company
        if claim["currency"] is not None:
            claim["currency"] = currency
    for observation in raw["analysis"]["observations"]:
        observation["entity_scope"] = company
        observation["currency"] = currency
        observation["unit"] = f"{currency} millions"
    raw["trend"]["company"] = company
    raw["trend"]["currency"] = currency
    raw["trend"]["unit"] = f"{currency} millions"
    analysis = AnalysisResponse.model_validate(raw["analysis"])
    digest = canonical_sha256(analysis)
    raw["snapshot"]["evidence_chain_sha256"] = digest
    raw["snapshot"]["analysis_id"] = f"sha256:{digest}"
    return ReportRenderBundle.model_validate(raw)


def test_pdf_is_byte_deterministic_and_sections_are_ordered() -> None:
    bundle = _bundle()
    first = render_pdf(bundle)
    second = render_pdf(bundle)
    text = _text(first)

    assert first == second
    headings = (
        "1. Executive summary",
        "2. Four primary financial metrics",
        "3. Secondary ratios",
        "4. Historical trend and value table",
        "5. Exceptions and review risks",
        "6. Narrative-versus-numbers findings",
        "7. Economic context - no causation",
        "8. Evidence and provenance appendix",
        "9. Methodology and limitations",
        "10. Data handling and export disclosure",
    )
    offsets = [text.index(heading) for heading in headings]
    assert offsets == sorted(offsets)
    assert "PROTOTYPE - HUMAN REVIEW REQUIRED" in text
    assert NO_CAUSATION in text
    assert DATA_HANDLING_DISCLOSURE in " ".join(text.split())


def test_pdf_is_a_substantial_a4_editorial_report_with_page_chrome() -> None:
    reader = PdfReader(__import__("io").BytesIO(render_pdf(_bundle())))

    assert 5 <= len(reader.pages) <= 7
    for page_number, page in enumerate(reader.pages, start=1):
        assert float(page.mediabox.width) == pytest.approx(595.276, abs=0.01)
        assert float(page.mediabox.height) == pytest.approx(841.89, abs=0.01)
        text = page.extract_text() or ""
        assert len(text.strip()) >= 700
        assert f"PAGE {page_number:02d}" in text
        assert "EDITORIAL LEDGER - PROTOTYPE - HUMAN REVIEW REQUIRED" in text


def test_pdf_translates_financial_ratios_and_preserves_auditable_visual_fallback() -> None:
    text = " ".join(_text(render_pdf(_bundle())).split())

    for concept in ("Growth", "Profitability", "Liquidity", "Cash flow"):
        assert concept in text
    assert "point-in-time coverage indicator" in text
    assert "non-GAAP view" in text
    assert "discrete period comparison" in text
    assert "Exact value" in text
    assert "Evidence and provenance appendix" in text
    assert "recommended next step" in text.lower()


@pytest.mark.parametrize(
    ("company", "currency"),
    (("Northstar Manufacturing plc", "GBP"), ("Sakura Components Co.", "JPY")),
)
def test_report_is_issuer_agnostic_across_synthetic_companies_and_currencies(
    company: str, currency: str
) -> None:
    bundle = _synthetic_issuer_bundle(company, currency)
    text = _text(render_pdf(bundle))

    assert company in text
    assert f"{currency} millions" in text
    assert "Four primary financial metrics" in text
    assert "Secondary ratios" in text
    assert "Historical trend and value table" in text
    assert "Real GDP annual growth" in text
    assert "shareholder" not in text.lower()
    assert "ownership" not in text.lower()


def test_generic_report_explicitly_discloses_absent_reviewed_context() -> None:
    raw = _synthetic_issuer_bundle("Contextless Holdings", "EUR").model_dump(mode="json")
    raw["economic_context"] = []
    raw["snapshot"]["economic_context_point_ids"] = []

    text = _text(render_pdf(ReportRenderBundle.model_validate(raw)))

    assert "No reviewed economic context was supplied" in text
    assert NO_CAUSATION in text


def test_report_fails_closed_on_currency_and_period_ambiguity() -> None:
    currency = _bundle().model_dump(mode="json")
    currency["analysis"]["observations"][2]["currency"] = "EUR"
    _rehash_analysis(currency)
    currency["snapshot"]["analysis_id"] = f"sha256:{currency['snapshot']['evidence_chain_sha256']}"
    response = _post_report(currency)
    assert response.status_code == 422
    assert "one explicit currency" in response.text

    period = _bundle().model_dump(mode="json")
    period["report_profile"]["reporting_period"]["start"] = "2024-01-01"
    period["report_profile"]["reporting_period"]["end"] = "2024-12-31"
    response = _post_report(period)
    assert response.status_code == 422
    assert "periods must match" in response.text


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
        point["reporting_basis"] = "Consolidated annual net sales"
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
    assert "company_id does not match" in response.text

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


def test_report_profile_order_is_covered_by_bundle_and_content_hashes() -> None:
    first = _bundle()
    raw = first.model_dump(mode="json")
    raw["report_profile"]["primary_observation_ids"] = list(
        reversed(raw["report_profile"]["primary_observation_ids"])
    )
    second = ReportRenderBundle.model_validate(raw)

    assert canonical_sha256(first) != canonical_sha256(second)
    assert hashlib.sha256(render_pdf(first)).digest() != hashlib.sha256(render_pdf(second)).digest()


def test_report_profile_cannot_introduce_a_forecast() -> None:
    raw = _bundle().model_dump(mode="json")
    raw["report_profile"]["forecast"] = {
        "value": "110",
        "method": "management estimate",
    }

    response = _post_report(raw)

    assert response.status_code == 422


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
