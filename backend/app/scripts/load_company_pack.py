"""Load a folder of company documents into the knowledge base (and optionally the company profile).

The folder may contain manifest.json ({filename: {doc_type, outcome}}) and company_profile.json.
Documents already in the knowledge base (same filename) are skipped. With --apply-profile the current
profile is backed up to backend/data/company_profile_backup.json first; --keep-name keeps the current
legal and short name.

Usage (from backend/):
    uv run python -m app.scripts.load_company_pack ../samples/nlp-company --apply-profile --keep-name
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
from app.models import KnowledgeDoc
from app.services.company import get_or_create_company
from app.services.files import sniff_kind

PROFILE_FIELDS = (
    "legal_name", "short_name", "address", "gstin", "pan", "udyam_no", "signatory_name",
    "signatory_designation", "email", "phone", "website", "year_established", "turnover",
    "certifications", "style_sample",
)  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("folder", type=Path)
    parser.add_argument(
        "--apply-profile", action="store_true", help="overwrite the company profile"
    )
    parser.add_argument(
        "--keep-name", action="store_true", help="keep the current legal/short name"
    )
    args = parser.parse_args()
    folder: Path = args.folder.resolve()
    if not folder.is_dir():
        raise SystemExit(f"Not a folder: {folder}")

    settings = get_settings().model_copy(update={"jobs_inline": True})
    run_migrations(settings)
    engine = get_engine(settings)
    manifest = (
        json.loads((folder / "manifest.json").read_text())
        if (folder / "manifest.json").exists()
        else {}
    )

    with Session(engine) as session:
        seed_admin(settings, session)
        company = get_or_create_company(session)
        assert company.id is not None
        if args.apply_profile and (folder / "company_profile.json").exists():
            backup = settings.data_dir / "company_profile_backup.json"
            backup.write_text(
                json.dumps({f: getattr(company, f) for f in PROFILE_FIELDS}, indent=2, default=str)
            )
            profile = json.loads((folder / "company_profile.json").read_text())
            for field in PROFILE_FIELDS:
                if field in profile and not (
                    args.keep_name and field in ("legal_name", "short_name")
                ):
                    setattr(company, field, profile[field])
            session.add(company)
            session.commit()
            print(f"Company profile updated (previous profile saved to {backup})")

        existing = {
            d.filename
            for d in session.exec(
                select(KnowledgeDoc).where(col(KnowledgeDoc.company_id) == company.id)
            ).all()
        }
        doc_ids: list[int] = []
        for path in sorted(folder.iterdir()):
            if (
                path.suffix.lower() not in (".pdf", ".docx")
                or path.name in existing
                or not sniff_kind(path)
            ):
                continue
            meta = manifest.get(path.name, {})
            target = settings.files_dir / "knowledge" / f"{uuid.uuid4().hex[:12]}_{path.name}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(path, target)
            doc = KnowledgeDoc(
                company_id=company.id,
                filename=path.name,
                stored_path=str(target),
                doc_type=meta.get("doc_type", "other"),
                outcome=meta.get("outcome", "unknown"),
            )
            session.add(doc)
            session.commit()
            assert doc.id is not None
            doc_ids.append(doc.id)

    if not doc_ids:
        print("No new documents to load.")
        return
    job = JobRunner(engine, settings).submit("index_knowledge", {"doc_ids": doc_ids})
    print(f"Indexed {len(doc_ids)} document(s): {job.status} {job.counts}")


if __name__ == "__main__":
    main()
