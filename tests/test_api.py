import json
from pathlib import Path

from fastapi.testclient import TestClient

from proofline.api import app
from proofline.contracts import AnalysisRequest

FIXTURE = Path(__file__).parent / "fixtures" / "tier0_analysis.json"


def test_health_does_not_require_model_key() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "schema_version": "1.0.0",
        "metric_registry_version": "1.0.0",
        "model_provider": "gemma",
        "model_configured": False,
    }


def test_analysis_endpoint_uses_string_decimals() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with TestClient(app) as client:
        response = client.post("/api/v1/analyses", json=fixture["request"])

    assert response.status_code == 200
    body = response.json()
    assert body["metric_results"][0]["result"] == "0.25"
    assert body["findings"][1]["classification"] == "contradicted"


def test_contract_rejects_executable_or_extra_plan_fields() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))["request"]
    fixture["items"][0]["calculation_plan"]["code"] = "__import__('os').system('false')"
    with TestClient(app) as client:
        response = client.post("/api/v1/analyses", json=fixture)

    assert response.status_code == 422


def test_contract_rejects_unknown_claim_reference() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))["request"]
    fixture["items"][0]["claim_id"] = "not-present"
    with TestClient(app) as client:
        response = client.post("/api/v1/analyses", json=fixture)

    assert response.status_code == 422


def test_checked_in_request_schema_matches_runtime_contract() -> None:
    checked_in = json.loads(
        (Path(__file__).parents[1] / "contracts/v1/analysis-request.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert checked_in == AnalysisRequest.model_json_schema()
