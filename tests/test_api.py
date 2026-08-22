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
    assert body["cached_output"] is False
    assert body["documents"][0]["id"] == "pdf-doc"
    assert body["claims"][0]["source_span_id"] == "span-pdf-1"
    span_ids = {span["id"] for span in body["source_spans"]}
    observation_ids = {observation["id"] for observation in body["observations"]}
    assert set(body["findings"][0]["evidence_source_span_ids"]) <= span_ids
    assert set(body["metric_results"][0]["input_observation_ids"]) <= observation_ids


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


def test_session_intake_status_and_scoped_deletion_receipt() -> None:
    request = {
        "schema_version": "1.0.0",
        "input": {
            "kind": "fixture",
            "fixture_id": "apple-fy2025",
            "public_data_confirmed": True,
        },
    }
    with TestClient(app) as client:
        created = client.post("/api/v1/sessions", json=request)
        session_id = created.json()["session_id"]
        status = client.get(f"/api/v1/sessions/{session_id}")
        deleted = client.delete(f"/api/v1/sessions/{session_id}")
        missing = client.get(f"/api/v1/sessions/{session_id}")

    assert created.status_code == 201
    assert status.json()["state"] == "accepted"
    assert status.json()["cached_output_status"] == "not_checked"
    assert "not implemented" in status.json()["fallback_disclosure"]
    assert deleted.json()["scope"] == ["in_memory_session_metadata"]
    assert "metadata only" in deleted.json()["disclosure"]
    assert missing.status_code == 404


def test_upload_intake_requires_public_data_confirmation_and_safe_extensions() -> None:
    request = {
        "input": {
            "kind": "upload",
            "pdf_filename": "report.pdf",
            "workbook_filename": "facts.xlsm",
            "public_data_confirmed": False,
        }
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/sessions", json=request)

    assert response.status_code == 422
