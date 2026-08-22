from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from proofline.config import Settings
from proofline.source_library import ProcessSessionRepository, SessionRepository

PERSISTENCE_BUCKET = "proofline-source-library"
ACCESS_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{20,4096}$")


class PersistenceError(Exception):
    """Stable persistence failure that never includes a remote response body."""

    def __init__(self, reason_code: str, status_code: int = 500) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.status_code = status_code


@dataclass(frozen=True)
class HttpResult:
    status_code: int
    body: bytes = b""


class HttpTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> HttpResult: ...


class UrllibHttpTransport:
    """Small synchronous transport; callers must keep it off the event loop."""

    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self.timeout_seconds = timeout_seconds

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> HttpResult:
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                return HttpResult(response.status, response.read())
        except HTTPError as error:
            return HttpResult(error.code, error.read())
        except (TimeoutError, URLError) as error:
            raise PersistenceError("SUPABASE_UNAVAILABLE", 503) from error


@dataclass(frozen=True)
class PersistenceSelection:
    backend: Literal["process-local", "supabase"]
    configured: bool
    activated: bool
    reason_code: str


@dataclass(frozen=True)
class SupabaseUserContext:
    owner_id: UUID
    access_token: str

    def __post_init__(self) -> None:
        if not self.access_token or self.access_token.startswith(("sb_publishable_", "sb_secret_")):
            raise PersistenceError("USER_ACCESS_TOKEN_INVALID", 401)


@dataclass(frozen=True)
class SupabaseConfiguration:
    project_url: str
    publishable_key: str
    bucket: str = PERSISTENCE_BUCKET

    def __post_init__(self) -> None:
        parsed = urlparse(self.project_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not parsed.hostname.endswith(".supabase.co")
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise PersistenceError("SUPABASE_URL_INVALID")
        if not self.publishable_key.startswith("sb_publishable_"):
            raise PersistenceError("SUPABASE_PUBLISHABLE_KEY_INVALID")
        if self.bucket != PERSISTENCE_BUCKET:
            raise PersistenceError("SUPABASE_BUCKET_INVALID")

    @property
    def base_url(self) -> str:
        return self.project_url.rstrip("/")


def persistence_selection(settings: Settings) -> PersistenceSelection:
    """Report configuration truth without activating or contacting Supabase."""

    if settings.source_library_persistence_backend == "process-local":
        return PersistenceSelection(
            backend="process-local",
            configured=True,
            activated=True,
            reason_code="PROCESS_LOCAL_FALLBACK_ACTIVE",
        )
    configured = bool(
        settings.supabase_url and settings.supabase_publishable_key and settings.supabase_secret_key
    )
    return PersistenceSelection(
        backend="supabase",
        configured=configured,
        activated=configured,
        reason_code=(
            "SUPABASE_AUTHENTICATED_PIPELINE_ACTIVE"
            if configured
            else "SUPABASE_NOT_CONFIGURED"
        ),
    )


def source_session_repository(
    settings: Settings,
    *,
    tombstone_ttl: timedelta = timedelta(hours=2),
    max_tombstones: int = 1_000,
) -> SessionRepository:
    """Select the repository used by the existing Source Library boundary.

    The current cookie-capability sessions use opaque ``src-*`` identifiers and
    have no authenticated Supabase owner. They therefore remain process-local.
    Selecting Supabase explicitly fails closed instead of silently writing a
    second, ownerless representation or duplicating upload normalization.
    """

    selection = persistence_selection(settings)
    if selection.backend == "process-local":
        return ProcessSessionRepository(
            tombstone_ttl=tombstone_ttl,
            max_tombstones=max_tombstones,
        )
    raise PersistenceError("AUTHENTICATED_API_REQUIRED", 503)


class AnalysisPersistenceRepository(Protocol):
    def create_session(self) -> dict[str, Any]: ...

    def get_session(self, session_id: UUID) -> dict[str, Any] | None: ...
    def touch_session(self, session_id: UUID) -> dict[str, Any]: ...
    def list_documents(self, session_id: UUID) -> list[dict[str, Any]]: ...
    def register_document(self, document: dict[str, Any]) -> dict[str, Any]: ...
    def request_delete(self, session_id: UUID) -> dict[str, Any]: ...


class PrivateObjectStore(Protocol):
    def upload(self, object_path: str, content: bytes, canonical_type: str) -> None: ...
    def download(self, object_path: str) -> bytes: ...
    def delete(self, object_path: str) -> bool: ...


class _SupabaseApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        bearer_token: str | None,
        transport: HttpTransport,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.bearer_token = bearer_token
        self.transport = transport

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        payload: Any | None = None,
        content_type: str = "application/json",
        prefer: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> HttpResult:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        headers = {"apikey": self.api_key, "Accept": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        if prefer:
            headers["Prefer"] = prefer
        if extra_headers:
            headers.update(extra_headers)
        body: bytes | None = None
        if payload is not None:
            if isinstance(payload, bytes):
                body = payload
            else:
                body = json.dumps(payload, separators=(",", ":"), default=_json_default).encode()
            headers["Content-Type"] = content_type
        result = self.transport.request(method, url, headers, body)
        if not 200 <= result.status_code < 300:
            if result.status_code in {401, 403, 404}:
                raise PersistenceError("SUPABASE_ACCESS_DENIED", result.status_code)
            if result.status_code == 409:
                raise PersistenceError("SUPABASE_CONFLICT", 409)
            raise PersistenceError("SUPABASE_REQUEST_FAILED", 502)
        return result


def _json_default(value: object) -> str:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"unsupported JSON type: {type(value).__name__}")


def _json_rows(result: HttpResult) -> list[dict[str, Any]]:
    try:
        value = json.loads(result.body or b"[]")
    except json.JSONDecodeError as error:
        raise PersistenceError("SUPABASE_RESPONSE_INVALID", 502) from error
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise PersistenceError("SUPABASE_RESPONSE_INVALID", 502)
    return value


def _json_single(result: HttpResult) -> dict[str, Any]:
    try:
        value = json.loads(result.body or b"null")
    except json.JSONDecodeError as error:
        raise PersistenceError("SUPABASE_RESPONSE_INVALID", 502) from error
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
        return value[0]
    if isinstance(value, dict):
        return value
    raise PersistenceError("SUPABASE_RESPONSE_INVALID", 502)


class SupabaseAnalysisRepository:
    """User-JWT PostgREST adapter. RLS remains the authorization boundary."""

    def __init__(
        self,
        configuration: SupabaseConfiguration,
        user: SupabaseUserContext,
        *,
        transport: HttpTransport | None = None,
    ) -> None:
        self.configuration = configuration
        self.user = user
        self.client = _SupabaseApiClient(
            base_url=configuration.base_url,
            api_key=configuration.publishable_key,
            bearer_token=user.access_token,
            transport=transport or UrllibHttpTransport(),
        )

    def create_session(self) -> dict[str, Any]:
        return _json_single(
            self.client.request("POST", "/rest/v1/rpc/create_analysis_session", payload={})
        )

    def get_session(self, session_id: UUID) -> dict[str, Any] | None:
        rows = _json_rows(
            self.client.request(
                "GET",
                "/rest/v1/analysis_sessions",
                query={
                    "select": "*",
                    "id": f"eq.{session_id}",
                    "owner_id": f"eq.{self.user.owner_id}",
                    "limit": "1",
                },
            )
        )
        return rows[0] if rows else None

    def touch_session(self, session_id: UUID) -> dict[str, Any]:
        return _json_single(
            self.client.request(
                "POST",
                "/rest/v1/rpc/touch_analysis_session",
                payload={"target_session_id": session_id},
            )
        )

    def list_documents(self, session_id: UUID) -> list[dict[str, Any]]:
        return _json_rows(
            self.client.request(
                "GET",
                "/rest/v1/documents",
                query={
                    "select": "*",
                    "session_id": f"eq.{session_id}",
                    "owner_id": f"eq.{self.user.owner_id}",
                    "order": "uploaded_at.asc",
                },
            )
        )

    def register_document(self, document: dict[str, Any]) -> dict[str, Any]:
        server_fields = {
            "owner_id",
            "storage_object_path",
            "validation_status",
            "validated_at",
            "uploaded_at",
            "expires_at",
        }
        allowed_fields = {
            "id",
            "session_id",
            "role",
            "display_name",
            "canonical_type",
            "byte_count",
            "content_sha256",
        }
        if server_fields.intersection(document) or set(document) != allowed_fields:
            raise PersistenceError("DOCUMENT_SERVER_FIELDS_FORBIDDEN")
        payload = {
            "target_session_id": UUID(str(document["session_id"])),
            "target_document_id": UUID(str(document["id"])),
            "document_role": document["role"],
            "document_display_name": document["display_name"],
            "document_canonical_type": document["canonical_type"],
            "document_byte_count": document["byte_count"],
            "document_content_sha256": document["content_sha256"],
        }
        return _json_single(
            self.client.request("POST", "/rest/v1/rpc/register_source_document", payload=payload)
        )

    def request_delete(self, session_id: UUID) -> dict[str, Any]:
        return _json_single(
            self.client.request(
                "POST",
                "/rest/v1/rpc/request_analysis_session_deletion",
                payload={"target_session_id": session_id},
            )
        )


class SupabasePrivateObjectStore:
    def __init__(
        self,
        configuration: SupabaseConfiguration,
        user: SupabaseUserContext,
        *,
        transport: HttpTransport | None = None,
    ) -> None:
        self.configuration = configuration
        self.user = user
        self.client = _SupabaseApiClient(
            base_url=configuration.base_url,
            api_key=configuration.publishable_key,
            bearer_token=user.access_token,
            transport=transport or UrllibHttpTransport(),
        )

    def _assert_owner_path(self, path: str) -> None:
        parts = path.split("/")
        if len(parts) != 3 or parts[0] != str(self.user.owner_id):
            raise PersistenceError("STORAGE_OBJECT_PATH_INVALID")
        try:
            UUID(parts[1])
            UUID(parts[2])
        except ValueError as error:
            raise PersistenceError("STORAGE_OBJECT_PATH_INVALID") from error

    def upload(self, object_path: str, content: bytes, canonical_type: str) -> None:
        self._assert_owner_path(object_path)
        self.client.request(
            "POST",
            f"/storage/v1/object/{self.configuration.bucket}/{quote(object_path, safe='/')}",
            payload=content,
            content_type=canonical_type,
            extra_headers={"x-upsert": "false"},
        )

    def download(self, object_path: str) -> bytes:
        self._assert_owner_path(object_path)
        return self.client.request(
            "GET",
            f"/storage/v1/object/authenticated/{self.configuration.bucket}/"
            f"{quote(object_path, safe='/')}",
        ).body

    def delete(self, object_path: str) -> bool:
        self._assert_owner_path(object_path)
        result = self.client.request(
            "DELETE",
            f"/storage/v1/object/{self.configuration.bucket}/{quote(object_path, safe='/')}",
        )
        return result.status_code in {200, 204}


class SupabaseServerMaintenanceRepository:
    """Backend-only lifecycle seam. A secret key bypasses RLS and must never reach a browser."""

    def __init__(
        self,
        configuration: SupabaseConfiguration,
        secret_key: str,
        *,
        transport: HttpTransport | None = None,
    ) -> None:
        if not secret_key.startswith("sb_secret_"):
            raise PersistenceError("SUPABASE_SECRET_KEY_INVALID")
        self.client = _SupabaseApiClient(
            base_url=configuration.base_url,
            api_key=secret_key,
            bearer_token=None,
            transport=transport or UrllibHttpTransport(),
        )

    def mark_provider_transfer_started(
        self, *, session_id: UUID, owner_id: UUID, started_at: datetime
    ) -> None:
        rows = _json_rows(
            self.client.request(
                "PATCH",
                "/rest/v1/analysis_sessions",
                query={"id": f"eq.{session_id}", "owner_id": f"eq.{owner_id}"},
                payload={
                    "provider_sent": True,
                    "provider_sent_at": started_at,
                    "updated_at": started_at,
                },
                prefer="return=representation",
            )
        )
        if len(rows) != 1:
            raise PersistenceError("SUPABASE_SESSION_NOT_FOUND", 404)

    def mark_document_validation(
        self,
        *,
        document_id: UUID,
        owner_id: UUID,
        status: Literal["Ready", "Needs attention"],
        canonical_type: str,
        byte_count: int,
        content_sha256: str,
        validated_at: datetime,
    ) -> dict[str, Any]:
        if status not in {"Ready", "Needs attention"}:
            raise PersistenceError("DOCUMENT_VALIDATION_STATUS_INVALID")
        if canonical_type not in {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }:
            raise PersistenceError("DOCUMENT_CANONICAL_TYPE_INVALID")
        if not 1 <= byte_count <= 20 * 1024 * 1024:
            raise PersistenceError("DOCUMENT_BYTE_COUNT_INVALID")
        if len(content_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in content_sha256
        ):
            raise PersistenceError("DOCUMENT_DIGEST_INVALID")
        rows = _json_rows(
            self.client.request(
                "PATCH",
                "/rest/v1/documents",
                query={
                    "id": f"eq.{document_id}",
                    "owner_id": f"eq.{owner_id}",
                    "validation_status": "eq.Checking",
                },
                payload={
                    "validation_status": status,
                    "canonical_type": canonical_type,
                    "byte_count": byte_count,
                    "content_sha256": content_sha256,
                    "validated_at": validated_at,
                },
                prefer="return=representation",
            )
        )
        if len(rows) != 1:
            raise PersistenceError("SUPABASE_DOCUMENT_NOT_CHECKING", 409)
        return rows[0]

    def discard_document(self, *, document_id: UUID, owner_id: UUID) -> None:
        self.client.request(
            "DELETE",
            "/rest/v1/documents",
            query={"id": f"eq.{document_id}", "owner_id": f"eq.{owner_id}"},
        )

    def persist_completed_analysis(
        self,
        *,
        session_id: UUID,
        owner_id: UUID,
        response: dict[str, Any],
        response_sha256: str,
        source_spans: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if len(response_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in response_sha256
        ):
            raise PersistenceError("ANALYSIS_DIGEST_INVALID")
        return _json_single(
            self.client.request(
                "POST",
                "/rest/v1/rpc/persist_completed_analysis",
                payload={
                    "target_session_id": session_id,
                    "target_owner_id": owner_id,
                    "analysis_response": response,
                    "analysis_response_sha256": response_sha256,
                    "normalized_source_spans": source_spans,
                    "normalized_evidence": evidence,
                },
            )
        )

    def list_expired_sessions(self, *, now: datetime, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500:
            raise PersistenceError("SUPABASE_MAINTENANCE_LIMIT_INVALID")
        instant = now.astimezone(UTC).isoformat()
        return _json_rows(
            self.client.request(
                "GET",
                "/rest/v1/analysis_sessions",
                query={
                    "select": "*",
                    "state": "in.(OPEN,PROCESSING)",
                    "or": f"(idle_expires_at.lte.{instant},absolute_expires_at.lte.{instant})",
                    "order": "absolute_expires_at.asc",
                    "limit": str(limit),
                },
            )
        )

    def write_deletion_receipt(self, receipt: dict[str, Any]) -> dict[str, Any]:
        completed_at = datetime.fromisoformat(str(receipt["completed_at"]).replace("Z", "+00:00"))
        retained_until = datetime.fromisoformat(
            str(receipt["retained_until"]).replace("Z", "+00:00")
        )
        if retained_until <= completed_at or retained_until - completed_at > timedelta(hours=2):
            raise PersistenceError("DELETION_RECEIPT_RETENTION_INVALID")
        if not isinstance(receipt.get("provider_sent"), bool):
            raise PersistenceError("DELETION_RECEIPT_PROVIDER_STATE_INVALID")
        rows = _json_rows(
            self.client.request(
                "POST",
                "/rest/v1/deletion_receipts",
                payload=receipt,
                prefer="return=representation",
            )
        )
        if len(rows) != 1:
            raise PersistenceError("SUPABASE_RESPONSE_INVALID", 502)
        return rows[0]

    def prune_deletion_receipts(self, *, now: datetime) -> None:
        self.client.request(
            "DELETE",
            "/rest/v1/deletion_receipts",
            query={"retained_until": f"lte.{now.astimezone(UTC).isoformat()}"},
        )


def object_path(owner_id: UUID, session_id: UUID, document_id: UUID) -> str:
    return f"{owner_id}/{session_id}/{document_id}"


def configured_user_adapters(
    settings: Settings,
    user: SupabaseUserContext,
    *,
    transport: HttpTransport | None = None,
) -> tuple[SupabaseAnalysisRepository, SupabasePrivateObjectStore]:
    """Explicit future activation seam; the current API never calls this automatically."""

    selection = persistence_selection(settings)
    if selection.backend != "supabase" or not selection.configured:
        raise PersistenceError("SUPABASE_NOT_CONFIGURED", 503)
    configuration = SupabaseConfiguration(
        project_url=str(settings.supabase_url),
        publishable_key=settings.supabase_publishable_key.get_secret_value(),
        bucket=settings.supabase_storage_bucket,
    )
    return (
        SupabaseAnalysisRepository(configuration, user, transport=transport),
        SupabasePrivateObjectStore(configuration, user, transport=transport),
    )


def verified_user_context(
    settings: Settings,
    access_token: str,
    *,
    transport: HttpTransport | None = None,
) -> SupabaseUserContext:
    """Verify a bearer token at Supabase Auth; never trust browser JWT claims directly."""

    if not ACCESS_TOKEN_PATTERN.fullmatch(access_token):
        raise PersistenceError("USER_ACCESS_TOKEN_INVALID", 401)
    selection = persistence_selection(settings)
    if selection.backend != "supabase" or not selection.configured:
        raise PersistenceError("SUPABASE_NOT_CONFIGURED", 503)
    configuration = SupabaseConfiguration(
        project_url=str(settings.supabase_url),
        publishable_key=settings.supabase_publishable_key.get_secret_value(),
        bucket=settings.supabase_storage_bucket,
    )
    client = _SupabaseApiClient(
        base_url=configuration.base_url,
        api_key=configuration.publishable_key,
        bearer_token=access_token,
        transport=transport or UrllibHttpTransport(),
    )
    try:
        result = client.request("GET", "/auth/v1/user")
        payload = json.loads(result.body)
        owner_id = UUID(str(payload["id"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise PersistenceError("USER_ACCESS_TOKEN_INVALID", 401) from error
    return SupabaseUserContext(owner_id=owner_id, access_token=access_token)


def configured_server_maintenance(
    settings: Settings,
    *,
    transport: HttpTransport | None = None,
) -> SupabaseServerMaintenanceRepository:
    selection = persistence_selection(settings)
    if selection.backend != "supabase" or not selection.configured:
        raise PersistenceError("SUPABASE_NOT_CONFIGURED", 503)
    configuration = SupabaseConfiguration(
        project_url=str(settings.supabase_url),
        publishable_key=settings.supabase_publishable_key.get_secret_value(),
        bucket=settings.supabase_storage_bucket,
    )
    return SupabaseServerMaintenanceRepository(
        configuration,
        settings.supabase_secret_key.get_secret_value(),
        transport=transport,
    )
