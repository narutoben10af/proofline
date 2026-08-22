from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from proofline.config import Settings, get_settings
from proofline.contracts import (
    AnalysisRequest,
    AnalysisResponse,
    CreateSessionRequest,
    DeletionReceipt,
    HealthResponse,
    SessionStatus,
)
from proofline.providers import GemmaProvider
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
