import json
from pathlib import Path

from app.llm.offline import extract_criteria, extract_requirements, extract_rules
from app.pipeline.chunk import build_chunks
from app.pipeline.parse import parse_document
from app.services.files import sniff_kind
from tests.conftest import SAMPLES

RFP = SAMPLES / "hmis-tender" / "rfp.pdf"


def _chunks() -> list:  # type: ignore[type-arg]
    return build_chunks(parse_document(RFP, "pdf"))


def test_parse_keeps_pages_and_tables() -> None:
    doc = parse_document(RFP, "pdf")
    assert len(doc.pages) >= 6
    rows = [line.text for page in doc.pages for line in page.lines if line.is_table_row]
    assert any(r.startswith("M2 | Operation theatre scheduling") for r in rows)
    assert any("Max Marks" in r for r in rows)
    # running footers are removed
    assert not any("Page 3 of" in line.text for page in doc.pages for line in page.lines)


def test_chunks_follow_top_level_sections() -> None:
    headings = [c.heading for c in _chunks()]
    assert "4. Scope of Work" in headings
    assert "4.2 Technical Requirements" in headings  # second-level sections are their own chunks
    assert "Annexure-A: Bid Submission Letter" in headings
    assert not any(h.endswith(".") for h in headings)


def test_requirements_include_clauses_and_table_rows() -> None:
    items = [
        item
        for chunk in _chunks()
        if chunk.heading.startswith("4.")
        for item in extract_requirements(
            {"chunk_text": chunk.text, "section_path": chunk.section_path}
        ).requirements
    ]
    texts = [i.text for i in items]
    assert any("ABHA" in t for t in texts)
    assert any("blood bank" in t.lower() for t in texts)
    assert not any(t.startswith("The Mission shall") for t in texts)  # buyer obligation skipped
    optional = [i for i in items if i.type == "optional"]
    assert any("mobile applications" in i.text for i in optional)
    assert all(i.section_path for i in items)


def test_rules_extraction_reads_instructions() -> None:
    chunks = _chunks()
    text = "\n\n".join(
        c.text for c in chunks if c.heading.startswith(("Preamble", "2", "3.", "Annexure"))
    )
    rules = extract_rules({"text": text})
    assert rules.tender_no == "DSHM/HMIS/2026/014"
    assert rules.deadline == "2026-12-15T15:00:00+05:30"
    assert rules.format.page_limit == 30
    assert rules.format.font == "Arial"
    assert rules.emd is not None and rules.emd.amount_inr == 200000
    assert len(rules.eligibility) == 6
    assert {f.code for f in rules.forms} >= {"Annexure-A", "Annexure-B", "Annexure-C"}
    assert "name_of_bidder" in next(f for f in rules.forms if f.code == "Annexure-A").fields
    assert [c.name for c in rules.covers] == ["Cover-1 Technical Bid", "Cover-2 Financial Bid"]


def test_criteria_extraction() -> None:
    evaluation = next(c for c in _chunks() if c.heading.startswith("5."))
    criteria = extract_criteria({"text": evaluation.text})
    assert criteria.qcbs_split == "70:30"
    assert criteria.min_qualifying_marks == 70
    assert sum(c.max_marks or 0 for c in criteria.criteria) == 100


def test_offline_recall_against_gold() -> None:
    from app.pipeline.textutil import similarity

    gold = json.loads((SAMPLES / "hmis-tender" / "gold_requirements.json").read_text())
    found: list[str] = []
    for chunk in _chunks():
        found += [
            i.text
            for i in extract_requirements(
                {"chunk_text": chunk.text, "section_path": chunk.section_path}
            ).requirements
        ]
    matched = [g for g in gold if any(similarity(str(g["text"]), f) >= 0.85 for f in found)]
    assert len(matched) / len(gold) >= 0.9


def test_sniff_kind(tmp_path: Path) -> None:
    fake = tmp_path / "renamed.pdf"
    fake.write_text("not really a pdf")
    assert sniff_kind(fake) is None
    assert sniff_kind(RFP) == "pdf"
    assert sniff_kind(SAMPLES / "company" / "Nimbus_Past_Proposal_Mysuru.docx") == "docx"
