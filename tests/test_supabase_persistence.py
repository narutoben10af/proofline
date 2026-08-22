import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import pytest

from proofline.config import Settings
from proofline.supabase_persistence import (
    HttpResult,
    PersistenceError,
    SupabaseAnalysisRepository,
    SupabaseConfiguration,
    SupabasePrivateObjectStore,
    SupabaseUserContext,
    configured_user_adapters,
    object_path,
    persistence_selection,
)

OWNER_A = UUID("10000000-0000-4000-8000-000000000001")
OWNER_B = UUID("20000000-0000-4000-8000-000000000002")
SESSION_A = UUID("11000000-0000-4000-8000-000000000001")
SESSION_B = UUID("22000000-0000-4000-8000-000000000002")
DOCUMENT_A = UUID("13000000-0000-4000-8000-000000000001")


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


def test_document_upsert_uses_exact_owner_session_document_path() -> None:
    expected = object_path(OWNER_A, SESSION_A, DOCUMENT_A)
    response = json.dumps([{"id": str(DOCUMENT_A), "storage_object_path": expected}]).encode()
    transport = FakeTransport([HttpResult(201, response)])
    repository = SupabaseAnalysisRepository(configuration(), user(), transport=transport)
    document = {
        "id": str(DOCUMENT_A),
        "session_id": str(SESSION_A),
        "owner_id": str(OWNER_A),
        "role": "report_pdf",
        "display_name": "report.pdf",
        "canonical_type": "application/pdf",
        "byte_count": 12,
        "storage_object_path": expected,
        "content_sha256": "a" * 64,
        "validation_status": "Ready",
        "expires_at": "2026-08-22T08:00:00Z",
    }

    assert repository.upsert_document(document)["id"] == str(DOCUMENT_A)
    method, url, headers, _body = transport.calls[0]
    assert method == "POST"
    assert "on_conflict=id" in url
    assert headers["Prefer"] == "resolution=merge-duplicates,return=representation"

    document["owner_id"] = str(OWNER_B)
    with pytest.raises(PersistenceError, match="DOCUMENT_OWNER_INVALID"):
        repository.upsert_document(document)


def test_private_object_store_rejects_cross_owner_paths_and_accepts_any_2xx() -> None:
    expected = object_path(OWNER_A, SESSION_A, DOCUMENT_A)
    transport = FakeTransport([HttpResult(201), HttpResult(200, b"pdf"), HttpResult(204)])
    store = SupabasePrivateObjectStore(configuration(), user(), transport=transport)

    store.upload(expected, b"pdf", "application/pdf")
    assert store.download(expected) == b"pdf"
    assert store.delete(expected) is True

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


def test_migration_has_private_bucket_explicit_grants_and_owner_rls_for_every_action() -> None:
    migration = next((Path(__file__).parents[1] / "supabase/migrations").glob("*.sql"))
    sql = migration.read_text(encoding="utf-8").lower()

    for table in ("analysis_sessions", "documents", "source_spans", "analysis_snapshots"):
        assert f"alter table public.{table} enable row level security" in sql
        for action in ("select", "insert", "update", "delete"):
            assert f"{table}_{action}_own" in sql
        assert f"{table}_update_own" in sql
    assert "using ((select auth.uid()) = owner_id)" in sql
    assert "with check ((select auth.uid()) = owner_id)" in sql
    assert "revoke all on table public.analysis_sessions from public, anon, authenticated" in sql
    assert "grant usage on schema public to authenticated" in sql
    assert "'proofline-source-library',\n  'proofline-source-library',\n  false" in sql
    assert "owner_id = (select auth.uid())::text" in sql
    assert "storage.foldername(name)" in sql
    assert "storage.filename(name)" in sql
    assert (
        "storage_object_path = owner_id::text || '/' || session_id::text || '/' || id::text" in sql
    )
    assert "provider_sent boolean not null default false" in sql
    assert "retained_until timestamptz not null" in sql
    assert " owner " not in sql


def test_sql_regression_exercises_cross_user_read_and_delete_denial() -> None:
    sql = (Path(__file__).parents[1] / "supabase/tests/source_library_rls.sql").read_text()
    assert "user A can read user B session" in sql
    assert "user A can read user B object" in sql
    assert "user A deleted user B session" in sql
    assert "user A deleted user B object" in sql
    assert sql.rstrip().endswith("rollback;")
