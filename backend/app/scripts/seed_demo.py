"""Load the demo dataset: company profile, knowledge base, and one analysed + drafted project.

Usage (from backend/):
    uv run python -m app.scripts.seed_demo            # company + knowledge + drafted project
    uv run python -m app.scripts.seed_demo --only-company
    uv run python -m app.scripts.seed_demo --stage analyse   # stop after extraction
"""

import argparse
import json
import shutil
import uuid
from pathlib import Path

from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.db import get_engine, run_migrations
from app.jobs.runner import JobRunner
from app.main import seed_admin  # also registers every job kind
from app.models import Company, KnowledgeDoc, Project, RfpFile, WinTheme
from app.pipeline.extras import generate_outline
from app.services.company import get_or_create_company

SAMPLES = Path(__file__).resolve().parents[3] / "samples"
KNOWLEDGE = [
    ("Nimbus_Company_Profile.pdf", "profile", "unknown"),
    ("Nimbus_Case_Studies.pdf", "case_study", "unknown"),
    ("Nimbus_Past_Proposal_Mysuru.docx", "past_proposal", "won"),
]
WIN_THEMES = [
    "Live in 38 hospitals today, including 12 district hospitals for Mysuru Health Society",
    "ABDM M1-M3 certified and FHIR R4 ready from day one",
    "Kannada user interface and on-site engineers for fast adoption",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only-company", action="store_true")
    parser.add_argument("--stage", choices=["analyse", "draft"], default="draft")
    args = parser.parse_args()

    if not (SAMPLES / "hmis-tender" / "rfp.pdf").exists():
        raise SystemExit("Samples missing: run `uv run python scripts/make_samples.py` first")

    settings = get_settings().model_copy(update={"jobs_inline": True})
    run_migrations(settings)
    engine = get_engine(settings)
    runner = JobRunner(engine, settings)
    profile = json.loads((SAMPLES / "company" / "company_profile.json").read_text())

    with Session(engine) as session:
        seed_admin(settings, session)
        company = get_or_create_company(session)
        for key, value in profile.items():
            setattr(company, key, value)
        session.add(company)
        session.commit()
        assert company.id is not None
        existing = {
            d.filename
            for d in session.exec(
                select(KnowledgeDoc).where(col(KnowledgeDoc.company_id) == company.id)
            ).all()
        }
        doc_ids: list[int] = []
        for filename, doc_type, outcome in KNOWLEDGE:
            if filename in existing:
                continue
            target = settings.files_dir / "knowledge" / f"{uuid.uuid4().hex[:12]}_{filename}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(SAMPLES / "company" / filename, target)
            doc = KnowledgeDoc(
                company_id=company.id,
                filename=filename,
                stored_path=str(target),
                doc_type=doc_type,
                outcome=outcome,
            )
            session.add(doc)
            session.commit()
            assert doc.id is not None
            doc_ids.append(doc.id)
    if doc_ids:
        job = runner.submit("index_knowledge", {"doc_ids": doc_ids})
        print(f"Knowledge base: indexed {len(doc_ids)} document(s) ({job.status})")
    if args.only_company:
        return

    with Session(engine) as session:
        owner = session.exec(select(Company)).first()
        assert owner is not None and owner.id is not None
        project = Project(company_id=owner.id, title="", status="analysing")
        session.add(project)
        session.commit()
        assert project.id is not None
        project_id = project.id
        target = settings.files_dir / "projects" / str(project_id) / "rfp.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(SAMPLES / "hmis-tender" / "rfp.pdf", target)
        session.add(
            RfpFile(project_id=project_id, role="main", filename="rfp.pdf", stored_path=str(target))
        )
        for order, text in enumerate(WIN_THEMES):
            session.add(WinTheme(project_id=project_id, text=text, order=order))
        session.commit()

    job = runner.submit("analyse", {"project_id": project_id}, project_id=project_id)
    print(f"Analyse: {job.status} {job.counts} {job.error or ''}")
    if job.status != "succeeded" or args.stage == "analyse":
        return
    with Session(engine) as session:
        seeded = session.get(Project, project_id)
        assert seeded is not None
        generate_outline(session, seeded)
    job = runner.submit("draft", {"project_id": project_id}, project_id=project_id)
    print(f"Draft: {job.status} {job.counts} {job.error or ''}")
    print(f"Demo project id: {project_id}")


if __name__ == "__main__":
    main()
