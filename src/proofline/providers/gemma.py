import asyncio
import json
import urllib.error
import urllib.request
from typing import Any, Protocol

from pydantic import Field, SecretStr, ValidationError, model_validator

from proofline.contracts import FinancialClaim, FrozenModel
from proofline.providers.base import ProviderUnavailable
from proofline.providers.contracts import (
    AssistantRequest,
    AssistantResult,
    ClaimExtractionRequest,
    ClaimExtractionResult,
    EvidenceCitation,
    ProviderConnectionTest,
    ProviderError,
    ProviderState,
    ProviderStatus,
)

SUPPORTED_GEMMA_4_MODELS = frozenset({"gemma-4-31b-it", "gemma-4-26b-a4b-it"})
API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
NO_SEND_DISCLOSURE = "No prompt or document content was sent to an external provider."
SENT_DISCLOSURE = (
    "Only the bounded evidence excerpts in this request were sent to Gemma 4 through the hosted "
    "Gemini Developer API."
)


class ProviderTransport(Protocol):
    async def post_json(
        self, *, url: str, payload: dict[str, Any], timeout_seconds: float
    ) -> dict[str, Any]: ...


class GeminiHttpTransport:
    """Minimal stdlib transport; the server secret stays redacted in a SecretStr."""

    def __init__(self, api_key: str) -> None:
        self._api_key = SecretStr(api_key)

    async def post_json(
        self, *, url: str, payload: dict[str, Any], timeout_seconds: float
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._post, url, payload, timeout_seconds)

    def _post(self, url: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self._api_key.get_secret_value(),
            },
            method="POST",
        )
        opener = urllib.request.build_opener(_NoRedirectHandler())
        with opener.open(request, timeout=timeout_seconds) as response:
            raw = response.read(65_537)
        if len(raw) > 65_536:
            raise ValueError("provider response exceeded 65536 bytes")
        decoded = json.loads(raw)
        if not isinstance(decoded, dict):
            raise ValueError("provider response must be an object")
        return decoded


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        del req, fp, code, msg, headers, newurl
        return None


class RemoteAssistantPayload(FrozenModel):
    content: str = Field(min_length=1, max_length=4_000)
    citations: tuple[EvidenceCitation, ...] = Field(min_length=1, max_length=12)


class RemoteExtractionPayload(FrozenModel):
    claims: tuple[FinancialClaim, ...] = Field(max_length=24)
    citations: tuple[EvidenceCitation, ...] = Field(max_length=24)

    @model_validator(mode="after")
    def cited_claims(self) -> "RemoteExtractionPayload":
        cited = {citation.source_span_id for citation in self.citations}
        if any(claim.source_span_id not in cited for claim in self.claims):
            raise ValueError("each claim requires a source-span citation")
        return self


class GemmaProvider:
    """Server-only Gemma 4 adapter; it has no filesystem or database capability."""

    def __init__(
        self,
        api_key: str | None,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        transport: ProviderTransport | None = None,
    ) -> None:
        if model not in SUPPORTED_GEMMA_4_MODELS:
            raise ValueError("unsupported hosted Gemma 4 model")
        if not 1 <= timeout_seconds <= 60:
            raise ValueError("provider timeout must be between 1 and 60 seconds")
        if not 0 <= max_retries <= 2:
            raise ValueError("provider retries must be between 0 and 2")
        key = api_key.strip() if api_key else ""
        self._transport = transport or (GeminiHttpTransport(key) if key else None)
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @property
    def configured(self) -> bool:
        return self._transport is not None

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            state="ready" if self.configured else "not_configured",
            provider="gemma_via_gemini_api",
            model=self.model,
            live_transport_enabled=self.configured,
            disclosure=(
                "Server-side hosted transport is configured; no content has been sent."
                if self.configured
                else NO_SEND_DISCLOSURE
            ),
        )

    async def test_connection(self) -> ProviderConnectionTest:
        if not self._transport:
            return ProviderConnectionTest(
                reachable=False, state="not_configured", disclosure=NO_SEND_DISCLOSURE
            )
        try:
            response = await self._request(
                'Return exactly the JSON object {"ok":true}. Do not add other text.'
            )
            parsed = json.loads(self._response_text(response))
            if parsed != {"ok": True}:
                raise ValueError("unexpected connection response")
        except (TimeoutError, urllib.error.URLError):
            return ProviderConnectionTest(
                reachable=False,
                state="offline",
                disclosure="Provider connection failed or timed out; no document content was sent.",
            )
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return ProviderConnectionTest(
                reachable=False,
                state="error",
                disclosure=(
                    "Provider connection returned an invalid response; details were redacted."
                ),
            )
        return ProviderConnectionTest(
            reachable=True,
            state="ready",
            disclosure="Provider connection succeeded; no document content was sent.",
        )

    async def assist(self, request: AssistantRequest) -> AssistantResult:
        if not self._transport:
            return self._assistant_unavailable(ProviderState.NOT_CONFIGURED)
        allowed_evidence = {item.evidence_id: item.source_span_id for item in request.evidence}
        prompt = json.dumps(
            {
                "task": "Answer only from evidence. Return JSON: content and citations.",
                "question": request.prompt,
                "evidence": [item.model_dump(mode="json") for item in request.evidence],
                "citation_schema": {
                    "evidence_id": "one supplied evidence_id",
                    "source_span_id": "its supplied source_span_id",
                    "label": "short label",
                },
            },
            separators=(",", ":"),
        )
        try:
            remote = RemoteAssistantPayload.model_validate_json(
                self._response_text(await self._request(prompt))
            )
            for citation in remote.citations:
                if allowed_evidence.get(citation.evidence_id) != citation.source_span_id:
                    raise ValueError("citation not present in supplied evidence")
        except (TimeoutError, urllib.error.URLError):
            return self._assistant_unavailable(ProviderState.OFFLINE)
        except (ValidationError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return self._assistant_error()
        return AssistantResult(
            state=ProviderState.COMPLETED,
            content=remote.content,
            citations=remote.citations,
            provider="gemma_via_gemini_api",
            model=self.model,
            disclosure=SENT_DISCLOSURE,
        )

    async def extract_claims(
        self, request: ClaimExtractionRequest | list[str]
    ) -> ClaimExtractionResult:
        if isinstance(request, list):
            raise ProviderUnavailable("Gemma extraction is not configured for legacy page input.")
        if not self._transport:
            return self._extraction_unavailable(ProviderState.NOT_CONFIGURED)
        allowed_spans = {page.source_span_id for page in request.pages}
        prompt = json.dumps(
            {
                "task": (
                    "Extract financial claims only from supplied pages. Return JSON with claims "
                    "matching the supplied FinancialClaim schema and citations."
                ),
                "pages": [page.model_dump(mode="json") for page in request.pages],
            },
            separators=(",", ":"),
        )
        try:
            remote = RemoteExtractionPayload.model_validate_json(
                self._response_text(await self._request(prompt))
            )
            if any(citation.source_span_id not in allowed_spans for citation in remote.citations):
                raise ValueError("citation not present in supplied pages")
        except (TimeoutError, urllib.error.URLError):
            return self._extraction_unavailable(ProviderState.OFFLINE)
        except (ValidationError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return self._extraction_error()
        return ClaimExtractionResult(
            state=ProviderState.COMPLETED,
            claims=remote.claims,
            citations=remote.citations,
            provider="gemma_via_gemini_api",
            model=self.model,
            disclosure=SENT_DISCLOSURE,
        )

    async def _request(self, prompt: str) -> dict[str, Any]:
        if not self._transport:
            raise RuntimeError("transport unavailable")
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0,
                "maxOutputTokens": 2048,
            },
        }
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    self._transport.post_json(
                        url=f"{API_ROOT}/{self.model}:generateContent",
                        payload=payload,
                        timeout_seconds=self.timeout_seconds,
                    ),
                    timeout=self.timeout_seconds,
                )
            except (TimeoutError, urllib.error.URLError) as error:
                last_error = error
                if attempt == self.max_retries:
                    raise
        raise RuntimeError("unreachable retry state") from last_error

    @staticmethod
    def _response_text(response: dict[str, Any]) -> str:
        serialized = json.dumps(response, separators=(",", ":"))
        if len(serialized.encode()) > 65_536:
            raise ValueError("provider response exceeded 65536 bytes")
        text = response["candidates"][0]["content"]["parts"][0]["text"]
        if not isinstance(text, str) or len(text) > 32_000:
            raise ValueError("provider text response invalid or oversized")
        return text

    def _assistant_unavailable(self, state: ProviderState) -> AssistantResult:
        return AssistantResult(
            state=state,
            provider="gemma_via_gemini_api",
            model=self.model,
            disclosure=NO_SEND_DISCLOSURE
            if state == ProviderState.NOT_CONFIGURED
            else SENT_DISCLOSURE,
        )

    def _assistant_error(self) -> AssistantResult:
        return AssistantResult(
            state=ProviderState.ERROR,
            error=ProviderError(
                code="provider_error",
                message="The provider returned an invalid or uncited response.",
                retryable=False,
            ),
            provider="gemma_via_gemini_api",
            model=self.model,
            disclosure=SENT_DISCLOSURE,
        )

    def _extraction_unavailable(self, state: ProviderState) -> ClaimExtractionResult:
        return ClaimExtractionResult(
            state=state,
            provider="gemma_via_gemini_api",
            model=self.model,
            disclosure=NO_SEND_DISCLOSURE
            if state == ProviderState.NOT_CONFIGURED
            else SENT_DISCLOSURE,
        )

    def _extraction_error(self) -> ClaimExtractionResult:
        return ClaimExtractionResult(
            state=ProviderState.ERROR,
            error=ProviderError(
                code="provider_error",
                message="The provider returned an invalid or uncited extraction.",
                retryable=False,
            ),
            provider="gemma_via_gemini_api",
            model=self.model,
            disclosure=SENT_DISCLOSURE,
        )
