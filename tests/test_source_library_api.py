import asyncio
import hashlib
import io
import json
import logging
import threading
import time
import zipfile
import zlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import UploadFile
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    EncodedStreamObject,
    NameObject,
    NumberObject,
    RectangleObject,
    TextStringObject,
)
from starlette.datastructures import Headers

from proofline.api import CAPABILITY_COOKIE, app
from proofline.contracts import (
    SourceDeletionReceipt,
    SourceFileMetadata,
    SourceSessionCreated,
    SourceSessionStatus,
)
from proofline.source_library import (
    PDF_MIME,
    PDF_SANITIZER_VERSION,
    XLSX_MIME,
    SourceLibraryStore,
)

ORIGIN_HEADERS = {"Origin": "https://testserver", "Sec-Fetch-Site": "same-origin"}


def pdf_bytes(*extra: bytes) -> bytes:
    target = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    if extra:
        writer.add_metadata({"/Subject": b" ".join(extra).decode("latin-1")})
    writer.write(target)
    return target.getvalue()


def escaped_javascript_pdf() -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R /OpenAction 4 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 72 72] >>",
        b"<< /S /Java#53cript /JS (app.alert\\(blocked\\)) >>",
    ]
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode())
    payload.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(payload)


def encrypted_pdf() -> bytes:
    target = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("password")
    writer.write(target)
    return target.getvalue()


def uri_action_pdf() -> bytes:
    target = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_uri(0, "https://example.invalid", RectangleObject((0, 0, 20, 20)))
    writer.write(target)
    return target.getvalue()


def catalog_action_pdf(action_name: str) -> bytes:
    target = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    action = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Action"),
            NameObject("/S"): NameObject(action_name),
        }
    )
    if action_name == "/GoToR":
        action[NameObject("/F")] = TextStringObject("external.pdf")
        action[NameObject("/D")] = TextStringObject("destination")
    writer.root_object[NameObject("/OpenAction")] = writer._add_object(action)
    writer.write(target)
    return target.getvalue()


def internal_open_action_pdf() -> bytes:
    target = io.BytesIO()
    writer = PdfWriter()
    page = writer.add_blank_page(width=72, height=72)
    action = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Action"),
            NameObject("/S"): NameObject("/GoTo"),
            NameObject("/D"): ArrayObject([page.indirect_reference, NameObject("/Fit")]),
        }
    )
    writer.root_object[NameObject("/OpenAction")] = writer._add_object(action)
    writer.write(target)
    return target.getvalue()


def interactive_pdf_requiring_sanitization() -> bytes:
    target = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_uri(0, "https://attacker.invalid/exfiltrate", RectangleObject((0, 0, 20, 20)))
    writer.add_js('app.alert("SANITIZER-MARKER");')
    writer.add_attachment("payload.txt", b"EMBEDDED-MARKER")
    writer.root_object[NameObject("/AcroForm")] = DictionaryObject(
        {NameObject("/XFA"): TextStringObject("XFA-MARKER")}
    )
    writer.write(target)
    return target.getvalue()


def large_benign_pdf_graph() -> bytes:
    target = io.BytesIO()
    writer = PdfWriter()
    page = writer.add_blank_page(width=72, height=72)
    page[NameObject("/ProoflineBenignArray")] = ArrayObject(
        NumberObject(index) for index in range(12_000)
    )
    writer.write(target)
    return target.getvalue()


def decompression_bomb_pdf() -> bytes:
    target = io.BytesIO()
    writer = PdfWriter()
    page = writer.add_blank_page(width=72, height=72)
    stream = EncodedStreamObject()
    stream._data = zlib.compress(b"q\n" * (6 * 1024 * 1024))
    stream[NameObject("/Filter")] = NameObject("/FlateDecode")
    page[NameObject("/Contents")] = writer._add_object(stream)
    writer.write(target)
    return target.getvalue()


def sentinel_log_pdf() -> bytes:
    sentinel = "DO-NOT-LEAK-SENTINEL"
    writer = PdfWriter()
    page = writer.add_blank_page(width=72, height=72)
    cmap = DecodedStreamObject()
    cmap.set_data(
        (
            "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
            "/CMapType 2 def\n1 begincodespacerange\n<00> <FF>\n"
            f"endcodespacerange\n1 beginbfchar\n<41> <{sentinel}>\n"
            "endbfchar\nendcmap\nend\nend"
        ).encode()
    )
    cmap_ref = writer._add_object(cmap)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            NameObject("/ToUnicode"): cmap_ref,
        }
    )
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf (A) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    target = io.BytesIO()
    writer.write(target)
    return target.getvalue()


def xlsx_bytes(
    *,
    extra_entries: dict[str, bytes] | None = None,
    content_types: bytes | None = None,
) -> bytes:
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            content_types
            or b'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><workbook '
            'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheets><sheet name="Facts" sheetId="1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0"?><worksheet '
            'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1"><c r="A1"><f>1+1</f><v>2</v></c>'
            "</row></sheetData></worksheet>",
        )
        for name, content in (extra_entries or {}).items():
            archive.writestr(name, content)
    return target.getvalue()


def create_session(client: TestClient) -> tuple[dict, str]:
    response = client.post("/api/sessions", headers=ORIGIN_HEADERS)
    assert response.status_code == 201
    capability = client.cookies.get(CAPABILITY_COOKIE)
    assert capability
    return response.json(), capability


def mutation_headers(csrf_token: str) -> dict[str, str]:
    return {**ORIGIN_HEADERS, "X-Proofline-CSRF": csrf_token}


def upload_pair(client: TestClient, session: dict) -> tuple[dict, dict]:
    headers = mutation_headers(session["csrf_token"])
    pdf = client.post(
        f"/api/sessions/{session['session_id']}/files",
        headers=headers,
        data={"role": "report_pdf"},
        files={"file": ("annual-report.pdf", pdf_bytes(), PDF_MIME)},
    )
    workbook = client.post(
        f"/api/sessions/{session['session_id']}/files",
        headers=headers,
        data={"role": "workbook"},
        files={"file": ("evidence.xlsx", xlsx_bytes(), XLSX_MIME)},
    )
    assert pdf.status_code == workbook.status_code == 201
    return pdf.json(), workbook.json()


def test_cookie_authorized_upload_list_download_remove_and_delete() -> None:
    with TestClient(app, base_url="https://testserver") as client:
        session, _capability = create_session(client)
        cookie = client.cookies.jar._cookies["testserver.local"]["/"][CAPABILITY_COOKIE]
        assert cookie.secure is True
        assert cookie.has_nonstandard_attr("HttpOnly")
        assert cookie.get_nonstandard_attr("SameSite") == "strict"

        pdf, workbook = upload_pair(client, session)
        listed = client.get(f"/api/sessions/{session['session_id']}/files")
        content = client.get(
            f"/api/sessions/{session['session_id']}/files/{pdf['file_id']}/content",
            params={"disposition": "inline"},
        )
        unavailable = client.post(
            f"/api/sessions/{session['session_id']}/start",
            headers=mutation_headers(session["csrf_token"]),
        )
        still_open = client.get(f"/api/sessions/{session['session_id']}")
        removed = client.delete(
            f"/api/sessions/{session['session_id']}/files/{workbook['file_id']}",
            headers=mutation_headers(session["csrf_token"]),
        )

        assert [item["role"] for item in listed.json()] == ["report_pdf", "workbook"]
        assert content.content.startswith(b"%PDF-")
        assert content.headers["content-disposition"].startswith("inline")
        assert content.headers["cache-control"] == "no-store, private"
        assert unavailable.json() == {"reason_code": "PROVIDER_ACCESS_REQUIRED"}
        assert still_open.json()["state"] == "OPEN"
        assert removed.status_code == 200

        receipt = client.delete(
            f"/api/sessions/{session['session_id']}",
            headers=mutation_headers(session["csrf_token"]),
        )
        retry = client.delete(
            f"/api/sessions/{session['session_id']}",
            headers=mutation_headers(session["csrf_token"]),
        )
        gone = client.get(f"/api/sessions/{session['session_id']}/files")

    assert receipt.status_code == 200
    assert receipt.json() == retry.json()
    assert receipt.json()["claim"] == (
        "Deleted from this running container’s application-managed session storage."
    )
    assert receipt.json()["removed"]["source_files"] == {"count": 1, "bytes": len(pdf_bytes())}
    assert receipt.json()["app_managed_directory_gone"] is True
    assert receipt.json()["source_material_sent_to_provider"] is False
    assert receipt.headers["cache-control"] == "no-store, private"
    assert gone.status_code == 410
    assert gone.json() == {"reason_code": "SESSION_GONE"}


def test_cross_session_and_csrf_origin_access_is_denied() -> None:
    with TestClient(app, base_url="https://testserver") as client:
        first, first_capability = create_session(client)
        first_pdf, _first_workbook = upload_pair(client, first)
        second, _second_capability = create_session(client)
        cross_list = client.get(f"/api/sessions/{first['session_id']}/files")
        cross_download = client.get(
            f"/api/sessions/{first['session_id']}/files/{first_pdf['file_id']}/content"
        )
        cross_delete = client.delete(
            f"/api/sessions/{first['session_id']}",
            headers=mutation_headers(second["csrf_token"]),
        )
        no_origin = client.post(
            f"/api/sessions/{second['session_id']}/files",
            headers={"X-Proofline-CSRF": second["csrf_token"]},
            data={"role": "report_pdf"},
            files={"file": ("report.pdf", pdf_bytes(), PDF_MIME)},
        )
        wrong_csrf = client.post(
            f"/api/sessions/{second['session_id']}/files",
            headers=mutation_headers("wrong-token-that-is-long-enough-for-testing"),
            data={"role": "report_pdf"},
            files={"file": ("report.pdf", pdf_bytes(), PDF_MIME)},
        )
        client.cookies.set(CAPABILITY_COOKIE, first_capability, domain="testserver.local", path="/")
        own_list = client.get(f"/api/sessions/{first['session_id']}/files")

    assert cross_list.status_code == 404
    assert cross_list.json() == {"reason_code": "SESSION_NOT_FOUND"}
    assert cross_download.status_code == 404
    assert cross_download.json() == {"reason_code": "SESSION_NOT_FOUND"}
    assert cross_delete.status_code == 404
    assert cross_delete.json() == {"reason_code": "SESSION_NOT_FOUND"}
    assert no_origin.json() == {"reason_code": "ORIGIN_NOT_ALLOWED"}
    assert wrong_csrf.json() == {"reason_code": "CSRF_TOKEN_INVALID"}
    assert own_list.status_code == 200


def test_unsafe_inputs_fail_with_stable_codes_and_no_partials() -> None:
    sentinel = "DO-NOT-LEAK-SENTINEL"
    cases = [
        ("../secret.pdf", pdf_bytes(sentinel.encode()), PDF_MIME, "FILENAME_SUSPICIOUS"),
        (
            "secret.xls",
            b"\xd0\xcf\x11\xe0",
            "application/vnd.ms-excel",
            "FILE_EXTENSION_NOT_ALLOWED",
        ),
        ("secret.pdf", encrypted_pdf(), PDF_MIME, "PASSWORD_PROTECTED_INPUT"),
        ("secret.pdf", b"PK\x03\x04not-a-pdf", PDF_MIME, "PDF_MAGIC_INVALID"),
    ]
    with TestClient(app, base_url="https://testserver") as client:
        for filename, content, mime, expected in cases:
            session, _capability = create_session(client)
            response = client.post(
                f"/api/sessions/{session['session_id']}/files",
                headers=mutation_headers(session["csrf_token"]),
                data={"role": "report_pdf"},
                files={"file": (filename, content, mime)},
            )
            directory = client.app.state.source_store.root / session["session_id"]
            assert response.json() == {"reason_code": expected}
            assert sentinel not in response.text
            assert list(directory.iterdir()) == []


def test_macro_external_link_and_zip_bomb_workbooks_are_rejected() -> None:
    cases = [
        (xlsx_bytes(extra_entries={"xl/vbaProject.bin": b"macro"}), "MACROS_NOT_ALLOWED"),
        (
            xlsx_bytes(
                content_types=(
                    b'<Types><Override ContentType="application/vnd.ms-excel.'
                    b'sheet.macroEnabled.main+xml"/></Types>'
                )
            ),
            "MACROS_NOT_ALLOWED",
        ),
        (
            xlsx_bytes(
                extra_entries={
                    "xl/_rels/workbook.xml.rels": (
                        b'<Relationships><Relationship TargetMode = "External"/></Relationships>'
                    )
                }
            ),
            "EXTERNAL_LINKS_NOT_ALLOWED",
        ),
        (
            xlsx_bytes(
                extra_entries={
                    "xl/connections.xml": (
                        b'<connections><connection><dbPr connection="https://'
                        b'attacker.invalid"/></connection></connections>'
                    )
                }
            ),
            "EXTERNAL_LINKS_NOT_ALLOWED",
        ),
        (
            xlsx_bytes(extra_entries={"xl/media/bomb.txt": b"0" * 1_000_000}),
            "ZIP_BOMB_DETECTED",
        ),
        (
            xlsx_bytes(extra_entries={"xl/../escape.xml": b"<escape/>"}),
            "ARCHIVE_PATH_SUSPICIOUS",
        ),
        (
            xlsx_bytes(
                extra_entries={
                    "xl/worksheets/data.xml": (
                        b'<worksheet xmlns="http://schemas.openxmlformats.org/'
                        b'spreadsheetml/2006/main"><sheetData><row r="1">'
                        b'<c r="XFE1"><v>1</v></c></row></sheetData></worksheet>'
                    )
                }
            ),
            "WORKBOOK_DIMENSION_LIMIT",
        ),
        (
            xlsx_bytes(
                extra_entries={
                    "xl/_rels/renamed.rels": (
                        b'<Relationships><Relationship Type="http://schemas.'
                        b"openxmlformats.org/officeDocument/2006/relationships/"
                        b'externalLink" Target="local.xml"/></Relationships>'
                    )
                }
            ),
            "EXTERNAL_LINKS_NOT_ALLOWED",
        ),
        (
            xlsx_bytes(
                extra_entries={
                    "xl/worksheets/dtd.xml": (
                        b" " * 5000
                        + b'<!DOCTYPE worksheet [<!ENTITY x "boom">]>'
                        + b"<worksheet>&x;</worksheet>"
                    )
                }
            ),
            "XML_DECLARATION_NOT_ALLOWED",
        ),
    ]
    with TestClient(app, base_url="https://testserver") as client:
        for content, expected in cases:
            session, _capability = create_session(client)
            response = client.post(
                f"/api/sessions/{session['session_id']}/files",
                headers=mutation_headers(session["csrf_token"]),
                data={"role": "workbook"},
                files={"file": ("evidence.xlsx", content, XLSX_MIME)},
            )
            assert response.json() == {"reason_code": expected}
            directory = client.app.state.source_store.root / session["session_id"]
            assert list(directory.iterdir()) == []


def test_oversized_upload_is_bounded_and_partial_is_removed() -> None:
    with TestClient(app, base_url="https://testserver") as client:
        session, _capability = create_session(client)
        client.app.state.source_store.max_pdf_bytes = 32
        response = client.post(
            f"/api/sessions/{session['session_id']}/files",
            headers=mutation_headers(session["csrf_token"]),
            data={"role": "report_pdf"},
            files={"file": ("large.pdf", pdf_bytes(), PDF_MIME)},
        )
        directory = client.app.state.source_store.root / session["session_id"]
        assert response.json() == {"reason_code": "FILE_TOO_LARGE"}
        assert list(directory.iterdir()) == []


def test_request_body_is_rejected_before_multipart_parsing() -> None:
    oversized = b"x" * (21 * 1024 * 1024 + 1)
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/api/sessions/not-a-real-session/files",
            headers=ORIGIN_HEADERS,
            content=oversized,
        )
    assert response.status_code == 413
    assert response.json() == {"reason_code": "REQUEST_TOO_LARGE"}


def test_ttl_startup_and_shutdown_cleanup_preserve_immutable_fixtures(tmp_path: Path) -> None:
    root = tmp_path / "managed"
    store = SourceLibraryStore(root=root, idle_ttl=timedelta(minutes=30))
    stale = root / f"src-{'a' * 24}"
    stale.mkdir(parents=True)
    (stale / "source.pdf").write_bytes(b"private")
    fixture = tmp_path / "immutable-fixture.json"
    fixture.write_text("public", encoding="utf-8")
    store.startup_cleanup()
    assert not stale.exists()
    assert fixture.read_text(encoding="utf-8") == "public"

    old = datetime.now(UTC) - timedelta(minutes=31)
    created, _capability = store.create(now=old)
    assert store.cleanup_expired() == 1
    assert not (root / created.session_id).exists()
    store.shutdown_cleanup()
    assert fixture.exists()


def test_managed_root_and_tombstones_are_bounded(tmp_path: Path) -> None:
    unsafe = tmp_path / "unmarked"
    unsafe.mkdir()
    (unsafe / "unrelated.txt").write_text("keep", encoding="utf-8")
    try:
        SourceLibraryStore(root=unsafe)
    except RuntimeError as error:
        assert "unmarked" in str(error)
    else:
        raise AssertionError("non-empty unmarked root was accepted")
    assert (unsafe / "unrelated.txt").read_text(encoding="utf-8") == "keep"

    store = SourceLibraryStore(root=tmp_path / "managed", max_tombstones=2)
    for _index in range(3):
        created, capability = store.create()
        store.delete(created.session_id, capability, created.csrf_token)
    assert len(store._tombstones) == 2


def test_provider_sent_receipt_flag_changes_only_at_transfer_boundary(tmp_path: Path) -> None:
    store = SourceLibraryStore(root=tmp_path / "managed")
    created, capability = store.create()
    record = store._sessions[created.session_id]
    assert record.source_material_sent_to_provider is False
    store.mark_provider_transfer_started(record)
    receipt = store.delete(created.session_id, capability, created.csrf_token)
    assert receipt.source_material_sent_to_provider is True


def test_public_demo_requires_checked_in_fixture_hash_and_no_key() -> None:
    with TestClient(app, base_url="https://testserver") as client:
        official = client.get("/api/public-demo/apple-fy2025")
        derived = client.get("/api/public-demo/pcg-fy2025")

    assert official.status_code == derived.status_code == 200
    assert official.json()["source_label"] == "Official source fixture"
    assert derived.json()["source_label"] == "Project-derived fixture"
    assert official.json()["verified_cached_output"] is True
    assert official.json()["provider_required"] is False


def test_checked_in_source_library_schemas_match_runtime_contracts() -> None:
    contract_root = Path(__file__).parents[1] / "contracts" / "v1"
    expected = {
        "source-file.schema.json": SourceFileMetadata,
        "source-session.schema.json": SourceSessionStatus,
        "source-session-create.schema.json": SourceSessionCreated,
        "source-deletion-receipt.schema.json": SourceDeletionReceipt,
    }
    for filename, model in expected.items():
        checked_in = json.loads((contract_root / filename).read_text(encoding="utf-8"))
        assert checked_in == model.model_json_schema()


def test_pdf_name_escape_active_content_is_structurally_rejected() -> None:
    with TestClient(app, base_url="https://testserver") as client:
        session, _capability = create_session(client)
        response = client.post(
            f"/api/sessions/{session['session_id']}/files",
            headers=mutation_headers(session["csrf_token"]),
            data={"role": "report_pdf"},
            files={"file": ("active.pdf", escaped_javascript_pdf(), PDF_MIME)},
        )
    assert response.json() == {"reason_code": "PDF_ACTIVE_CONTENT"}


def test_pdf_uri_action_is_structurally_rejected() -> None:
    with TestClient(app, base_url="https://testserver") as client:
        session, _capability = create_session(client)
        response = client.post(
            f"/api/sessions/{session['session_id']}/files",
            headers=mutation_headers(session["csrf_token"]),
            data={"role": "report_pdf"},
            files={"file": ("linked.pdf", uri_action_pdf(), PDF_MIME)},
        )
    assert response.json() == {"reason_code": "PDF_ACTIVE_CONTENT"}


def test_pdf_launch_and_external_goto_actions_are_structurally_rejected() -> None:
    with TestClient(app, base_url="https://testserver") as client:
        for action_name in ("/Launch", "/GoToR"):
            session, _capability = create_session(client)
            response = client.post(
                f"/api/sessions/{session['session_id']}/files",
                headers=mutation_headers(session["csrf_token"]),
                data={"role": "report_pdf"},
                files={
                    "file": ("active.pdf", catalog_action_pdf(action_name), PDF_MIME),
                },
            )
            assert response.json() == {"reason_code": "PDF_ACTIVE_CONTENT"}


def test_internal_open_action_and_large_benign_graph_are_accepted() -> None:
    with TestClient(app, base_url="https://testserver") as client:
        for content in (internal_open_action_pdf(), large_benign_pdf_graph()):
            session, _capability = create_session(client)
            response = client.post(
                f"/api/sessions/{session['session_id']}/files",
                headers=mutation_headers(session["csrf_token"]),
                data={"role": "report_pdf"},
                files={"file": ("report.pdf", content, PDF_MIME)},
            )
            assert response.status_code == 201


def test_interactive_pdf_is_rebuilt_as_a_strict_static_derivative() -> None:
    original = interactive_pdf_requiring_sanitization()
    with TestClient(app, base_url="https://testserver") as client:
        session, _capability = create_session(client)
        response = client.post(
            f"/api/sessions/{session['session_id']}/files",
            headers=mutation_headers(session["csrf_token"]),
            data={"role": "report_pdf"},
            files={"file": ("interactive.pdf", original, PDF_MIME)},
        )
        assert response.status_code == 201

        store = client.app.state.source_store
        record = store._sessions[session["session_id"]]
        stored = record.files[response.json()["file_id"]]
        assert stored.original_path is not None
        assert stored.original_path.read_bytes() == original
        assert stored.sanitization is not None
        assert stored.sanitization.sanitizer_version == PDF_SANITIZER_VERSION
        assert stored.sanitization.original_sha256 == hashlib.sha256(original).hexdigest()
        derivative = stored.path.read_bytes()
        assert stored.sanitization.derivative_sha256 == hashlib.sha256(derivative).hexdigest()
        assert derivative != original
        assert b"SANITIZER-MARKER" not in derivative
        assert b"EMBEDDED-MARKER" not in derivative
        assert (
            store._probe_pdf_structure(
                stored.path,
                time.monotonic(),
                allow_static_sanitization=False,
            )
            is False
        )

        downloaded = client.get(
            f"/api/sessions/{session['session_id']}/files/{response.json()['file_id']}/content"
        )
        assert downloaded.content == derivative
        assert downloaded.content != original

        derivative_path = stored.path
        original_path = stored.original_path
        store.status(record)
        refreshed = record.files[response.json()["file_id"]]
        assert refreshed.original_path == original_path
        assert refreshed.sanitization == stored.sanitization
        store.remove_file(record, response.json()["file_id"])
        assert not derivative_path.exists()
        assert original_path is not None and not original_path.exists()


def test_pdf_decompression_abuse_is_rejected_with_a_stable_reason() -> None:
    with TestClient(app, base_url="https://testserver") as client:
        session, _capability = create_session(client)
        response = client.post(
            f"/api/sessions/{session['session_id']}/files",
            headers=mutation_headers(session["csrf_token"]),
            data={"role": "report_pdf"},
            files={"file": ("bomb.pdf", decompression_bomb_pdf(), PDF_MIME)},
        )
    assert response.json() == {"reason_code": "PDF_DECOMPRESSION_LIMIT"}


def test_pypdf_controlled_messages_are_suppressed(tmp_path: Path, caplog) -> None:
    sentinel = "DO-NOT-LEAK-SENTINEL"
    path = tmp_path / "probe.pdf"
    path.write_bytes(sentinel_log_pdf())
    store = SourceLibraryStore(root=tmp_path / "managed")
    with caplog.at_level(logging.DEBUG):
        store._probe_pdf(path, time.monotonic())
    assert sentinel not in caplog.text


def test_probe_that_exceeds_deadline_is_rejected(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "probe.pdf"
    path.write_bytes(pdf_bytes())
    store = SourceLibraryStore(root=tmp_path / "managed", probe_timeout_seconds=0.001)

    def slow_probe(_path: Path, _started: float) -> None:
        time.sleep(0.01)

    monkeypatch.setattr(store, "_probe_pdf_structure", slow_probe)
    try:
        store._probe_pdf(path, time.monotonic())
    except Exception as error:
        assert getattr(error, "reason_code", None) == "VALIDATION_TIMEOUT"
    else:
        raise AssertionError("probe exceeding its deadline was accepted")


def test_idle_and_absolute_expiry_cannot_be_resurrected(tmp_path: Path) -> None:
    store = SourceLibraryStore(
        root=tmp_path / "managed",
        idle_ttl=timedelta(minutes=30),
        absolute_ttl=timedelta(hours=2),
    )
    now = datetime.now(UTC)
    idle_created, idle_capability = store.create(now=now)
    idle_record = store._sessions[idle_created.session_id]
    idle_record.last_activity_at = now - timedelta(minutes=30)
    try:
        store.authorize(idle_created.session_id, idle_capability)
    except Exception as error:
        assert getattr(error, "reason_code", None) == "SESSION_GONE"
    else:
        raise AssertionError("idle-expired session was revived")
    assert idle_created.session_id not in store._sessions
    assert not idle_record.directory.exists()

    absolute_created, absolute_capability = store.create(now=now - timedelta(hours=2))
    absolute_record = store._sessions[absolute_created.session_id]
    absolute_record.last_activity_at = now
    try:
        store.authorize(absolute_created.session_id, absolute_capability)
    except Exception as error:
        assert getattr(error, "reason_code", None) == "SESSION_GONE"
    else:
        raise AssertionError("absolute-expired session was revived")
    assert absolute_created.session_id not in store._sessions
    assert not absolute_record.directory.exists()


def test_start_rechecks_expiry_and_never_simulates_processing(tmp_path: Path) -> None:
    store = SourceLibraryStore(root=tmp_path / "managed")
    created, capability = store.create()
    record = store.authorize(created.session_id, capability)
    record.last_activity_at = datetime.now(UTC) - timedelta(minutes=31)
    try:
        store.start(record)
    except Exception as error:
        assert getattr(error, "reason_code", None) == "SESSION_GONE"
    else:
        raise AssertionError("expired session entered processing")

    fresh, fresh_capability = store.create()
    fresh_record = store.authorize(fresh.session_id, fresh_capability)
    try:
        store.start(fresh_record)
    except Exception as error:
        assert getattr(error, "reason_code", None) == "REQUIRED_FILES_NOT_READY"
    else:
        raise AssertionError("review without ready files entered processing")
    assert fresh_record.state == "OPEN"


def test_concurrent_upload_cannot_recreate_files_after_delete(tmp_path: Path, monkeypatch) -> None:
    store = SourceLibraryStore(root=tmp_path / "managed")
    created, capability = store.create()
    record = store._sessions[created.session_id]
    probe_started = threading.Event()
    release_probe = threading.Event()
    original_probe = store._probe_pdf

    def blocking_probe(path: Path, started: float) -> None:
        probe_started.set()
        assert release_probe.wait(timeout=5)
        original_probe(path, started)

    monkeypatch.setattr(store, "_probe_pdf", blocking_probe)
    upload = UploadFile(
        file=io.BytesIO(pdf_bytes()),
        filename="report.pdf",
        headers=Headers({"content-type": PDF_MIME}),
    )
    result: dict[str, object] = {}

    def run_upload() -> None:
        result["file"] = asyncio.run(store.upload(record, "report_pdf", upload))

    def run_delete() -> None:
        result["receipt"] = store.delete(created.session_id, capability, created.csrf_token)

    upload_thread = threading.Thread(target=run_upload)
    delete_thread = threading.Thread(target=run_delete)
    upload_thread.start()
    assert probe_started.wait(timeout=5)
    delete_thread.start()
    release_probe.set()
    upload_thread.join(timeout=5)
    delete_thread.join(timeout=5)

    assert not upload_thread.is_alive()
    assert not delete_thread.is_alive()
    assert result["receipt"].status == "complete"
    assert created.session_id not in store._sessions
    assert not record.directory.exists()


def test_concurrent_delete_returns_one_immutable_receipt(tmp_path: Path) -> None:
    store = SourceLibraryStore(root=tmp_path / "managed")
    created, capability = store.create()
    barrier = threading.Barrier(3)
    receipts = []

    def delete_once() -> None:
        barrier.wait()
        receipts.append(store.delete(created.session_id, capability, created.csrf_token))

    threads = [threading.Thread(target=delete_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert len(receipts) == 2
    assert receipts[0] == receipts[1]
