from __future__ import annotations

from decimal import Decimal
from io import BytesIO

import fitz
from fastapi.testclient import TestClient
from openpyxl import Workbook
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject

from proofline.api import app
from proofline.source_library import PDF_MIME, PDF_SANITIZER_WARNING, XLSX_MIME

ORIGIN_HEADERS = {"Origin": "https://testserver", "Sec-Fetch-Site": "same-origin"}


def _pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((48, 48), text, fontsize=11)
    content = document.tobytes()
    document.close()
    return content


def _interactive_pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((48, 48), text, fontsize=11)
    base = document.tobytes()
    document.close()
    writer = PdfWriter()
    writer.append_pages_from_reader(PdfReader(BytesIO(base)))
    writer.add_uri(0, "https://example.invalid/removed", RectangleObject((48, 80, 220, 100)))
    writer.add_js("app.alert('removed')")
    writer.add_attachment("removed.txt", b"removed")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _xlsx(rows: list[list[object]], title: str) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _headers(csrf_token: str) -> dict[str, str]:
    return {**ORIGIN_HEADERS, "X-Proofline-CSRF": csrf_token}


def _analyze(client: TestClient, pdf_content: bytes, workbook_content: bytes) -> dict:
    created = client.post("/api/sessions", headers=ORIGIN_HEADERS)
    assert created.status_code == 201
    session = created.json()
    headers = _headers(session["csrf_token"])
    pdf = client.post(
        f"/api/sessions/{session['session_id']}/files",
        headers=headers,
        data={"role": "report_pdf"},
        files={"file": ("claims.pdf", pdf_content, PDF_MIME)},
    )
    workbook = client.post(
        f"/api/sessions/{session['session_id']}/files",
        headers=headers,
        data={"role": "workbook"},
        files={"file": ("facts.xlsx", workbook_content, XLSX_MIME)},
    )
    assert pdf.status_code == workbook.status_code == 201
    result = client.post(f"/api/sessions/{session['session_id']}/analysis", headers=headers)
    assert result.status_code == 200, result.text
    return result.json()


def _metric_value(analysis: dict, metric_id: str) -> Decimal:
    result = next(item for item in analysis["metric_results"] if item["metric_id"] == metric_id)
    assert result["result"] is not None
    return Decimal(result["result"])


def test_uploaded_issuer_analysis_is_dynamic_and_cited_for_2026_input() -> None:
    first_workbook = _xlsx(
        [
            ["Issuer", "Alpine Robotics SE"],
            ["Entity scope", "Alpine Robotics SE consolidated"],
            ["Currency", "EUR"],
            ["Units", "thousands"],
            ["Restatement basis", "not restated"],
            ["Line item", 2025, 2026],
            ["Revenue", 1_000, 1_200],
            ["Operating profit", 150, 240],
            ["Total current assets", 400, 500],
            ["Total current liabilities", 200, 250],
            ["Net cash from operating activities", 260, 320],
            ["Capital expenditures", "(80)", "(100)"],
        ],
        "Consolidated statement",
    )
    changed_workbook = _xlsx(
        [
            ["Issuer", "Alpine Robotics SE"],
            ["Entity scope", "Alpine Robotics SE consolidated"],
            ["Currency", "EUR"],
            ["Units", "thousands"],
            ["Restatement basis", "not restated"],
            ["Line item", 2025, 2026],
            ["Revenue", 1_000, 1_500],
            ["Operating profit", 150, 300],
            ["Total current assets", 400, 600],
            ["Total current liabilities", 200, 300],
            ["Net cash from operating activities", 260, 360],
            ["Capital expenditures", "(80)", "(120)"],
        ],
        "Consolidated statement",
    )
    claims = _pdf(
        "Issuer: Alpine Robotics SE\n"
        "Financial report. Consolidated statements. Amounts in EUR thousands.\n"
        "Revenue grew 50% for 2026.\n"
        "Operating margin was 20% for 2026.\n"
        "Current ratio was 2 for 2026.\n"
        "Project-defined FCF margin was 16% for 2026."
    )

    with TestClient(app, base_url="https://testserver") as client:
        first = _analyze(client, claims, first_workbook)
        changed = _analyze(client, claims, changed_workbook)

    # The PDF claim remains 50% while the workbook changes; the response is computed from the
    # uploaded workbook and reports the resulting contradiction rather than fixture output.
    assert (
        first["documents"][0]["issuer"] == changed["documents"][0]["issuer"] == "Alpine Robotics SE"
    )
    assert _metric_value(first, "revenue_growth_yoy") == Decimal("0.2")
    assert _metric_value(changed, "revenue_growth_yoy") == Decimal("0.5")
    assert first["source_spans"] and changed["source_spans"]
    assert {finding["classification"] for finding in changed["findings"]} >= {"supported"}
    assert all(
        observation["source_span_id"].startswith("span:") for observation in changed["observations"]
    )


def test_malaysian_transposed_issuer_and_myr_currency_are_not_fixture_bound() -> None:
    workbook = _xlsx(
        [
            ["Reporting entity", "Kestrel Logistics Berhad"],
            ["Scope", "Kestrel Logistics Berhad consolidated group"],
            ["Reporting currency", "MYR"],
            ["Scale", "millions"],
            ["Restatement status", "restated"],
            [],
            [
                "Period",
                "Net sales",
                "Operating income",
                "Current assets",
                "Current liabilities",
                "Operating cash flow",
                "Purchase of property, plant and equipment",
            ],
            ["2025-12-31", 800, 80, 300, 150, 120, -40],
            ["2026-12-31", 920, -115, 360, 180, 150, -50],
        ],
        "Metrics across columns",
    )
    claims = _pdf(
        "Issuer: Kestrel Logistics Berhad\n"
        "Financial report. Consolidated group statements. Amounts in MYR millions.\n"
        "Revenue grew 15% for 2026.\n"
        "Operating margin was -12.5% for 2026.\n"
        "Current ratio was 2 for 2026.\n"
        "Project-defined FCF margin was 10.8695652174% for 2026."
    )

    with TestClient(app, base_url="https://testserver") as client:
        analysis = _analyze(client, claims, workbook)

    assert {document["issuer"] for document in analysis["documents"]} == {
        "Kestrel Logistics Berhad"
    }
    assert {observation["currency"] for observation in analysis["observations"]} == {"MYR"}
    assert _metric_value(analysis, "revenue_growth_yoy") == Decimal("0.15")
    assert _metric_value(analysis, "operating_margin") == Decimal("-0.125")
    assert len(analysis["claims"]) == 4
    assert all(claim["source_span_id"].startswith("span:") for claim in analysis["claims"])


def test_unsupported_or_ambiguous_upload_fails_closed_without_fixture_fallback() -> None:
    workbook = _xlsx(
        [
            ["Issuer", "Unmapped Works"],
            ["Entity scope", "Unmapped Works consolidated"],
            ["Currency", "USD"],
            ["Units", "thousands"],
            ["Restatement basis", "not restated"],
            ["Line item", 2025, 2026],
            ["Gross sales", 100, 110],
        ],
        "Unsupported statement",
    )
    with TestClient(app, base_url="https://testserver") as client:
        created = client.post("/api/sessions", headers=ORIGIN_HEADERS).json()
        headers = _headers(created["csrf_token"])
        client.post(
            f"/api/sessions/{created['session_id']}/files",
            headers=headers,
            data={"role": "report_pdf"},
            files={"file": ("claims.pdf", _pdf("Gross sales increased."), PDF_MIME)},
        )
        client.post(
            f"/api/sessions/{created['session_id']}/files",
            headers=headers,
            data={"role": "workbook"},
            files={"file": ("facts.xlsx", workbook, XLSX_MIME)},
        )
        result = client.post(f"/api/sessions/{created['session_id']}/analysis", headers=headers)

    assert result.status_code == 422
    assert result.json() == {"reason_code": "WORKBOOK_MAPPING_REQUIRED"}


def test_static_derivative_warning_forces_uncertain_analysis() -> None:
    workbook = _xlsx(
        [
            ["Issuer", "Alpine Robotics SE"],
            ["Entity scope", "Alpine Robotics SE consolidated"],
            ["Currency", "EUR"],
            ["Units", "thousands"],
            ["Restatement basis", "not restated"],
            ["Line item", 2025, 2026],
            ["Revenue", 1_000, 1_200],
        ],
        "Consolidated statement",
    )
    report = _interactive_pdf(
        "Issuer: Alpine Robotics SE\n"
        "Financial report. Consolidated statements. Amounts in EUR thousands.\n"
        "Revenue grew 20% for 2026."
    )

    with TestClient(app, base_url="https://testserver") as client:
        analysis = _analyze(client, report, workbook)

    assert {finding["classification"] for finding in analysis["findings"]} == {"uncertain"}
    assert all(
        PDF_SANITIZER_WARNING in claim["extraction_warnings"] for claim in analysis["claims"]
    )
