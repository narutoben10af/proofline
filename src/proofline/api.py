from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response

from proofline.config import Settings, get_settings
from proofline.contracts import (
    AnalysisRequest,
    AnalysisResponse,
    CreateSessionRequest,
    DeletionReceipt,
    HealthResponse,
    SessionStatus,
)
from proofline.economic_context import get_company_lens
from proofline.providers import GemmaProvider
from proofline.report_contracts import CompanyLens, ReportRenderBundle, canonical_sha256
from proofline.reports import (
    attachment_filename,
    content_sha256,
    render_evidence_json,
    render_pdf,
)
from proofline.service import analyze
from proofline.sessions import SessionStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.claim_provider = GemmaProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemma_model,
        timeout_seconds=settings.gemini_request_timeout_seconds,
        max_retries=settings.gemini_max_retries,
    )
    yield


app = FastAPI(
    title="Proofline API",
    version="1.0.0",
    description="Contract-first deterministic financial claim analysis prototype.",
    lifespan=lifespan,
)
session_store = SessionStore()


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(
        model_provider=settings.model_provider,
        model_configured=bool(settings.gemini_api_key),
    )


@app.post("/api/v1/analyses", response_model=AnalysisResponse, tags=["analysis"])
def create_analysis(request: AnalysisRequest) -> AnalysisResponse:
    try:
        return analyze(request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get(
    "/api/v1/company-lenses/{company_id}",
    response_model=CompanyLens,
    tags=["reporting"],
)
def company_lens(company_id: str) -> CompanyLens:
    lens = get_company_lens(company_id)
    if lens is None:
        raise HTTPException(status_code=404, detail="company lens not found")
    return lens


@app.post(
    "/api/v1/reports/pdf",
    response_class=Response,
    responses={
        200: {
            "content": {
                "application/pdf": {},
                "application/json": {},
            },
            "description": "Deterministic PDF report or reviewed JSON evidence export.",
        }
    },
    tags=["reporting"],
)
def render_report(
    bundle: ReportRenderBundle,
    output: Literal["pdf", "evidence-json"] = "pdf",
) -> Response:
    if output == "evidence-json":
        content = render_evidence_json(bundle)
        media_type = "application/json"
        filename = attachment_filename(bundle, "json")
    else:
        content = render_pdf(bundle)
        media_type = "application/pdf"
        filename = attachment_filename(bundle, "pdf")
    digest = content_sha256(content)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{filename}"',
            "ETag": f'"{digest}"',
            "X-Content-SHA256": digest,
            "X-Report-Bundle-SHA256": canonical_sha256(bundle),
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.post("/api/v1/sessions", response_model=SessionStatus, status_code=201, tags=["sessions"])
def create_session(request: CreateSessionRequest) -> SessionStatus:
    return session_store.create(request)


@app.get("/api/v1/sessions/{session_id}", response_model=SessionStatus, tags=["sessions"])
def get_session(session_id: str) -> SessionStatus:
    status = session_store.get(session_id)
    if status is None:
        raise HTTPException(status_code=404, detail="session not found")
    return status


@app.delete("/api/v1/sessions/{session_id}", response_model=DeletionReceipt, tags=["sessions"])
def delete_session(session_id: str) -> DeletionReceipt:
    receipt = session_store.delete(session_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="session not found")
    return receipt
