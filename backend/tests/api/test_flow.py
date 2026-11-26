"""End-to-end API flow on the sample tender with the offline provider (no network)."""

import io
import json
import zipfile

from fastapi.testclient import TestClient

from tests.conftest import SAMPLES

PROFILE = json.loads((SAMPLES / "company" / "company_profile.json").read_text())


def _upload_knowledge(client: TestClient) -> None:
    for name, doc_type in (
        ("Nimbus_Company_Profile.pdf", "profile"),
        ("Nimbus_Case_Studies.pdf", "case_study"),
        ("Nimbus_Past_Proposal_Mysuru.docx", "past_proposal"),
    ):
        with (SAMPLES / "company" / name).open("rb") as handle:
            response = client.post(
                "/api/knowledge", files={"files": (name, handle)}, data={"doc_type": doc_type}
            )
        assert response.status_code == 202, response.text


def _create_project(client: TestClient) -> int:
    with (SAMPLES / "hmis-tender" / "rfp.pdf").open("rb") as handle:
        response = client.post(
            "/api/projects", files={"main": ("rfp.pdf", handle, "application/pdf")}
        )
    assert response.status_code == 202, response.text
    job = client.get(f"/api/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "succeeded", job
    return int(response.json()["project_id"])


def test_auth_flow(client: TestClient) -> None:
    assert client.get("/api/projects").status_code == 401
    bad = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "nope"})
    assert bad.status_code == 401
    assert bad.json()["error"]["message"] == "Email or password is incorrect"
    ok = client.post(
        "/api/auth/login", json={"email": "ADMIN@example.com", "password": "test-password"}
    )
    assert ok.status_code == 200
    assert client.get("/api/auth/me").json()["email"] == "admin@example.com"
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_company_validation(auth_client: TestClient) -> None:
    bad = auth_client.put("/api/company", json={"legal_name": "Acme", "gstin": "123"})
    assert bad.status_code == 422
    good = auth_client.put("/api/company", json=PROFILE)
    assert good.status_code == 200
    assert auth_client.get("/api/company").json()["gstin"] == PROFILE["gstin"]


def test_upload_rejects_non_pdf(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/knowledge",
        files={"files": ("x.pdf", io.BytesIO(b"hello"))},
        data={"doc_type": "other"},
    )
    assert response.status_code == 422


def test_knowledge_search_and_delete(auth_client: TestClient) -> None:
    _upload_knowledge(auth_client)
    docs = auth_client.get("/api/knowledge").json()
    assert {d["status"] for d in docs} == {"ready"}
    hits = auth_client.get("/api/knowledge/search", params={"q": "ABDM milestones FHIR"}).json()
    assert hits and hits[0]["filename"] == "Nimbus_Company_Profile.pdf"
    doc_id = docs[0]["id"]
    assert auth_client.delete(f"/api/knowledge/{doc_id}").status_code == 204
    assert all(d["id"] != doc_id for d in auth_client.get("/api/knowledge").json())


def test_full_flow(auth_client: TestClient) -> None:
    auth_client.put("/api/company", json=PROFILE)
    _upload_knowledge(auth_client)
    project_id = _create_project(auth_client)

    project = auth_client.get(f"/api/projects/{project_id}").json()
    assert project["tender_no"] == "DSHM/HMIS/2026/014"
    assert "Hospital Management Information System" in project["title"]
    assert project["counts"]["requirements"] >= 28

    rules = auth_client.get(f"/api/projects/{project_id}/rules").json()
    assert rules["format"]["page_limit"] == 30
    statuses = {e["criterion"]: e["status"] for e in rules["eligibility"]}
    assert (
        statuses["Average annual turnover of at least INR 5 crore in the last 3 financial years"]
        == "met"
    )
    assert statuses["CMMI Level 3 or above"] == "met"

    criteria = auth_client.get(f"/api/projects/{project_id}/criteria").json()
    assert len(criteria) == 6 and sum(c["requirement_count"] for c in criteria) > 10

    assert (
        auth_client.put(
            f"/api/projects/{project_id}/win-themes", json={"themes": ["a", "b", "c", "d"]}
        ).status_code
        == 422
    )
    auth_client.put(
        f"/api/projects/{project_id}/win-themes", json={"themes": ["Live in 38 hospitals"]}
    )

    outline = auth_client.post(f"/api/projects/{project_id}/outline").json()
    assert abs(sum(s["page_budget"] for s in outline) - 30) <= 0.5

    draft = auth_client.post(f"/api/projects/{project_id}/draft").json()
    assert auth_client.get(f"/api/jobs/{draft['job_id']}").json()["status"] == "succeeded"
    rows = auth_client.get(f"/api/projects/{project_id}/requirements").json()
    items = rows["items"]
    drafted = [r for r in items if r["response"]["status"] not in ("gap", "pending")]
    gaps = [r for r in items if r["response"]["status"] == "gap"]
    assert len(drafted) >= 15 and gaps
    assert all(r["response"]["citations"] for r in drafted)
    assert all(r["response"]["answer"] is None for r in gaps)
    assert rows["summary"]["gap"] == len(gaps)

    filtered = auth_client.get(
        f"/api/projects/{project_id}/requirements", params={"status": "gap", "mandatory": True}
    ).json()
    assert all(
        r["type"] == "mandatory" and r["response"]["status"] == "gap" for r in filtered["items"]
    )

    # Approving a gap is refused; approving a drafted answer works and feeds the answer library.
    gap_response = gaps[0]["response"]["id"]
    assert (
        auth_client.patch(f"/api/responses/{gap_response}", json={"approved": True}).status_code
        == 409
    )
    target = drafted[0]
    approve = auth_client.patch(
        f"/api/responses/{target['response']['id']}",
        json={"approved": True, "override_reason": "Checked"},
    )
    assert approve.status_code == 200 and approve.json()["response"]["approved"]
    history = auth_client.get(f"/api/responses/{target['response']['id']}/history").json()
    assert [h["action"] for h in history][:2] == ["approve", "ai_draft"]

    # A high-severity issue blocks approval without a reason.
    edited = auth_client.patch(
        f"/api/responses/{drafted[1]['response']['id']}", json={"answer": "We comply."}
    ).json()
    assert edited["response"]["edited_by_user"]

    validation = auth_client.get(f"/api/projects/{project_id}/validate").json()
    codes = {b["code"] for b in validation["blockers"]}
    assert {"mandatory_gaps", "unapproved"} <= codes
    assert validation["readiness_score"] < 100

    gng = auth_client.put(
        f"/api/projects/{project_id}/go-no-go", json={"competition_rating": 3}
    ).json()
    assert gng["decision"] in ("go", "review", "no_go") and len(gng["reasons"]) >= 4

    conflicts = auth_client.post(f"/api/projects/{project_id}/consistency").json()
    assert isinstance(conflicts, list)

    package = auth_client.post(f"/api/projects/{project_id}/package").json()
    job = auth_client.get(f"/api/jobs/{package['job_id']}").json()
    assert job["status"] == "succeeded", job
    info = auth_client.get(f"/api/projects/{project_id}/package").json()
    names = [f["name"] for f in info["files"]]
    assert any("Technical_Proposal.pdf" in n for n in names)
    assert all(
        n.startswith("DSHM-HMIS-2026-014_NimbusHealth_") or n.startswith("README") for n in names
    )
    archive = auth_client.get(f"/api/projects/{project_id}/package/download")
    assert archive.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive.content)) as zf:
        assert len(zf.namelist()) == len(names) >= 10

    png = auth_client.get(f"/api/projects/{project_id}/requirements/{items[1]['id']}/source.png")
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"

    # Re-analysing a project that already has drafts, an outline and criteria must work.
    again = auth_client.post(f"/api/projects/{project_id}/reanalyse").json()
    rerun = auth_client.get(f"/api/jobs/{again['job_id']}").json()
    assert rerun["status"] == "succeeded", rerun
    assert auth_client.get(f"/api/projects/{project_id}").json()["counts"]["requirements"] >= 28


def test_addendum_diff(auth_client: TestClient) -> None:
    auth_client.put("/api/company", json=PROFILE)
    _upload_knowledge(auth_client)
    project_id = _create_project(auth_client)
    auth_client.post(f"/api/projects/{project_id}/draft")
    with (SAMPLES / "hmis-tender" / "corrigendum-1.pdf").open("rb") as handle:
        response = auth_client.post(
            f"/api/projects/{project_id}/addenda", files={"file": ("corrigendum-1.pdf", handle)}
        )
    job = auth_client.get(f"/api/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "succeeded", job
    assert (
        job["counts"]["modified"] == 2
        and job["counts"]["added"] == 1
        and job["counts"]["removed"] == 1
    )

    changed = auth_client.get(
        f"/api/projects/{project_id}/requirements",
        params={"version_status": "modified,added,removed"},
    ).json()["items"]
    by_status = {r["version_status"]: r for r in changed}
    modified = [r for r in changed if r["version_status"] == "modified"]
    assert any("99.9%" in r["text"] and "99.5%" in (r["previous_text"] or "") for r in modified)
    assert "e-Hospital dashboard" in by_status["added"]["text"]
    assert "biometric" in by_status["removed"]["text"]
    diff = auth_client.get(f"/api/requirements/{modified[0]['id']}/diff").json()
    assert {"insert", "delete"} <= {d["op"] for d in diff}
    project = auth_client.get(f"/api/projects/{project_id}").json()
    assert project["deadline"].startswith("2026-12-22")
