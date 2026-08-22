from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from proofline.config import Settings

PERSISTENCE_BUCKET = "proofline-source-library"


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
        activated=False,
        reason_code=(
            "SUPABASE_AUTH_INTEGRATION_REQUIRED" if configured else "SUPABASE_NOT_CONFIGURED"
        ),
    )


class AnalysisPersistenceRepository(Protocol):
    def create_session(
        self, *, now: datetime | None = None, idle_ttl: timedelta, absolute_ttl: timedelta
    ) -> dict[str, Any]: ...

    def get_session(self, session_id: UUID) -> dict[str, Any] | None: ...
    def list_documents(self, session_id: UUID) -> list[dict[str, Any]]: ...
    def upsert_document(self, document: dict[str, Any]) -> dict[str, Any]: ...
    def delete_session_metadata_after_objects(self, session_id: UUID) -> bool: ...


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
    ) -> HttpResult:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        headers = {"apikey": self.api_key, "Accept": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        if prefer:
            headers["Prefer"] = prefer
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
    if isinstance(value, UUID | datetime):
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

    def create_session(
        self,
        *,
        now: datetime | None = None,
        idle_ttl: timedelta = timedelta(minutes=30),
        absolute_ttl: timedelta = timedelta(hours=2),
    ) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        session_id = uuid4()
        payload = {
            "id": session_id,
            "owner_id": self.user.owner_id,
            "state": "OPEN",
            "created_at": now,
            "updated_at": now,
            "last_activity_at": now,
            "idle_expires_at": min(now + idle_ttl, now + absolute_ttl),
            "absolute_expires_at": now + absolute_ttl,
        }
        rows = _json_rows(
            self.client.request(
                "POST",
                "/rest/v1/analysis_sessions",
                payload=payload,
                prefer="return=representation",
            )
        )
        if len(rows) != 1:
            raise PersistenceError("SUPABASE_RESPONSE_INVALID", 502)
        return rows[0]

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

    def upsert_document(self, document: dict[str, Any]) -> dict[str, Any]:
        document_id = UUID(str(document["id"]))
        session_id = UUID(str(document["session_id"]))
        expected_path = object_path(self.user.owner_id, session_id, document_id)
        if document.get("owner_id") != str(self.user.owner_id):
            raise PersistenceError("DOCUMENT_OWNER_INVALID")
        if document.get("storage_object_path") != expected_path:
            raise PersistenceError("DOCUMENT_OBJECT_PATH_INVALID")
        rows = _json_rows(
            self.client.request(
                "POST",
                "/rest/v1/documents",
                query={"on_conflict": "id"},
                payload=document,
                prefer="resolution=merge-duplicates,return=representation",
            )
        )
        if len(rows) != 1:
            raise PersistenceError("SUPABASE_RESPONSE_INVALID", 502)
        return rows[0]

    def delete_session_metadata_after_objects(self, session_id: UUID) -> bool:
        rows = _json_rows(
            self.client.request(
                "DELETE",
                "/rest/v1/analysis_sessions",
                query={
                    "id": f"eq.{session_id}",
                    "owner_id": f"eq.{self.user.owner_id}",
                },
                prefer="return=representation",
            )
        )
        return len(rows) == 1


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
        )

    def download(self, object_path: str) -> bytes:
        self._assert_owner_path(object_path)
        return self.client.request(
            "GET",
            f"/storage/v1/object/{self.configuration.bucket}/{quote(object_path, safe='/')}",
        ).body

    def delete(self, object_path: str) -> bool:
        self._assert_owner_path(object_path)
        result = self.client.request(
            "DELETE",
            f"/storage/v1/object/{self.configuration.bucket}/{quote(object_path, safe='/')}",
        )
        return result.status_code in {200, 204}


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
