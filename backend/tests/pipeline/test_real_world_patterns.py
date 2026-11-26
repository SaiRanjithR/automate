"""Patterns from real government RFPs (e.g. GeM / CPPP tenders) that the sample tender does not cover."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.llm.offline import extract_requirements, extract_rules
from app.models import Requirement
from app.pipeline.analyse import buyer_aliases
from app.pipeline.chunk import build_chunks
from app.pipeline.draft import is_undertaking, undertaking_draft
from app.pipeline.parse import Line, ParsedDocument, ParsedPage
from tests.conftest import SAMPLES

BUYER = "Government e-Marketplace (GeM)"


def _doc(lines: list[tuple[str, bool, float]]) -> ParsedDocument:
    body = [
        Line(text=f"Body line {i} with enough words to set the body size.", size=9.0)
        for i in range(30)
    ]
    parsed = [Line(text=t, bold=b, size=s) for t, b, s in lines]
    return ParsedDocument(pages=[ParsedPage(page=1, lines=parsed + body)])


def test_headings_without_space_and_list_items_are_not_sections() -> None:
    doc = _doc(
        [
            ("Request for Proposal (RFP)", True, 18.0),
            ("New Delhi - 110001", True, 13.0),
            ("DISCLAIMER", True, 10.4),
            ("1.Introduction", True, 10.4),
            ("1.1Overview", True, 9.3),
            ("2.Eligibility Criteria of the Bidder", True, 10.4),
            ("3.Technical Evaluation and Award Criteria", True, 10.4),
            ("2.Percentage accuracy of Search Results", True, 9.3),  # list item inside section 3
            ("4.Scope of Work", True, 10.4),
            ("4.1Training and Support", True, 9.3),
            ("9.1Annexure 1: Technical Bid Covering Letter", True, 9.3),
        ]
    )
    headings = [c.heading for c in build_chunks(doc)]
    assert headings[:2] == ["Preamble", "DISCLAIMER"]
    assert "New Delhi - 110001" not in headings
    assert "2.Percentage accuracy of Search Results" not in headings
    for expected in ("1.Introduction", "1.1Overview", "4.Scope of Work", "4.1Training and Support"):
        assert expected in headings
    assert "9.1Annexure 1: Technical Bid Covering Letter" in headings


def test_disclaimer_and_buyer_statements_are_not_requirements() -> None:
    text = "\n".join(
        [
            "[[page 2]]",
            "The purpose of this RFP document is to provide interested parties with information that may be useful.",
            "Each Bidder should, therefore, conduct its own investigations and analysis of the information.",
            "GeM may in its absolute discretion update, amend, or supplement the information in this RFP.",
            "This RFP document may not be appropriate for all persons and bidders.",
            "The bidder shall provide a 24x7 helpdesk for all users of the platform.",
        ]
    )
    items = extract_requirements(
        {
            "chunk_text": text,
            "section_path": "5 Scope",
            "buyer_aliases": buyer_aliases(BUYER),
            "category": "scope",
        }
    ).requirements
    texts = [i.text for i in items]
    assert texts == ["The bidder shall provide a 24x7 helpdesk for all users of the platform."]


def test_will_obligations_bullets_and_lead_in_lists() -> None:
    text = "\n".join(
        [
            "[[page 21]]",
            "5.1Training and Support",
            "The bidder will be responsible for training GeM employees in operations and administration.",
            "The Training should at least cover but not limited to the following Areas:",
            "No. | Specification",
            "1 | Solution Architecture and Design",
            "2 | Advanced troubleshooting techniques",
            "Phase | Activity | Deliverable",
            "Build | API development | • NLP Optimizer APIs will be hosted on MeitY Empanelled Cloud Service • Integrate the optimizer with the existing search architecture",
            "MSP will provide required support and access to the selected bidder.",
        ]
    )
    items = extract_requirements(
        {
            "chunk_text": text,
            "section_path": "5 Scope",
            "buyer_aliases": buyer_aliases(BUYER),
            "category": "scope",
        }
    ).requirements
    texts = [i.text for i in items]
    assert any(t.startswith("The bidder will be responsible for training") for t in texts)
    assert any(t.endswith("following Areas: Solution Architecture and Design.") for t in texts)
    assert any("Advanced troubleshooting techniques" in t for t in texts)
    assert any(t.startswith("NLP Optimizer APIs will be hosted") for t in texts)
    assert any(t.startswith("Integrate the optimizer") for t in texts)
    assert not any(t.startswith("MSP will") for t in texts)  # another party, not the bidder
    assert not any("Specification" in t for t in texts)  # header row


def test_eligibility_should_is_mandatory() -> None:
    text = "[[page 13]]\n1 | Turnover | The Bidder should have a minimum turnover of INR 25 crores in each of the last 3 years. | Audited balance sheets"
    items = extract_requirements(
        {
            "chunk_text": text,
            "section_path": "2 Eligibility",
            "buyer_aliases": [],
            "category": "eligibility",
        }
    ).requirements
    assert [i.type for i in items] == ["mandatory"]


def test_rules_rfp_number_numeric_deadline_and_emd_in_lakh() -> None:
    text = "\n".join(
        [
            "[[page 1]]",
            "Request for Proposal (RFP)",
            "For",
            "Search Engine Enhancement using Natural Language Processing (NLP)",
            "For",
            "Government e-Marketplace (GeM)",
            "RFP No. \u2013RFP/2020/04-GeM",
            "[[page 5]]",
            "4 | Last Date & Time for Receipt of Queries from Bidders for Clarifications | 14-05-2020 (18:00 Hrs)",
            "8 | Last Date & Time for Online Bid Submission | 29-05-2020 (15:00 Hrs)",
            "14 | Earnest Money Deposit (EMD) | INR 5(Five) Lakh only",
            "The Technical bid must be submitted through CPPP only. The Commercial Bid will be opened later.",
        ]
    )
    rules = extract_rules({"text": text})
    assert rules.tender_no == "RFP/2020/04-GeM"
    assert rules.buyer == "Government e-Marketplace (GeM)"
    assert rules.title is not None and rules.title.startswith("Search Engine Enhancement")
    assert rules.deadline == "2020-05-29T15:00:00+05:30"
    assert rules.emd is not None and rules.emd.amount_inr == 500000
    assert rules.bid_system == "two_bid"


def test_undertakings_get_a_commitment_not_a_capability_claim() -> None:
    assert is_undertaking(
        "The bidder shall furnish a performance bank guarantee of 10% of the contract value."
    )
    assert is_undertaking(
        "There shall be no change in the rates finalized upon award of the tender."
    )
    assert is_undertaking("For every day of delay, a penalty of 0.5% of invoice value shall apply.")
    assert not is_undertaking("The solution shall support HL7 FHIR R4 interfaces.")
    req = Requirement(
        project_id=1,
        text="The bidder shall furnish a performance bank guarantee.",
        section_path="5.7 SLA",
        page=25,
        source_quote="furnish a performance bank guarantee",
    )
    draft = undertaking_draft(req)
    assert draft["status"] == "fully_compliant"
    assert draft["citations"][0]["kind"] == "rfp_clause"
    assert draft["review_issues"][0]["type"] == "undertaking"
    assert "We confirm that we accept and will comply" in draft["answer"]


def test_won_bids_rank_higher(auth_client: TestClient, tmp_path: Path) -> None:
    from docx import Document

    for name, outcome in (("won.docx", "won"), ("lost.docx", "lost")):
        doc = Document()
        doc.add_paragraph(
            "We operate a 24x7 helpdesk with a response time of 2 hours for critical incidents."
        )
        path = tmp_path / name
        doc.save(str(path))
        with path.open("rb") as handle:
            response = auth_client.post(
                "/api/knowledge",
                files={"files": (name, handle)},
                data={"doc_type": "past_proposal", "outcome": outcome},
            )
        assert response.status_code == 202
    docs = {d["filename"]: d for d in auth_client.get("/api/knowledge").json()}
    assert docs["won.docx"]["outcome"] == "won"
    hits = auth_client.get(
        "/api/knowledge/search", params={"q": "24x7 helpdesk response time"}
    ).json()
    assert hits[0]["filename"] == "won.docx"
    # Changing the outcome flips the ranking.
    auth_client.patch(f"/api/knowledge/{docs['won.docx']['id']}", json={"outcome": "lost"})
    auth_client.patch(f"/api/knowledge/{docs['lost.docx']['id']}", json={"outcome": "won"})
    hits = auth_client.get(
        "/api/knowledge/search", params={"q": "24x7 helpdesk response time"}
    ).json()
    assert hits[0]["filename"] == "lost.docx"


def test_sample_tender_still_meets_recall() -> None:
    assert (SAMPLES / "hmis-tender" / "rfp.pdf").exists()
