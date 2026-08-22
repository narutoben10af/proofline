import asyncio
import hashlib
import hmac
import json
from contextlib import asynccontextmanager, suppress
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from proofline.config import Settings, get_settings
from proofline.contracts import (
    AnalysisRequest,
    AnalysisResponse,
    CreateSessionRequest,
    DeletionReceipt,
    HealthResponse,
    SessionStatus,
    SourceDeletionReceipt,
    SourceFileMetadata,
    SourceSessionCreated,
    SourceSessionStatus,
)
from proofline.economic_context import get_company_lens
from proofline.mcp_server import build_mcp_server, mcp_http_gateway
from proofline.providers import GemmaProvider
from proofline.providers.contracts import (
    AssistantRequest,
    AssistantResult,
    ChartRequest,
    ChartResult,
    ClaimExtractionRequest,
    ClaimExtractionResult,
    ProviderConnectionTest,
    ProviderStatus,
)
from proofline.report_contracts import CompanyLens, ReportRenderBundle, canonical_sha256
from proofline.reports import (
    attachment_filename,
    content_sha256,
    render_evidence_json,
    render_pdf,
)
from proofline.service import analyze
from proofline.sessions import SessionStore
from proofline.source_library import LibraryError, SessionRecord, SourceLibraryStore, Tombstone
from proofline.upload_analysis import UploadAnalysisError, analyze_uploaded_evidence

CAPABILITY_COOKIE = "__Host-proofline_capability"
FIXTURE_ROOT = Path(__file__).parents[2] / "fixtures" / "financial"
FIXTURE_HASHES = {
    "apple-fy2025": "e963123f156b1a33f988074ec8d08f7a98b2d1180684ac6c801f09cb4facc9bd",
    "pcg-fy2025": "914daaa1923613b8942efe4f289160c54088ff1720ba223d93cc4d99aa3110f3",
}
FIXTURE_FILES = {
    "apple-fy2025": ("expected_metrics.json", "Official source fixture"),
    "pcg-fy2025": ("hero_cases.json", "Project-derived fixture"),
}


class RequestSizeLimitMiddleware:
    def __init__(self, app, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/sessions"):
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", ()))
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    await JSONResponse({"reason_code": "REQUEST_TOO_LARGE"}, status_code=413)(
                        scope, receive, send
                    )
                    return
            except ValueError:
                await JSONResponse({"reason_code": "CONTENT_LENGTH_INVALID"}, status_code=400)(
                    scope, receive, send
                )
                return
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise LibraryError("REQUEST_TOO_LARGE", 413)
            return message

        try:
            await self.app(scope, bounded_receive, send)
        except LibraryError as error:
            await JSONResponse({"reason_code": error.reason_code}, status_code=error.status_code)(
                scope, receive, send
            )


class SessionNoStoreMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/sessions"):
            await self.app(scope, receive, send)
            return

        async def no_store_send(message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", ()))
                headers.append((b"cache-control", b"no-store, private"))
                headers.append((b"pragma", b"no-cache"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, no_store_send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.analysis_provider = GemmaProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemma_model,
        timeout_seconds=settings.gemini_request_timeout_seconds,
        max_retries=settings.gemini_max_retries,
    )
    source_store = SourceLibraryStore(
        root=settings.source_library_root,
        idle_ttl=timedelta(minutes=settings.source_library_idle_minutes),
        absolute_ttl=timedelta(minutes=settings.source_library_absolute_minutes),
    )
    source_store.startup_cleanup()
    app.state.source_store = source_store
    stop_cleanup = asyncio.Event()

    async def periodic_cleanup() -> None:
        while not stop_cleanup.is_set():
            try:
                await asyncio.wait_for(
                    stop_cleanup.wait(), timeout=settings.source_library_cleanup_seconds
                )
            except TimeoutError:
                source_store.cleanup_expired()

    cleanup_task = asyncio.create_task(periodic_cleanup())
    mcp_http_app = build_mcp_server().streamable_http_app()
    mcp_http_gateway.active_app = mcp_http_app
    try:
        async with mcp_http_app.router.lifespan_context(mcp_http_app):
            yield
    finally:
        mcp_http_gateway.active_app = None
        stop_cleanup.set()
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task
        source_store.shutdown_cleanup()


app = FastAPI(
    title="Proofline API",
    version="1.0.0",
    description="Contract-first deterministic financial claim analysis prototype.",
    lifespan=lifespan,
)
app.add_middleware(
    RequestSizeLimitMiddleware,
    max_bytes=get_settings().source_library_max_request_bytes,
)
app.add_middleware(SessionNoStoreMiddleware)
session_store = SessionStore()


@app.exception_handler(LibraryError)
async def library_error_handler(_request: Request, error: LibraryError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"reason_code": error.reason_code},
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    if request.url.path.startswith("/api/sessions"):
        return JSONResponse(status_code=422, content={"reason_code": "REQUEST_INVALID"})
    return await request_validation_exception_handler(request, error)


def source_store(request: Request) -> SourceLibraryStore:
    return request.app.state.source_store


def require_same_origin(request: Request) -> None:
    settings = get_settings()
    allowed = {item.strip() for item in settings.source_library_allowed_origins.split(",")}
    origin = request.headers.get("origin")
    fetch_site = request.headers.get("sec-fetch-site")
    if origin not in allowed or fetch_site not in {None, "same-origin"}:
        raise LibraryError("ORIGIN_NOT_ALLOWED", 403)


def authorized_session(
    request: Request,
    session_id: str,
    *,
    mutate: bool = False,
) -> SessionRecord:
    if mutate:
        require_same_origin(request)
    authorized = source_store(request).authorize(
        session_id,
        request.cookies.get(CAPABILITY_COOKIE),
        csrf_token=request.headers.get("x-proofline-csrf"),
        require_csrf=mutate,
    )
    if isinstance(authorized, Tombstone):
        raise LibraryError("SESSION_GONE", 410)
    return authorized


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(
        model_provider=settings.model_provider,
        model_configured=bool(settings.gemini_api_key),
    )


@app.get("/api/v1/providers/model", response_model=ProviderStatus, tags=["providers"])
def model_provider_status() -> ProviderStatus:
    return app.state.analysis_provider.status()


@app.post("/api/v1/providers/model/test", response_model=ProviderConnectionTest, tags=["providers"])
async def test_model_provider_connection() -> ProviderConnectionTest:
    return await app.state.analysis_provider.test_connection()


@app.post("/api/v1/assistant", response_model=AssistantResult, tags=["providers"])
async def create_assistant_response(request: AssistantRequest) -> AssistantResult:
    return await app.state.analysis_provider.assist(request)


@app.post("/api/v1/assistant/chart", response_model=ChartResult, tags=["providers"])
async def create_chart_response(request: ChartRequest) -> ChartResult:
    return await app.state.analysis_provider.propose_chart(request)


@app.post("/api/v1/extractions", response_model=ClaimExtractionResult, tags=["providers"])
async def create_claim_extraction(request: ClaimExtractionRequest) -> ClaimExtractionResult:
    return await app.state.analysis_provider.extract_claims(request)


@app.get("/api/public-demo/{fixture_id}", tags=["public-demo"])
def public_demo(fixture_id: str) -> dict:
    fixture = FIXTURE_FILES.get(fixture_id)
    expected_hash = FIXTURE_HASHES.get(fixture_id)
    if fixture is None or expected_hash is None:
        raise LibraryError("FIXTURE_NOT_FOUND", 404)
    filename, source_label = fixture
    path = FIXTURE_ROOT / filename
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if not hmac_compare(actual_hash, expected_hash):
        raise LibraryError("FIXTURE_HASH_MISMATCH", 409)
    return {
        "fixture_id": fixture_id,
        "source_label": source_label,
        "fixture_hash": actual_hash,
        "verified_cached_output": True,
        "provider_required": False,
        "data": json.loads(path.read_text(encoding="utf-8")),
    }


def hmac_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)


@app.post(
    "/api/sessions",
    response_model=SourceSessionCreated,
    status_code=201,
    tags=["source-library"],
)
def create_source_session(request: Request, response: Response) -> SourceSessionCreated:
    require_same_origin(request)
    created, capability = source_store(request).create()
    response.set_cookie(
        CAPABILITY_COOKIE,
        capability,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
        max_age=get_settings().source_library_absolute_minutes * 60,
    )
    return created


@app.get(
    "/api/sessions/{session_id}",
    response_model=SourceSessionStatus,
    tags=["source-library"],
)
def get_source_session(request: Request, session_id: str) -> SourceSessionStatus:
    record = authorized_session(request, session_id)
    return source_store(request).status(record)


@app.get(
    "/api/sessions/{session_id}/files",
    response_model=tuple[SourceFileMetadata, ...],
    tags=["source-library"],
)
def list_source_files(request: Request, session_id: str) -> tuple[SourceFileMetadata, ...]:
    record = authorized_session(request, session_id)
    return source_store(request).list_files(record)


@app.post(
    "/api/sessions/{session_id}/files",
    response_model=SourceFileMetadata,
    status_code=201,
    tags=["source-library"],
)
async def upload_source_file(
    request: Request,
    session_id: str,
    role: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> SourceFileMetadata:
    record = authorized_session(request, session_id, mutate=True)
    return await source_store(request).upload(record, role, file)


@app.get(
    "/api/sessions/{session_id}/files/{file_id}",
    response_model=SourceFileMetadata,
    tags=["source-library"],
)
def get_source_file_metadata(request: Request, session_id: str, file_id: str) -> SourceFileMetadata:
    record = authorized_session(request, session_id)
    return source_store(request).get_file(record, file_id).metadata


@app.get(
    "/api/sessions/{session_id}/files/{file_id}/content",
    response_class=FileResponse,
    tags=["source-library"],
)
def get_source_file_content(
    request: Request,
    session_id: str,
    file_id: str,
    disposition: str = "attachment",
) -> FileResponse:
    if disposition not in {"inline", "attachment"}:
        raise LibraryError("DISPOSITION_INVALID")
    record = authorized_session(request, session_id)
    stored = source_store(request).get_file(record, file_id)
    if disposition == "inline" and stored.metadata.role != "report_pdf":
        raise LibraryError("PREVIEW_NOT_AVAILABLE", 409)
    return FileResponse(
        stored.path,
        media_type=stored.metadata.canonical_type,
        filename=stored.metadata.display_name,
        content_disposition_type=disposition,
    )


@app.delete(
    "/api/sessions/{session_id}/files/{file_id}",
    response_model=SourceFileMetadata,
    tags=["source-library"],
)
def remove_source_file(request: Request, session_id: str, file_id: str) -> SourceFileMetadata:
    record = authorized_session(request, session_id, mutate=True)
    return source_store(request).remove_file(record, file_id)


@app.post(
    "/api/sessions/{session_id}/start",
    response_model=SourceSessionStatus,
    tags=["source-library"],
)
def start_source_review(request: Request, session_id: str) -> SourceSessionStatus:
    record = authorized_session(request, session_id, mutate=True)
    return source_store(request).start(record)


@app.post(
    "/api/sessions/{session_id}/analysis",
    response_model=AnalysisResponse,
    tags=["source-library", "analysis"],
)
def analyze_source_session(request: Request, session_id: str) -> AnalysisResponse:
    """Analyze one authorized, validated PDF/XLSX pair without consulting demo fixtures."""

    record = authorized_session(request, session_id, mutate=True)
    metadata = source_store(request).list_files(record)
    pdf_metadata = next((item for item in metadata if item.role == "report_pdf"), None)
    workbook_metadata = next((item for item in metadata if item.role == "workbook"), None)
    if pdf_metadata is None or workbook_metadata is None:
        raise LibraryError("REQUIRED_FILES_NOT_READY", 409)
    pdf = source_store(request).get_file(record, pdf_metadata.file_id)
    workbook = source_store(request).get_file(record, workbook_metadata.file_id)
    sanitization = getattr(pdf, "sanitization", None)
    pdf_warnings = (sanitization.warning,) if sanitization is not None else ()
    try:
        return analyze_uploaded_evidence(
            pdf_content=pdf.path.read_bytes(),
            workbook_content=workbook.path.read_bytes(),
            session_id=record.session_id,
            pdf_file_id=pdf.metadata.file_id,
            workbook_file_id=workbook.metadata.file_id,
            retrieved_at=max(pdf.metadata.uploaded_at, workbook.metadata.uploaded_at),
            pdf_extraction_warnings=pdf_warnings,
        )
    except UploadAnalysisError as error:
        raise LibraryError(error.code, 422) from error


@app.delete(
    "/api/sessions/{session_id}",
    response_model=SourceDeletionReceipt,
    tags=["source-library"],
)
def delete_source_session(request: Request, session_id: str) -> SourceDeletionReceipt:
    require_same_origin(request)
    receipt = source_store(request).delete(
        session_id,
        request.cookies.get(CAPABILITY_COOKIE),
        request.headers.get("x-proofline-csrf"),
    )
    return receipt


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


# Keep the existing API routes ahead of this catch-all mount. The mounted MCP app owns /mcp.
app.mount("/", mcp_http_gateway)
