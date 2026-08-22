from __future__ import annotations

import hashlib
import json
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import UploadFile

from proofline.config import Settings
from proofline.contracts import AnalysisResponse, FrozenModel
from proofline.parsing.base import OcrAdapter
from proofline.source_library import (
    PDF_MIME,
    XLSX_MIME,
    LibraryError,
    ValidationService,
)
from proofline.supabase_persistence import (
    PersistenceError,
    SupabaseAnalysisRepository,
    SupabasePrivateObjectStore,
    SupabaseServerMaintenanceRepository,
    SupabaseUserContext,
    configured_server_maintenance,
    configured_user_adapters,
    object_path,
    verified_user_context,
)
from proofline.upload_analysis import UploadAnalysisError, analyze_uploaded_evidence

BEARER_PATTERN = re.compile(r"^Bearer ([A-Za-z0-9._~-]{20,4096})$")


class AuthenticatedSessionCreated(FrozenModel):
    session_id: UUID
    state: Literal["OPEN"]
    created_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    persistence: Literal["supabase-private"] = "supabase-private"


class AuthenticatedSourceFile(FrozenModel):
    file_id: UUID
    session_id: UUID
    role: Literal["report_pdf", "workbook"]
    display_name: str
    canonical_type: str
    byte_count: int
    content_sha256: str
    validation_status: Literal["Ready"] = "Ready"
    uploaded_at: datetime
    sanitization_warning: str | None = None


def bearer_access_token(authorization: str | None) -> str:
    match = BEARER_PATTERN.fullmatch(authorization or "")
    if match is None:
        raise LibraryError("AUTH_REQUIRED", 401)
    return match.group(1)


def authenticated_adapters(
    settings: Settings,
    authorization: str | None,
) -> tuple[
    SupabaseUserContext,
    SupabaseAnalysisRepository,
    SupabasePrivateObjectStore,
    SupabaseServerMaintenanceRepository,
]:
    token = bearer_access_token(authorization)
    try:
        user = verified_user_context(settings, token)
        repository, objects = configured_user_adapters(settings, user)
        maintenance = configured_server_maintenance(settings)
    except PersistenceError as error:
        raise LibraryError(error.reason_code, error.status_code) from error
    return user, repository, objects, maintenance


def create_authenticated_session(
    repository: SupabaseAnalysisRepository,
) -> AuthenticatedSessionCreated:
    try:
        row = repository.create_session()
        return AuthenticatedSessionCreated(
            session_id=UUID(str(row["id"])),
            state=row["state"],
            created_at=row["created_at"],
            idle_expires_at=row["idle_expires_at"],
            absolute_expires_at=row["absolute_expires_at"],
        )
    except (KeyError, TypeError, ValueError, PersistenceError) as error:
        if isinstance(error, PersistenceError):
            raise LibraryError(error.reason_code, error.status_code) from error
        raise LibraryError("SUPABASE_RESPONSE_INVALID", 502) from error


async def read_validated_upload(
    upload: UploadFile,
    *,
    role: str,
    validator: ValidationService,
    max_pdf_bytes: int = 20 * 1024 * 1024,
    max_xlsx_bytes: int = 10 * 1024 * 1024,
) -> tuple[str, str, bytes, str | None]:
    if role not in {"report_pdf", "workbook"}:
        raise LibraryError("ROLE_INVALID")
    display_name = _safe_display_name(upload.filename)
    expected_suffix = ".pdf" if role == "report_pdf" else ".xlsx"
    expected_type = PDF_MIME if role == "report_pdf" else XLSX_MIME
    if Path(display_name).suffix.lower() != expected_suffix:
        raise LibraryError("FILE_EXTENSION_NOT_ALLOWED")
    if upload.content_type != expected_type:
        raise LibraryError("DECLARED_MIME_MISMATCH")
    limit = max_pdf_bytes if role == "report_pdf" else max_xlsx_bytes
    content = bytearray()
    try:
        while chunk := await upload.read(64 * 1024):
            content.extend(chunk)
            if len(content) > limit:
                raise LibraryError("FILE_TOO_LARGE", 413)
    finally:
        await upload.close()
    if not content:
        raise LibraryError("FILE_EMPTY")

    with tempfile.TemporaryDirectory(prefix="proofline-live-validation-") as directory:
        candidate = Path(directory) / "candidate.part"
        candidate.write_bytes(content)
        result = validator.validate(role, candidate)
        canonical = (
            result.derivative_path.read_bytes()
            if result is not None and result.derivative_path is not None
            else bytes(content)
        )
        warning = result.sanitization.warning if result and result.sanitization else None
    return display_name, expected_type, canonical, warning


def register_validated_upload(
    *,
    user: SupabaseUserContext,
    repository: SupabaseAnalysisRepository,
    objects: SupabasePrivateObjectStore,
    maintenance: SupabaseServerMaintenanceRepository,
    session_id: UUID,
    role: str,
    display_name: str,
    canonical_type: str,
    content: bytes,
    sanitization_warning: str | None,
) -> AuthenticatedSourceFile:
    document_id = uuid4()
    digest = hashlib.sha256(content).hexdigest()
    try:
        row = repository.register_document(
            {
                "id": str(document_id),
                "session_id": str(session_id),
                "role": role,
                "display_name": display_name,
                "canonical_type": canonical_type,
                "byte_count": len(content),
                "content_sha256": digest,
            }
        )
        path = object_path(user.owner_id, session_id, document_id)
        if row.get("storage_object_path") != path:
            raise PersistenceError("STORAGE_OBJECT_PATH_INVALID", 502)
        objects.upload(path, content, canonical_type)
        ready = maintenance.mark_document_validation(
            document_id=document_id,
            owner_id=user.owner_id,
            status="Ready",
            canonical_type=canonical_type,
            byte_count=len(content),
            content_sha256=digest,
            validated_at=datetime.now(UTC),
        )
        return AuthenticatedSourceFile(
            file_id=document_id,
            session_id=session_id,
            role=role,
            display_name=display_name,
            canonical_type=canonical_type,
            byte_count=len(content),
            content_sha256=digest,
            uploaded_at=ready["uploaded_at"],
            sanitization_warning=sanitization_warning,
        )
    except (KeyError, TypeError, ValueError, PersistenceError) as error:
        path = object_path(user.owner_id, session_id, document_id)
        try:
            objects.delete(path)
        except PersistenceError:
            pass
        try:
            maintenance.discard_document(document_id=document_id, owner_id=user.owner_id)
        except PersistenceError:
            pass
        if isinstance(error, PersistenceError):
            raise LibraryError(error.reason_code, error.status_code) from error
        raise LibraryError("SUPABASE_RESPONSE_INVALID", 502) from error


def analyze_authenticated_session(
    *,
    user: SupabaseUserContext,
    repository: SupabaseAnalysisRepository,
    objects: SupabasePrivateObjectStore,
    maintenance: SupabaseServerMaintenanceRepository,
    validator: ValidationService,
    session_id: UUID,
    ocr: OcrAdapter | None,
) -> AnalysisResponse:
    try:
        repository.touch_session(session_id)
        documents = repository.list_documents(session_id)
        by_role = {
            row.get("role"): row
            for row in documents
            if row.get("validation_status") == "Ready"
        }
        if set(by_role) != {"report_pdf", "workbook"} or len(documents) != 2:
            raise LibraryError("REQUIRED_FILES_NOT_READY", 409)
        pdf_row = by_role["report_pdf"]
        workbook_row = by_role["workbook"]
        pdf_content = objects.download(_owned_object_path(pdf_row, user, session_id))
        workbook_content = objects.download(_owned_object_path(workbook_row, user, session_id))
        _revalidate_stored_bytes(validator, "report_pdf", pdf_content)
        _revalidate_stored_bytes(validator, "workbook", workbook_content)
        response = analyze_uploaded_evidence(
            pdf_content=pdf_content,
            workbook_content=workbook_content,
            session_id=str(session_id),
            pdf_file_id=str(pdf_row["id"]),
            workbook_file_id=str(workbook_row["id"]),
            pdf_document_id=str(pdf_row["id"]),
            workbook_document_id=str(workbook_row["id"]),
            pdf_display_name=str(pdf_row["display_name"]),
            workbook_display_name=str(workbook_row["display_name"]),
            retrieved_at=max(
                datetime.fromisoformat(str(pdf_row["uploaded_at"]).replace("Z", "+00:00")),
                datetime.fromisoformat(str(workbook_row["uploaded_at"]).replace("Z", "+00:00")),
            ),
            ocr=ocr,
        )
        payload = response.model_dump(mode="json")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        spans, evidence = _persistence_rows(response)
        maintenance.persist_completed_analysis(
            session_id=session_id,
            owner_id=user.owner_id,
            response=payload,
            response_sha256=hashlib.sha256(encoded).hexdigest(),
            source_spans=spans,
            evidence=evidence,
        )
        return response
    except UploadAnalysisError as error:
        raise LibraryError(error.code, 422) from error
    except PersistenceError as error:
        raise LibraryError(error.reason_code, error.status_code) from error
    except (KeyError, TypeError, ValueError) as error:
        raise LibraryError("SUPABASE_RESPONSE_INVALID", 502) from error


def _safe_display_name(name: str | None) -> str:
    if not name or len(name) > 255:
        raise LibraryError("FILENAME_INVALID")
    if any(ord(character) < 32 for character in name) or "/" in name or "\\" in name:
        raise LibraryError("FILENAME_SUSPICIOUS")
    if name.startswith(".") or name.rstrip(". ") != name:
        raise LibraryError("FILENAME_SUSPICIOUS")
    return name


def _owned_object_path(
    row: dict[str, object], user: SupabaseUserContext, session_id: UUID
) -> str:
    document_id = UUID(str(row["id"]))
    expected = object_path(user.owner_id, session_id, document_id)
    if row.get("owner_id") != str(user.owner_id) or row.get("storage_object_path") != expected:
        raise PersistenceError("STORAGE_OBJECT_PATH_INVALID", 403)
    return expected


def _revalidate_stored_bytes(
    validator: ValidationService, role: str, content: bytes
) -> None:
    with tempfile.TemporaryDirectory(prefix="proofline-live-revalidation-") as directory:
        candidate = Path(directory) / "candidate.part"
        candidate.write_bytes(content)
        result = validator.validate(role, candidate)
        if result is not None and result.derivative_path is not None:
            raise LibraryError("STORED_DOCUMENT_CHANGED_AFTER_VALIDATION", 409)


def _persistence_rows(
    response: AnalysisResponse,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    documents = {document.id: document for document in response.documents}
    spans = {span.id: span for span in response.source_spans}
    span_rows: list[dict[str, object]] = []
    for span in response.source_spans:
        source = span.source
        text = source.quote if source.kind == "pdf" else source.display_value
        span_rows.append(
            {
                "document_id": span.document_version_id,
                "source_span_id": span.id,
                "page_number": source.page if source.kind == "pdf" else None,
                "sheet_name": source.sheet if source.kind == "spreadsheet" else None,
                "cell_range": source.cell if source.kind == "spreadsheet" else None,
                "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
            }
        )
    evidence_rows: list[dict[str, object]] = []
    for observation in response.observations:
        span = spans[observation.source_span_id]
        document = documents[span.document_version_id]
        evidence_rows.append(
            {
                "source_id": span.document_version_id,
                "source_span_id": span.id,
                "observation_id": observation.id,
                "issuer": document.issuer,
                "concept": observation.concept,
                "numeric_value": str(observation.numeric_value),
                "display_value": observation.display_value,
                "period_start": observation.period.start.isoformat()
                if observation.period.start
                else None,
                "period_end": observation.period.end.isoformat(),
                "duration_weeks": observation.period.duration_weeks,
                "unit": observation.unit,
                "currency": observation.currency,
            }
        )
    return span_rows, evidence_rows
