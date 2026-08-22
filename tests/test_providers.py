import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from proofline.api import app
from proofline.contracts import AnalysisRequest
from proofline.providers.contracts import (
    AssistantRequest,
    AssistantResult,
    ClaimExtractionRequest,
    ClaimExtractionResult,
    EvidenceCitation,
    EvidenceExcerpt,
    ProviderState,
    SourcePage,
)
from proofline.providers.fixture import DeterministicFixtureProvider
from proofline.providers.gemma import GemmaProvider

FIXTURE = Path(__file__).parent / "fixtures" / "tier0_analysis.json"


class FakeTransport:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls = []

    async def post_json(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def gemma(api_key: str | None = None, transport=None) -> GemmaProvider:
    return GemmaProvider(api_key, "gemma-4-26b-a4b-it", 5, 0, transport=transport)


def assistant_request(prompt: str = "Explain revenue") -> AssistantRequest:
    return AssistantRequest(
        prompt=prompt,
        evidence=(
            EvidenceExcerpt(
                evidence_id="evidence-1",
                source_span_id="span-pdf-1",
                text="Revenue increased by 25%.",
            ),
        ),
        provider_sent=True,
    )


def extraction_request(text: str = "Revenue increased.") -> ClaimExtractionRequest:
    return ClaimExtractionRequest(
        pages=(SourcePage(page=1, source_span_id="span-pdf-1", text=text),),
        provider_sent=True,
    )


def test_default_gemma_is_truthfully_not_configured_and_non_networking() -> None:
    provider = gemma()
    result = asyncio.run(provider.assist(assistant_request()))
    extraction = asyncio.run(provider.extract_claims(extraction_request()))

    assert provider.status().state == "not_configured"
    assert provider.status().live_transport_enabled is False
    assert provider.status().document_content_sent is False
    assert result.state == ProviderState.NOT_CONFIGURED
    assert result.content is None and result.citations == ()
    assert extraction.state == ProviderState.NOT_CONFIGURED
    assert extraction.claims == () and extraction.citations == ()


def test_supplied_secret_is_not_retained_represented_or_returned(caplog) -> None:
    secret = "server-secret-sentinel"
    provider = gemma(secret)
    assert not hasattr(provider, "api_key")
    assert secret not in repr(provider)
    assert secret not in repr(vars(provider))
    assert secret not in provider.status().model_dump_json()
    assert secret not in caplog.text
    assert provider.status().state == "ready"


@pytest.mark.parametrize("model", ["gemma-4", "gemini-4", "gemma-3-27b-it"])
def test_unofficial_or_unsupported_model_names_fail_closed(model: str) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        GemmaProvider(None, model, 5, 0)


@pytest.mark.parametrize(("timeout", "retries"), [(0, 0), (61, 0), (5, -1), (5, 3)])
def test_transport_limits_fail_closed(timeout: float, retries: int) -> None:
    with pytest.raises(ValueError):
        GemmaProvider(None, "gemma-4-26b-a4b-it", timeout, retries)


def test_provider_sent_declaration_and_input_bounds_are_required() -> None:
    with pytest.raises(ValidationError):
        AssistantRequest(
            prompt="x",
            evidence=(EvidenceExcerpt(evidence_id="e-1", source_span_id="span-1", text="x"),),
        )
    with pytest.raises(ValidationError):
        AssistantRequest(
            prompt="x" * 2_001,
            evidence=(EvidenceExcerpt(evidence_id="e-1", source_span_id="span-1", text="x"),),
            provider_sent=True,
        )
    with pytest.raises(ValidationError):
        ClaimExtractionRequest(
            pages=(SourcePage(page=1, source_span_id="span-1", text="x" * 8_001),),
            provider_sent=True,
        )


def test_completed_assistant_output_requires_citation_and_is_bounded() -> None:
    with pytest.raises(ValidationError):
        AssistantResult(
            state="completed", content="uncited", provider="test", model="test", disclosure="x"
        )
    with pytest.raises(ValidationError):
        AssistantResult(
            state="completed",
            content="x" * 4_001,
            citations=(
                EvidenceCitation(evidence_id="span-1", source_span_id="span-1", label="span-1"),
            ),
            provider="test",
            model="test",
            disclosure="x",
        )


def test_extracted_claims_require_resolvable_source_span_citations() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["request"]
    claim = AnalysisRequest.model_validate(payload).claims[0]
    with pytest.raises(ValidationError, match="source-span citation"):
        ClaimExtractionResult(
            state="completed",
            claims=(claim,),
            provider="test",
            model="test",
            disclosure="x",
        )


def test_fixture_provider_is_deterministic_cited_and_refuses_unknown_prompts() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["request"]
    claim = AnalysisRequest.model_validate(payload).claims[0]
    provider = DeterministicFixtureProvider(
        answers={"Explain revenue": "Revenue is supported by the cited fixture."}, claims=(claim,)
    )

    first = asyncio.run(provider.assist(assistant_request()))
    second = asyncio.run(provider.assist(assistant_request()))
    unknown = asyncio.run(provider.assist(assistant_request("unlisted prompt")))
    extracted = asyncio.run(provider.extract_claims(extraction_request()))

    assert first == second
    assert first.state == ProviderState.FALLBACK
    assert first.citations[0].source_span_id == "span-pdf-1"
    assert unknown.state == ProviderState.ERROR
    assert unknown.content is None and unknown.citations == ()
    assert extracted.claims == (claim,)
    assert extracted.citations[0].source_span_id == claim.source_span_id


def wrapped(payload: dict) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}


def test_live_assistant_sends_only_bounded_request_and_accepts_cited_json() -> None:
    transport = FakeTransport(
        wrapped(
            {
                "content": "Revenue increased by 25%.",
                "citations": [
                    {
                        "evidence_id": "evidence-1",
                        "source_span_id": "span-pdf-1",
                        "label": "Revenue evidence",
                    }
                ],
            }
        )
    )
    provider = gemma(transport=transport)
    result = asyncio.run(provider.assist(assistant_request()))

    assert result.state == ProviderState.COMPLETED
    assert result.citations[0].evidence_id == "evidence-1"
    assert len(transport.calls) == 1
    assert transport.calls[0]["url"].endswith("gemma-4-26b-a4b-it:generateContent")
    sent = json.dumps(transport.calls[0]["payload"])
    assert "Revenue increased by 25%." in sent
    assert "GOOGLE_API_KEY" not in sent


@pytest.mark.parametrize(
    ("transport", "expected"),
    [
        (FakeTransport(error=TimeoutError()), ProviderState.OFFLINE),
        (FakeTransport(response={"unexpected": True}), ProviderState.ERROR),
        (
            FakeTransport(
                wrapped(
                    {
                        "content": "Invented",
                        "citations": [
                            {
                                "evidence_id": "not-supplied",
                                "source_span_id": "not-supplied",
                                "label": "bad",
                            }
                        ],
                    }
                )
            ),
            ProviderState.ERROR,
        ),
    ],
)
def test_live_assistant_failures_are_typed_and_redacted(transport, expected) -> None:
    result = asyncio.run(gemma(transport=transport).assist(assistant_request()))
    assert result.state == expected
    assert result.content is None and result.citations == ()
    assert "unexpected" not in result.model_dump_json()


def test_live_extraction_accepts_only_cited_claims_from_supplied_spans() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["request"]
    claim = AnalysisRequest.model_validate(payload).claims[0]
    transport = FakeTransport(
        wrapped(
            {
                "claims": [claim.model_dump(mode="json")],
                "citations": [
                    {
                        "evidence_id": claim.source_span_id,
                        "source_span_id": claim.source_span_id,
                        "label": "Page 1",
                    }
                ],
            }
        )
    )
    result = asyncio.run(gemma(transport=transport).extract_claims(extraction_request()))
    assert result.state == ProviderState.COMPLETED
    assert result.claims == (claim,)


def test_connection_test_uses_no_document_content_and_redacts_failure() -> None:
    ready = FakeTransport(wrapped({"ok": True}))
    result = asyncio.run(gemma(transport=ready).test_connection())
    assert result.reachable is True
    sent = json.dumps(ready.calls[0]["payload"])
    assert "Revenue" not in sent

    malformed = asyncio.run(
        gemma(transport=FakeTransport(response={"upstream": "secret detail"})).test_connection()
    )
    assert malformed.state == "error"
    assert "secret detail" not in malformed.model_dump_json()


def test_api_status_connection_and_default_answers_are_redacted() -> None:
    request = assistant_request().model_dump(mode="json")
    with TestClient(app) as client:
        status = client.get("/api/v1/providers/model")
        connection = client.post("/api/v1/providers/model/test")
        answer = client.post("/api/v1/assistant", json=request)

    assert status.status_code == connection.status_code == answer.status_code == 200
    assert status.json()["state"] == "not_configured"
    assert status.json()["document_content_sent"] is False
    assert connection.json()["reachable"] is False
    assert answer.json()["state"] == "not_configured"
    serialized = status.text + connection.text + answer.text
    assert "GOOGLE_API_KEY" not in serialized
    assert "GEMINI_API_KEY" not in serialized


def test_openapi_never_contains_secret_values_or_secret_fields() -> None:
    serialized = json.dumps(app.openapi())
    assert "GOOGLE_API_KEY" not in serialized
    assert "GEMINI_API_KEY" not in serialized
    assert '"api_key"' not in serialized
