from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from io import BytesIO
from uuid import UUID

import fitz
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from proofline.api import app
from proofline.live_upload import analyze_authenticated_session
from proofline.parsing.ocr import PaddleOcrCompatibleAdapter
from proofline.source_library import PDF_MIME, XLSX_MIME, SourceLibraryStore
from proofline.supabase_persistence import SupabaseUserContext, object_path
from proofline.upload_analysis import UploadAnalysisError, analyze_uploaded_evidence

OWNER_ID = UUID("10000000-0000-4000-8000-000000000001")
SESSION_ID = UUID("11000000-0000-4000-8000-000000000001")
PDF_ID = UUID("12000000-0000-4000-8000-000000000001")
WORKBOOK_ID = UUID("13000000-0000-4000-8000-000000000001")


def _pdf(text: str | None) -> bytes:
    document = fitz.open()
    page = document.new_page()
    if text is not None:
        page.insert_text((48, 48), text, fontsize=11)
    content = document.tobytes()
    document.close()
    return content


def _workbook() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Consolidated statement"
    for row in (
        ["Issuer", "Live Pipeline Berhad"],
        ["Entity scope", "Live Pipeline Berhad consolidated"],
        ["Currency", "MYR"],
        ["Units", "millions"],
        ["Restatement basis", "not restated"],
        ["Line item", 2025, 2026],
        ["Revenue", 1_000, 1_250],
        ["Operating profit", 150, 250],
        ["Total current assets", 400, 500],
        ["Total current liabilities", 200, 250],
        ["Net cash from operating activities", 260, 325],
        ["Capital expenditures", "(80)", "(100)"],
    ):
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


class FakeRepository:
    def __init__(self) -> None:
        self.documents = [
            {
                "id": str(PDF_ID),
                "session_id": str(SESSION_ID),
                "owner_id": str(OWNER_ID),
                "role": "report_pdf",
                "display_name": "live-report.pdf",
                "canonical_type": PDF_MIME,
                "validation_status": "Ready",
                "storage_object_path": object_path(OWNER_ID, SESSION_ID, PDF_ID),
                "uploaded_at": "2026-08-22T08:00:00Z",
            },
            {
                "id": str(WORKBOOK_ID),
                "session_id": str(SESSION_ID),
                "owner_id": str(OWNER_ID),
                "role": "workbook",
                "display_name": "live-facts.xlsx",
                "canonical_type": XLSX_MIME,
                "validation_status": "Ready",
                "storage_object_path": object_path(OWNER_ID, SESSION_ID, WORKBOOK_ID),
                "uploaded_at": "2026-08-22T08:00:01Z",
            },
        ]

    def touch_session(self, session_id: UUID) -> dict:
        assert session_id == SESSION_ID
        return {"id": str(session_id), "state": "OPEN"}

    def list_documents(self, session_id: UUID) -> list[dict]:
        assert session_id == SESSION_ID
        return self.documents


class FakeObjects:
    def __init__(self, pdf: bytes, workbook: bytes) -> None:
        self.content = {
            object_path(OWNER_ID, SESSION_ID, PDF_ID): pdf,
            object_path(OWNER_ID, SESSION_ID, WORKBOOK_ID): workbook,
        }

    def download(self, path: str) -> bytes:
        return self.content[path]


class FakeMaintenance:
    def __init__(self) -> None:
        self.persisted: dict | None = None

    def persist_completed_analysis(self, **payload) -> dict:
        self.persisted = payload
        return {"status": "complete"}


class HttpRepository:
    def __init__(self) -> None:
        self.documents: list[dict] = []

    def create_session(self) -> dict:
        return {
            "id": str(SESSION_ID),
            "state": "OPEN",
            "created_at": "2026-08-22T08:00:00Z",
            "idle_expires_at": "2026-08-22T08:30:00Z",
            "absolute_expires_at": "2026-08-22T10:00:00Z",
        }

    def register_document(self, document: dict) -> dict:
        row = {
            **document,
            "owner_id": str(OWNER_ID),
            "storage_object_path": object_path(
                OWNER_ID, UUID(str(document["session_id"])), UUID(str(document["id"]))
            ),
            "validation_status": "Checking",
            "uploaded_at": "2026-08-22T08:00:01Z",
            "sanitization_warning": None,
        }
        self.documents.append(row)
        return row

    def touch_session(self, session_id: UUID) -> dict:
        assert session_id == SESSION_ID
        return {"id": str(session_id), "state": "OPEN"}

    def list_documents(self, session_id: UUID) -> list[dict]:
        assert session_id == SESSION_ID
        return self.documents


class HttpObjects:
    def __init__(self) -> None:
        self.content: dict[str, bytes] = {}

    def upload(self, path: str, content: bytes, _canonical_type: str) -> None:
        assert path.startswith(f"{OWNER_ID}/{SESSION_ID}/")
        self.content[path] = content

    def download(self, path: str) -> bytes:
        return self.content[path]

    def delete(self, path: str) -> bool:
        return self.content.pop(path, None) is not None


class HttpMaintenance(FakeMaintenance):
    def __init__(self, repository: HttpRepository) -> None:
        super().__init__()
        self.repository = repository

    def mark_document_validation(self, *, document_id: UUID, **values) -> dict:
        row = next(item for item in self.repository.documents if item["id"] == str(document_id))
        status = values.pop("status")
        values.pop("owner_id")
        row.update(values, validation_status=status)
        return row

    def discard_document(self, *, document_id: UUID, **_values) -> None:
        self.repository.documents = [
            item for item in self.repository.documents if item["id"] != str(document_id)
        ]


def test_authenticated_pipeline_reloads_exact_private_objects_and_persists_cited_evidence(
    tmp_path,
) -> None:
    pdf = _pdf(
        "Live Pipeline Berhad Annual Report\n"
        "Issuer: Live Pipeline Berhad\n"
        "Currency MYR\n"
        "Consolidated financial statements\n"
        "Revenue grew 25% for 2026.\n"
        "Operating margin was 20% for 2026.\n"
        "Current ratio was 2 for 2026.\n"
        "Project-defined FCF margin was 18% for 2026."
    )
    workbook = _workbook()
    maintenance = FakeMaintenance()
    validator = SourceLibraryStore(root=tmp_path / "validation")

    response = analyze_authenticated_session(
        user=SupabaseUserContext(owner_id=OWNER_ID, access_token="user.jwt.access-token"),
        repository=FakeRepository(),
        objects=FakeObjects(pdf, workbook),
        maintenance=maintenance,
        validator=validator,
        session_id=SESSION_ID,
        ocr=None,
    )

    assert {document.id for document in response.documents} == {str(PDF_ID), str(WORKBOOK_ID)}
    assert {document.version_label for document in response.documents} == {
        "live-report.pdf",
        "live-facts.xlsx",
    }
    assert response.cached_output is False
    assert maintenance.persisted is not None
    assert maintenance.persisted["session_id"] == SESSION_ID
    assert maintenance.persisted["owner_id"] == OWNER_ID
    assert maintenance.persisted["response"] == response.model_dump(mode="json")
    assert maintenance.persisted["evidence"]
    assert {row["source_id"] for row in maintenance.persisted["evidence"]} == {
        str(WORKBOOK_ID)
    }
    assert all(
        row["source_span_id"].startswith("span:")
        for row in maintenance.persisted["evidence"]
    )


def test_authenticated_http_upload_pair_returns_dynamic_analysis(monkeypatch) -> None:
    repository = HttpRepository()
    objects = HttpObjects()
    maintenance = HttpMaintenance(repository)
    user = SupabaseUserContext(owner_id=OWNER_ID, access_token="test.user.access-token")
    monkeypatch.setattr(
        "proofline.api.authenticated_adapters",
        lambda _settings, _authorization: (user, repository, objects, maintenance),
    )
    headers = {
        "Origin": "https://testserver",
        "Authorization": "Bearer test.user.access-token",
    }
    report = _pdf(
        "Live Pipeline Berhad Annual Report\n"
        "Issuer: Live Pipeline Berhad\n"
        "Currency MYR\n"
        "Consolidated financial statements\n"
        "Revenue grew 25% for 2026.\n"
        "Operating margin was 20% for 2026.\n"
        "Current ratio was 2 for 2026.\n"
        "Project-defined FCF margin was 18% for 2026."
    )

    with TestClient(app, base_url="https://testserver") as client:
        created = client.post("/api/authenticated/sessions", headers=headers)
        pdf_upload = client.post(
            f"/api/authenticated/sessions/{SESSION_ID}/files",
            headers=headers,
            data={"role": "report_pdf"},
            files={"file": ("synthetic-live-report.pdf", report, PDF_MIME)},
        )
        workbook_upload = client.post(
            f"/api/authenticated/sessions/{SESSION_ID}/files",
            headers=headers,
            data={"role": "workbook"},
            files={"file": ("synthetic-live-facts.xlsx", _workbook(), XLSX_MIME)},
        )
        analyzed = client.post(
            f"/api/authenticated/sessions/{SESSION_ID}/analysis", headers=headers
        )

    assert created.status_code == 201
    assert created.json()["persistence"] == "supabase-private"
    assert pdf_upload.status_code == 201
    assert workbook_upload.status_code == 201
    assert analyzed.status_code == 200
    payload = analyzed.json()
    assert payload["cached_output"] is False
    assert {item["version_label"] for item in payload["documents"]} == {
        "synthetic-live-report.pdf",
        "synthetic-live-facts.xlsx",
    }
    assert any(
        Decimal(str(item["numeric_value"])) == Decimal("1250000000")
        for item in payload["observations"]
    )
    assert any(
        Decimal(str(item["result"])) == Decimal("0.25")
        for item in payload["metric_results"]
    )
    assert maintenance.persisted is not None
    assert maintenance.persisted["response"] == payload


def test_scanned_pdf_fails_closed_with_specific_ocr_unavailable_reason(tmp_path) -> None:
    maintenance = FakeMaintenance()
    validator = SourceLibraryStore(root=tmp_path / "validation")
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/api/authenticated/sessions",
            headers={"Origin": "https://testserver"},
        )
    assert response.status_code == 401
    assert response.json() == {"reason_code": "AUTH_REQUIRED"}

    repository = FakeRepository()
    objects = FakeObjects(_pdf(None), _workbook())
    try:
        analyze_authenticated_session(
            user=SupabaseUserContext(owner_id=OWNER_ID, access_token="user.jwt.access-token"),
            repository=repository,
            objects=objects,
            maintenance=maintenance,
            validator=validator,
            session_id=SESSION_ID,
            ocr=None,
        )
    except Exception as error:
        assert getattr(error, "reason_code", None) == "OCR_UNAVAILABLE"
    else:
        raise AssertionError("scanned PDF unexpectedly produced analysis without OCR")


def test_low_confidence_ocr_never_reaches_workbook_analysis() -> None:
    ocr = PaddleOcrCompatibleAdapter(
        lambda _image: (("Revenue grew 25% for 2026.", 0.41),), threshold=0.7
    )
    with pytest.raises(UploadAnalysisError, match="confidence") as captured:
        analyze_uploaded_evidence(
            pdf_content=_pdf(None),
            workbook_content=_workbook(),
            session_id=str(SESSION_ID),
            pdf_file_id=str(PDF_ID),
            workbook_file_id=str(WORKBOOK_ID),
            retrieved_at=datetime.fromisoformat("2026-08-22T08:00:00+00:00"),
            ocr=ocr,
        )
    assert captured.value.code == "OCR_LOW_CONFIDENCE"
