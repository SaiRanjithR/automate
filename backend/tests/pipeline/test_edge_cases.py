"""Edge cases from TASKS 4A.2: DOCX RFP, scanned page, no evaluation section, empty knowledge base."""

from pathlib import Path

import pymupdf
from docx import Document
from fastapi.testclient import TestClient

from app.pipeline.parse import parse_document


def _docx_tender(path: Path) -> Path:
    doc = Document()
    doc.add_heading("Request for Proposal for Campus Wi-Fi Network", level=0)
    doc.add_paragraph("Tender No: UNI/IT/2026/07")
    doc.add_heading("1. Instructions to Bidders", level=1)
    doc.add_paragraph("1.1 The last date for bid submission is 5 January 2099, 17:00 IST.")
    doc.add_heading("2. Scope of Work", level=1)
    doc.add_paragraph("2.1 The bidder shall install 400 Wi-Fi access points across the campus.")
    doc.add_paragraph("2.2 The bidder shall provide 3 years of on-site warranty support.")
    table = doc.add_table(rows=2, cols=3)
    for i, text in enumerate(["Ref", "Item", "Priority"]):
        table.rows[0].cells[i].text = text
    for i, text in enumerate(["W1", "Guest network with captive portal login", "Mandatory"]):
        table.rows[1].cells[i].text = text
    doc.save(str(path))
    return path


def _upload(client: TestClient, path: Path, mime: str) -> dict:  # type: ignore[type-arg]
    with path.open("rb") as handle:
        response = client.post("/api/projects", files={"main": (path.name, handle, mime)})
    assert response.status_code == 202, response.text
    job = client.get(f"/api/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "succeeded", job
    return response.json()


def test_docx_rfp_without_evaluation_section(auth_client: TestClient, tmp_path: Path) -> None:
    started = _upload(
        auth_client,
        _docx_tender(tmp_path / "wifi.docx"),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    project_id = started["project_id"]
    rows = auth_client.get(f"/api/projects/{project_id}/requirements").json()["items"]
    texts = " ".join(r["text"] for r in rows)
    assert "400 Wi-Fi access points" in texts and "captive portal" in texts
    assert auth_client.get(f"/api/projects/{project_id}/criteria").json() == []
    project = auth_client.get(f"/api/projects/{project_id}").json()
    assert project["deadline"].startswith("2099-01-05")
    # No scoring criteria: the outline still builds with default sections and the default page limit.
    outline = auth_client.post(f"/api/projects/{project_id}/outline").json()
    assert [s["title"] for s in outline] == [
        "Executive Summary",
        "Company Profile",
        "General Compliance",
    ]


def test_empty_knowledge_base_makes_every_row_a_gap(
    auth_client: TestClient, tmp_path: Path
) -> None:
    started = _upload(auth_client, _docx_tender(tmp_path / "wifi.docx"), "application/octet-stream")
    project_id = started["project_id"]
    job = auth_client.post(f"/api/projects/{project_id}/draft").json()
    assert auth_client.get(f"/api/jobs/{job['job_id']}").json()["status"] == "succeeded"
    items = auth_client.get(f"/api/projects/{project_id}/requirements").json()["items"]
    assert items and all(r["response"]["status"] == "gap" for r in items)
    assert all(r["response"]["answer"] is None for r in items)


def test_scanned_page_does_not_crash(tmp_path: Path) -> None:
    path = tmp_path / "scanned.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 100), False)
    pix.clear_with(200)
    page.insert_image(page.rect, pixmap=pix)
    doc.save(path)
    parsed = parse_document(path, "pdf", ocr=True)
    assert len(parsed.pages) == 1
    # Without Tesseract the page is kept (empty) and a warning explains why.
    if not parsed.pages[0].lines:
        assert parsed.warnings and "OCR" in parsed.warnings[0]


def test_passed_deadline_is_a_blocker(auth_client: TestClient, tmp_path: Path) -> None:
    doc = Document()
    doc.add_heading("Request for Proposal for Printers", level=0)
    doc.add_heading("1. Instructions to Bidders", level=1)
    doc.add_paragraph("1.1 The last date for bid submission is 5 January 2020, 17:00 IST.")
    doc.add_heading("2. Scope of Work", level=1)
    doc.add_paragraph("2.1 The bidder shall supply 20 laser printers with toner.")
    path = tmp_path / "old.docx"
    doc.save(str(path))
    project_id = _upload(auth_client, path, "application/octet-stream")["project_id"]
    blockers = auth_client.get(f"/api/projects/{project_id}/validate").json()["blockers"]
    assert any(b["code"] == "deadline" for b in blockers)
