from fastapi.testclient import TestClient

from proofline.api import app
from proofline.economic_context import get_company_lens
from proofline.report_contracts import NO_CAUSATION


def test_company_lenses_use_official_sources_and_compact_defaults() -> None:
    apple = get_company_lens("apple-fy2025")
    pcg = get_company_lens("pcg-fy2025")

    assert apple is not None
    assert pcg is not None
    assert len(apple.economic_context) == 4
    assert len(pcg.economic_context) == 4
    assert len(pcg.additional_context) == 1
    assert "selling-price" in pcg.economic_context[1].comparability_warning
    assert len(apple.trend.points) == 3
    assert len(pcg.trend.points) == 3
    for lens in (apple, pcg):
        assert lens.context_caveat == NO_CAUSATION
        for point in lens.economic_context + lens.additional_context:
            assert point.company == lens.company
            assert point.official_source_url.startswith("https://")
            assert point.caveat == NO_CAUSATION
            assert point.relevance
            assert point.comparability_warning
            assert point.published_on <= point.retrieved_on


def test_unknown_company_lens_is_not_invented() -> None:
    assert get_company_lens("unknown-company") is None


def test_company_lens_api_exposes_the_exact_caveat_and_interactive_series() -> None:
    response = TestClient(app).get("/api/v1/company-lenses/apple-fy2025")

    assert response.status_code == 200
    payload = response.json()
    assert payload["context_caveat"] == NO_CAUSATION
    assert len(payload["economic_context"]) == 4
    assert len(payload["trend"]["points"]) == 3
    assert all(point["historical"] is True for point in payload["trend"]["points"])
