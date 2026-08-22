import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from proofline.config import Settings
from proofline.contracts import (
    AnalysisResponse,
    DocumentVersion,
    FactObservation,
    Period,
    SourceSpan,
    SpreadsheetSourceRef,
)
from proofline.source_library import ProcessSessionRepository
from proofline.supabase_persistence import (
    HttpResult,
    PersistenceError,
    SupabaseAnalysisRepository,
    SupabaseConfiguration,
    SupabasePrivateObjectStore,
    SupabaseServerMaintenanceRepository,
    SupabaseUserContext,
    configured_user_adapters,
    object_path,
    persistence_selection,
    source_session_repository,
)

OWNER_A = UUID("10000000-0000-4000-8000-000000000001")
OWNER_B = UUID("20000000-0000-4000-8000-000000000002")
SESSION_A = UUID("11000000-0000-4000-8000-000000000001")
SESSION_B = UUID("22000000-0000-4000-8000-000000000002")
DOCUMENT_A = UUID("13000000-0000-4000-8000-000000000001")
UPLOAD_SESSION = "src-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
UPLOAD_SOURCE = "file-bbbbbbbbbbbbbbbbbbbbbbbb"


@dataclass
class FakeTransport:
    results: list[HttpResult] = field(default_factory=list)
    calls: list[tuple[str, str, dict[str, str], bytes | None]] = field(default_factory=list)

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> HttpResult:
        self.calls.append((method, url, headers, body))
        return self.results.pop(0) if self.results else HttpResult(204)


def configuration() -> SupabaseConfiguration:
    return SupabaseConfiguration(
        project_url="https://qvxohnlboefomtjecxdh.supabase.co",
        publishable_key="sb_publishable_test-only-placeholder",
    )


def user(owner: UUID = OWNER_A) -> SupabaseUserContext:
    return SupabaseUserContext(owner_id=owner, access_token="user.jwt.access-token")


def assistant_analysis() -> AnalysisResponse:
    document_id = f"{UPLOAD_SESSION}:workbook"
    observations = []
    spans = []
    for index, (concept, value) in enumerate(
        (("revenue", Decimal("120000000")), ("operating_profit", Decimal("24000000"))),
        start=1,
    ):
        span_id = f"span:{concept}:2026"
        spans.append(
            SourceSpan(
                id=span_id,
                document_version_id=document_id,
                source=SpreadsheetSourceRef(
                    document_id=document_id,
                    sheet="Financial statements",
                    cell=f"B{index}",
                    display_value=str(value),
                ),
            )
        )
        observations.append(
            FactObservation(
                id=f"fact:{index:020x}",
                source_span_id=span_id,
                concept=concept,
                numeric_value=value,
                display_value=f"MYR {value}",
                unit="MYR base units",
                currency="MYR",
                period=Period(
                    start=date(2026, 1, 1),
                    end=date(2026, 12, 31),
                    duration_weeks=52,
                ),
                entity_scope="Northstar Industrial plc consolidated",
                restated=False,
                sign_convention="positive",
                fixture_status="derived",
            )
        )
    return AnalysisResponse(
        documents=(
            DocumentVersion(
                id=document_id,
                sha256="a" * 64,
                issuer="Northstar Industrial plc",
                source_url=f"urn:proofline:session:{UPLOAD_SOURCE}",
                retrieved_at=datetime(2026, 8, 22, tzinfo=UTC),
                reporting_basis="Northstar Industrial plc consolidated",
                version_label="FY2026",
            ),
        ),
        source_spans=tuple(spans),
        claims=(),
        observations=tuple(observations),
        metric_results=(),
        findings=(),
    )


def test_process_local_is_the_default_and_supabase_is_never_auto_activated() -> None:
    local = persistence_selection(Settings(_env_file=None))
    assert local.backend == "process-local"
    assert local.configured is True
    assert local.activated is True

    configured = Settings(
        _env_file=None,
        source_library_persistence_backend="supabase",
        supabase_url="https://qvxohnlboefomtjecxdh.supabase.co",
        supabase_publishable_key="sb_publishable_test-only-placeholder",
        supabase_secret_key="sb_secret_test-only-placeholder",
    )
    selection = persistence_selection(configured)
    assert selection.backend == "supabase"
    assert selection.configured is True
    assert selection.activated is False
    assert selection.reason_code == "SUPABASE_AUTH_INTEGRATION_REQUIRED"


def test_source_library_repository_boundary_defaults_local_and_fails_closed_for_supabase() -> None:
    repository = source_session_repository(Settings(_env_file=None))
    assert isinstance(repository, ProcessSessionRepository)

    configured = Settings(
        _env_file=None,
        source_library_persistence_backend="supabase",
        supabase_url="https://qvxohnlboefomtjecxdh.supabase.co",
        supabase_publishable_key="sb_publishable_test-only-placeholder",
        supabase_secret_key="sb_secret_test-only-placeholder",
    )
    with pytest.raises(PersistenceError, match="SUPABASE_AUTH_INTEGRATION_REQUIRED"):
        source_session_repository(configured)


def test_configuration_rejects_secret_or_legacy_key_in_publishable_slot() -> None:
    for invalid in ("sb_secret_backend-only", "legacy-anon-jwt", "service_role"):
        with pytest.raises(PersistenceError, match="SUPABASE_PUBLISHABLE_KEY_INVALID"):
            SupabaseConfiguration(
                project_url="https://qvxohnlboefomtjecxdh.supabase.co",
                publishable_key=invalid,
            )


def test_user_repository_sends_publishable_key_and_user_jwt_with_owner_filter() -> None:
    transport = FakeTransport([HttpResult(200, b"[]")])
    repository = SupabaseAnalysisRepository(configuration(), user(), transport=transport)

    assert repository.get_session(SESSION_B) is None

    method, url, headers, body = transport.calls[0]
    assert method == "GET"
    assert "owner_id=eq.10000000-0000-4000-8000-000000000001" in url
    assert headers["apikey"].startswith("sb_publishable_")
    assert headers["Authorization"] == "Bearer user.jwt.access-token"
    assert "secret" not in json.dumps(headers).lower()
    assert body is None


def test_user_writes_use_server_authored_rpc_fields_only() -> None:
    expected = object_path(OWNER_A, SESSION_A, DOCUMENT_A)
    responses = [
        HttpResult(200, json.dumps({"id": str(SESSION_A), "state": "OPEN"}).encode()),
        HttpResult(200, json.dumps({"id": str(SESSION_A), "state": "OPEN"}).encode()),
        HttpResult(
            200,
            json.dumps(
                {
                    "id": str(DOCUMENT_A),
                    "storage_object_path": expected,
                    "validation_status": "Checking",
                }
            ).encode(),
        ),
        HttpResult(200, json.dumps({"id": str(SESSION_A), "state": "DELETING"}).encode()),
    ]
    transport = FakeTransport(responses)
    repository = SupabaseAnalysisRepository(configuration(), user(), transport=transport)

    assert repository.create_session()["state"] == "OPEN"
    assert repository.touch_session(SESSION_A)["state"] == "OPEN"
    document = {
        "id": str(DOCUMENT_A),
        "session_id": str(SESSION_A),
        "role": "report_pdf",
        "display_name": "report.pdf",
        "canonical_type": "application/pdf",
        "byte_count": 12,
        "content_sha256": "a" * 64,
    }

    assert repository.register_document(document)["validation_status"] == "Checking"
    assert repository.request_delete(SESSION_A)["state"] == "DELETING"

    method, url, _headers, body = transport.calls[0]
    assert method == "POST"
    assert url.endswith("/rest/v1/rpc/create_analysis_session")
    assert json.loads(body) == {}

    assert transport.calls[1][1].endswith("/rest/v1/rpc/touch_analysis_session")
    method, url, _headers, body = transport.calls[2]
    assert method == "POST"
    assert url.endswith("/rest/v1/rpc/register_source_document")
    payload = json.loads(body)
    assert payload["target_session_id"] == str(SESSION_A)
    assert payload["target_document_id"] == str(DOCUMENT_A)
    assert not {
        "owner_id",
        "storage_object_path",
        "validation_status",
        "expires_at",
    }.intersection(payload)
    assert transport.calls[3][1].endswith("/rest/v1/rpc/request_analysis_session_deletion")


def test_user_repository_rejects_attempted_server_field_spoofing_before_network() -> None:
    transport = FakeTransport()
    repository = SupabaseAnalysisRepository(configuration(), user(), transport=transport)
    base = {
        "id": str(DOCUMENT_A),
        "session_id": str(SESSION_A),
        "role": "report_pdf",
        "display_name": "report.pdf",
        "canonical_type": "application/pdf",
        "byte_count": 12,
        "content_sha256": "a" * 64,
    }
    for server_field, value in (
        ("owner_id", str(OWNER_B)),
        ("storage_object_path", "../foreign"),
        ("validation_status", "Ready"),
        ("expires_at", "2999-01-01T00:00:00Z"),
    ):
        with pytest.raises(PersistenceError, match="DOCUMENT_SERVER_FIELDS_FORBIDDEN"):
            repository.register_document({**base, server_field: value})
    assert transport.calls == []


def test_private_object_store_rejects_cross_owner_paths_and_accepts_any_2xx() -> None:
    expected = object_path(OWNER_A, SESSION_A, DOCUMENT_A)
    transport = FakeTransport([HttpResult(201), HttpResult(200, b"pdf"), HttpResult(204)])
    store = SupabasePrivateObjectStore(configuration(), user(), transport=transport)

    store.upload(expected, b"pdf", "application/pdf")
    assert store.download(expected) == b"pdf"
    assert store.delete(expected) is True
    assert transport.calls[0][2]["x-upsert"] == "false"
    assert "/storage/v1/object/authenticated/proofline-source-library/" in transport.calls[1][1]

    foreign = object_path(OWNER_B, SESSION_B, DOCUMENT_A)
    with pytest.raises(PersistenceError, match="STORAGE_OBJECT_PATH_INVALID"):
        store.download(foreign)
    assert len(transport.calls) == 3


def test_adapter_factory_stays_gated_without_complete_server_configuration() -> None:
    settings = Settings(
        _env_file=None,
        source_library_persistence_backend="supabase",
        supabase_url="https://qvxohnlboefomtjecxdh.supabase.co",
        supabase_publishable_key="sb_publishable_test-only-placeholder",
    )
    with pytest.raises(PersistenceError, match="SUPABASE_NOT_CONFIGURED"):
        configured_user_adapters(settings, user(), transport=FakeTransport())


def test_server_maintenance_uses_secret_only_backend_header_and_bounds_receipts() -> None:
    now = datetime(2026, 8, 22, 6, tzinfo=UTC)
    session_response = json.dumps([{"id": str(SESSION_A)}]).encode()
    document_response = json.dumps([{"id": str(DOCUMENT_A), "validation_status": "Ready"}]).encode()
    transport = FakeTransport(
        [
            HttpResult(200, session_response),
            HttpResult(200, document_response),
            HttpResult(200, b"[]"),
        ]
    )
    maintenance = SupabaseServerMaintenanceRepository(
        configuration(), "sb_secret_backend-test-placeholder", transport=transport
    )

    maintenance.mark_provider_transfer_started(
        session_id=SESSION_A, owner_id=OWNER_A, started_at=now
    )
    validated = maintenance.mark_document_validation(
        document_id=DOCUMENT_A,
        owner_id=OWNER_A,
        status="Ready",
        canonical_type="application/pdf",
        byte_count=12,
        content_sha256="a" * 64,
        validated_at=now,
    )
    assert validated["validation_status"] == "Ready"
    assert maintenance.list_expired_sessions(now=now) == []

    _method, _url, headers, body = transport.calls[0]
    assert headers["apikey"].startswith("sb_secret_")
    assert "Authorization" not in headers
    assert json.loads(body)["provider_sent"] is True
    assert json.loads(body)["provider_sent_at"].startswith("2026-08-22T06:00:00")

    method, url, headers, body = transport.calls[1]
    assert method == "PATCH"
    assert "/rest/v1/documents" in url
    assert "validation_status=eq.Checking" in url
    assert "Authorization" not in headers
    assert json.loads(body)["validation_status"] == "Ready"
    assert json.loads(body)["validated_at"].startswith("2026-08-22T06:00:00")

    invalid_receipt = {
        "completed_at": now.isoformat(),
        "retained_until": (now + timedelta(hours=3)).isoformat(),
        "provider_sent": False,
    }
    with pytest.raises(PersistenceError, match="DELETION_RECEIPT_RETENTION_INVALID"):
        maintenance.write_deletion_receipt(invalid_receipt)


def test_server_writes_numeric_free_magic_assistant_index_from_reviewed_analysis() -> None:
    transport = FakeTransport([HttpResult(200, b"2")])
    maintenance = SupabaseServerMaintenanceRepository(
        configuration(), "sb_secret_backend-test-placeholder", transport=transport
    )

    assert (
        maintenance.replace_magic_assistant_evidence(
            analysis_session_id=SESSION_A,
            owner_id=OWNER_A,
            external_session_id=UPLOAD_SESSION,
            analysis=assistant_analysis(),
            document_ids_by_source_id={UPLOAD_SOURCE: DOCUMENT_A},
        )
        == 2
    )

    method, url, headers, body = transport.calls[0]
    assert method == "POST"
    assert url.endswith("/rest/v1/rpc/replace_magic_assistant_evidence")
    assert headers["apikey"].startswith("sb_secret_")
    assert "Authorization" not in headers
    payload = json.loads(body)
    assert payload["target_analysis_session_id"] == str(SESSION_A)
    assert payload["target_owner_id"] == str(OWNER_A)
    assert payload["external_session_id"] == UPLOAD_SESSION
    assert {row["concept"] for row in payload["evidence_rows"]} == {
        "revenue",
        "operating_profit",
    }
    serialized_rows = json.dumps(payload["evidence_rows"])
    for forbidden in ("numeric_value", "display_value", "quote", "formula", "file_bytes"):
        assert forbidden not in serialized_rows


def test_magic_assistant_index_fails_closed_without_persisted_document_mapping() -> None:
    maintenance = SupabaseServerMaintenanceRepository(
        configuration(), "sb_secret_backend-test-placeholder", transport=FakeTransport()
    )
    with pytest.raises(PersistenceError, match="MAGIC_ASSISTANT_DOCUMENT_MAPPING_REQUIRED"):
        maintenance.replace_magic_assistant_evidence(
            analysis_session_id=SESSION_A,
            owner_id=OWNER_A,
            external_session_id=UPLOAD_SESSION,
            analysis=assistant_analysis(),
            document_ids_by_source_id={},
        )


def test_migration_makes_trust_fields_rpc_or_service_role_only() -> None:
    migration = (
        Path(__file__).parents[1]
        / "supabase/migrations/20260822054654_source_library_persistence.sql"
    )
    sql = migration.read_text(encoding="utf-8").lower()

    for table in ("analysis_sessions", "documents", "source_spans", "analysis_snapshots"):
        assert f"alter table public.{table} enable row level security" in sql
        assert f"{table}_select_own" in sql
        for action in ("insert", "update", "delete"):
            assert f"{table}_{action}_own" not in sql
    assert "revoke all on table public.analysis_sessions from public, anon, authenticated" in sql
    assert "grant usage on schema public to authenticated" in sql
    assert "grant select on public.analysis_sessions to authenticated" in sql
    assert "grant insert" not in sql.split("to service_role;")[0]
    assert "grant update" not in sql.split("to service_role;")[0]
    for function in (
        "create_analysis_session",
        "touch_analysis_session",
        "register_source_document",
        "request_analysis_session_deletion",
    ):
        assert f"create function public.{function}" in sql
        assert "security definer" in sql
        assert "set search_path = ''" in sql
        assert f"grant execute on function public.{function}" in sql
    assert "'checking',\n    null," in sql
    assert "instant + interval '2 hours'" in sql
    assert "least(instant + interval '30 minutes', absolute_expires_at)" in sql
    assert "'proofline-source-library',\n  'proofline-source-library',\n  false" in sql
    assert "owner_id = (select auth.uid())::text" in sql
    assert "storage.foldername(name)" in sql
    assert "storage.filename(name)" in sql
    assert (
        "storage_object_path = owner_id::text || '/' || session_id::text || '/' || id::text" in sql
    )
    assert "provider_sent boolean not null default false" in sql
    assert "check (provider_sent = (provider_sent_at is not null))" in sql
    assert "retained_until timestamptz not null" in sql
    assert "storage.objects for delete to authenticated" in sql
    assert "state = 'deleting'" in sql
    assert " owner =" not in sql


def test_magic_assistant_migration_is_owner_read_only_and_numeric_free() -> None:
    migration = (
        Path(__file__).parents[1]
        / "supabase/migrations/20260822072915_magic_assistant_evidence.sql"
    )
    sql = migration.read_text(encoding="utf-8").lower()

    assert "create table public.magic_assistant_evidence" in sql
    assert "alter table public.magic_assistant_evidence enable row level security" in sql
    assert "alter table public.magic_assistant_evidence force row level security" in sql
    assert "magic_assistant_evidence_select_active_own" in sql
    assert "(select auth.uid()) = owner_id" in sql
    assert "not coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false)" in sql
    assert "grant select on public.magic_assistant_evidence to authenticated" in sql
    assert "grant insert on public.magic_assistant_evidence to authenticated" not in sql
    assert "revoke all on table public.magic_assistant_evidence from service_role" in sql
    assert "owned_session.owner_id = magic_assistant_evidence.owner_id" in sql
    assert "create function public.replace_magic_assistant_evidence" in sql
    assert "security definer" in sql
    assert "set search_path = ''" in sql
    assert "service_role_required" in sql
    assert "ready_source_document_required" in sql
    for forbidden_column in ("numeric_value", "display_value", "source_quote", "file_bytes"):
        assert forbidden_column not in sql


def test_sql_regression_covers_roles_spoofing_receipts_and_storage_crud() -> None:
    sql = (Path(__file__).parents[1] / "supabase/tests/source_library_rls.sql").read_text()
    for marker in (
        "same-user RPC insert failed",
        "same-user RPC update failed",
        "cross-user RPC insert succeeded",
        "cross-user RPC update succeeded",
        "anon role reached private metadata",
        "anonymous Auth user created a session",
        "spoofed owner insert succeeded",
        "spoofed expiry update succeeded",
        "spoofed Ready update succeeded",
        "traversal object insert succeeded",
        "cross-user receipt became visible",
        "authenticated receipt write succeeded",
        "service-role Ready write failed",
        "same-user Storage insert failed",
        "same-user Storage update failed",
        "same-user Storage delete failed",
        "cross-user Storage CRUD succeeded",
        "Ready Storage upsert succeeded",
        "Ready Storage delete succeeded",
    ):
        assert marker in sql
    assert sql.rstrip().endswith("rollback;")
