import io
from pathlib import Path
from typing import Annotated, Any

import pymupdf
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlmodel import Session, col, delete, func, select

from app.api.jobs import job_out
from app.core.deps import CurrentUser, SessionDep, SettingsDep
from app.core.errors import NotFoundError, ValidationFailedError
from app.jobs.runner import JobRunner
from app.models import (
    AnswerLibrary,
    EvaluationCriterion,
    FactConflict,
    Job,
    OutlineSection,
    Project,
    Requirement,
    RfpFile,
    SubmissionRules,
    WinTheme,
)
from app.models import (
    Response as ResponseRow,
)
from app.pipeline.extras import generate_outline, run_consistency
from app.pipeline.validate import WORDS_PER_PAGE, compute_go_no_go, validate_project
from app.schemas.api import (
    CompetitionIn,
    ConflictOut,
    CriterionOut,
    JobStarted,
    OutcomeIn,
    OutlineSectionOut,
    ProjectSummary,
    WinThemesIn,
)
from app.services.company import get_or_create_company
from app.services.files import save_upload

router = APIRouter(prefix="/projects", tags=["projects"])


def get_project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} not found")
    return project


def runner_of(request: Request) -> JobRunner:
    runner: JobRunner = request.app.state.jobs
    return runner


def summary(session: Session, project: Project) -> ProjectSummary:
    assert project.id is not None
    rows = session.exec(
        select(Requirement.type, ResponseRow.status, ResponseRow.approved)
        .join(ResponseRow, col(ResponseRow.requirement_id) == col(Requirement.id), isouter=True)
        .where(
            col(Requirement.project_id) == project.id, col(Requirement.version_status) != "removed"
        )
    ).all()
    counts = {
        "requirements": len(rows),
        "mandatory": sum(1 for t, _, _ in rows if t == "mandatory"),
        "gaps": sum(1 for _, s, _ in rows if s == "gap"),
        "drafted": sum(1 for _, s, _ in rows if s not in (None, "pending")),
        "approved": sum(1 for _, _, a in rows if a),
        "fully_compliant": sum(1 for _, s, _ in rows if s == "fully_compliant"),
    }
    latest = session.exec(
        select(Job).where(col(Job.project_id) == project.id).order_by(col(Job.id).desc())
    ).first()
    files = [
        {"id": f.id, "filename": f.filename, "role": f.role, "version": f.version, "pages": f.pages}
        for f in session.exec(
            select(RfpFile).where(col(RfpFile.project_id) == project.id).order_by(col(RfpFile.id))
        ).all()
    ]
    return ProjectSummary(
        id=project.id,
        title=project.title,
        tender_no=project.tender_no,
        buyer=project.buyer,
        deadline=project.deadline,
        status=project.status,
        readiness_score=project.readiness_score,
        outcome=project.outcome,
        competition_rating=project.competition_rating,
        go_no_go=project.go_no_go,
        created_at=project.created_at,
        counts=counts,
        latest_job=job_out(latest) if latest else None,
        files=files,
        has_package=bool(project.package_path and Path(project.package_path).exists()),
    )


@router.get("", response_model=list[ProjectSummary])
def list_projects(_: CurrentUser, session: SessionDep) -> list[ProjectSummary]:
    projects = session.exec(select(Project).order_by(col(Project.id).desc())).all()
    return [summary(session, p) for p in projects]


@router.post("", response_model=JobStarted, status_code=202)
def create_project(
    request: Request,
    _: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    main: Annotated[UploadFile, File()],
    attachments: Annotated[list[UploadFile] | None, File()] = None,
    title: Annotated[str, Form()] = "",
) -> JobStarted:
    company = get_or_create_company(session)
    assert company.id is not None
    project = Project(company_id=company.id, title=title.strip(), status="analysing")
    session.add(project)
    session.commit()
    assert project.id is not None
    for role, upload in [("main", main)] + [("attachment", a) for a in (attachments or [])]:
        path, _kind = save_upload(settings, upload, f"projects/{project.id}")
        session.add(
            RfpFile(
                project_id=project.id,
                role=role,
                filename=upload.filename or path.name,
                stored_path=str(path),
            )
        )
    session.commit()
    job = runner_of(request).submit("analyse", {"project_id": project.id}, project_id=project.id)
    assert job.id is not None
    return JobStarted(job_id=job.id, project_id=project.id)


@router.get("/{project_id}", response_model=ProjectSummary)
def read_project(project_id: int, _: CurrentUser, session: SessionDep) -> ProjectSummary:
    project = get_project(session, project_id)
    if project.status not in ("analysing", "failed"):
        validate_project(session, project)  # keeps readiness_score current
    return summary(session, project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, _: CurrentUser, session: SessionDep) -> None:
    project = get_project(session, project_id)
    req_ids = [
        r.id
        for r in session.exec(
            select(Requirement).where(col(Requirement.project_id) == project_id)
        ).all()
    ]
    session.exec(delete(ResponseRow).where(col(ResponseRow.requirement_id).in_(req_ids)))
    for model in (
        Requirement,
        OutlineSection,
        EvaluationCriterion,
        WinTheme,
        FactConflict,
        SubmissionRules,
        RfpFile,
    ):
        session.exec(delete(model).where(col(model.project_id) == project_id))
    session.delete(project)
    session.commit()


@router.post("/{project_id}/reanalyse", response_model=JobStarted, status_code=202)
def reanalyse(project_id: int, request: Request, _: CurrentUser, session: SessionDep) -> JobStarted:
    get_project(session, project_id)
    job = runner_of(request).submit("analyse", {"project_id": project_id}, project_id=project_id)
    assert job.id is not None
    return JobStarted(job_id=job.id, project_id=project_id)


# ---------------------------------------------------------------- overview data


@router.get("/{project_id}/win-themes", response_model=list[str])
def get_win_themes(project_id: int, _: CurrentUser, session: SessionDep) -> list[str]:
    get_project(session, project_id)
    return [
        t.text
        for t in session.exec(
            select(WinTheme)
            .where(col(WinTheme.project_id) == project_id)
            .order_by(col(WinTheme.order))
        ).all()
    ]


@router.put("/{project_id}/win-themes", response_model=list[str])
def set_win_themes(
    project_id: int, body: WinThemesIn, _: CurrentUser, session: SessionDep
) -> list[str]:
    get_project(session, project_id)
    session.exec(delete(WinTheme).where(col(WinTheme.project_id) == project_id))
    for order, text in enumerate(body.themes):
        session.add(WinTheme(project_id=project_id, text=text, order=order))
    session.commit()
    return body.themes


@router.get("/{project_id}/criteria", response_model=list[CriterionOut])
def get_criteria(project_id: int, _: CurrentUser, session: SessionDep) -> list[CriterionOut]:
    get_project(session, project_id)
    counts = dict(
        session.exec(
            select(Requirement.criterion_id, func.count())
            .where(
                col(Requirement.project_id) == project_id,
                col(Requirement.version_status) != "removed",
            )
            .group_by(col(Requirement.criterion_id))
        ).all()
    )
    out = []
    for c in session.exec(
        select(EvaluationCriterion)
        .where(col(EvaluationCriterion.project_id) == project_id)
        .order_by(col(EvaluationCriterion.id))
    ).all():
        assert c.id is not None
        out.append(
            CriterionOut(
                id=c.id,
                code=c.code,
                name=c.name,
                max_marks=c.max_marks,
                sub_criteria=c.sub_criteria,
                page=c.page,
                requirement_count=int(counts.get(c.id, 0)),
            )
        )
    return out


@router.get("/{project_id}/rules")
def get_rules(project_id: int, _: CurrentUser, session: SessionDep) -> dict[str, Any]:
    project = get_project(session, project_id)
    row = session.exec(
        select(SubmissionRules).where(col(SubmissionRules.project_id) == project_id)
    ).first()
    from app.models import Company
    from app.services.profile import check_eligibility, unfilled_fields

    company = session.get(Company, project.company_id)
    rules: dict[str, Any] = dict(row.rules) if row else {}
    rules["eligibility"] = check_eligibility(session, company, rules.get("eligibility", []))
    rules["forms"] = [
        {**f, "unfilled": unfilled_fields(f, company, project)} for f in rules.get("forms", [])
    ]
    return rules


@router.get("/{project_id}/go-no-go")
def get_go_no_go(project_id: int, _: CurrentUser, session: SessionDep) -> dict[str, Any]:
    return compute_go_no_go(session, get_project(session, project_id))


@router.put("/{project_id}/go-no-go")
def set_competition(
    project_id: int, body: CompetitionIn, _: CurrentUser, session: SessionDep
) -> dict[str, Any]:
    project = get_project(session, project_id)
    project.competition_rating = body.competition_rating
    session.add(project)
    session.commit()
    return compute_go_no_go(session, project)


@router.put("/{project_id}/outcome", response_model=ProjectSummary)
def set_outcome(
    project_id: int, body: OutcomeIn, _: CurrentUser, session: SessionDep
) -> ProjectSummary:
    project = get_project(session, project_id)
    project.outcome = body.outcome
    for entry in session.exec(
        select(AnswerLibrary).where(col(AnswerLibrary.source_project_id) == project_id)
    ).all():
        entry.outcome = body.outcome
        session.add(entry)
    session.add(project)
    session.commit()
    return summary(session, project)


# ---------------------------------------------------------------- drafting, validation, extras


@router.post("/{project_id}/draft", response_model=JobStarted, status_code=202)
def draft_all(project_id: int, request: Request, _: CurrentUser, session: SessionDep) -> JobStarted:
    get_project(session, project_id)
    job = runner_of(request).submit("draft", {"project_id": project_id}, project_id=project_id)
    assert job.id is not None
    return JobStarted(job_id=job.id, project_id=project_id)


@router.get("/{project_id}/validate")
def validate(project_id: int, _: CurrentUser, session: SessionDep) -> dict[str, Any]:
    return validate_project(session, get_project(session, project_id))


@router.post("/{project_id}/outline", response_model=list[OutlineSectionOut])
def make_outline(project_id: int, _: CurrentUser, session: SessionDep) -> list[OutlineSectionOut]:
    generate_outline(session, get_project(session, project_id))
    return read_outline(project_id, _, session)


@router.get("/{project_id}/outline", response_model=list[OutlineSectionOut])
def read_outline(project_id: int, _: CurrentUser, session: SessionDep) -> list[OutlineSectionOut]:
    get_project(session, project_id)
    sections = session.exec(
        select(OutlineSection)
        .where(col(OutlineSection.project_id) == project_id)
        .order_by(col(OutlineSection.order))
    ).all()
    rows = session.exec(
        select(Requirement.outline_section_id, ResponseRow.answer)
        .join(ResponseRow, col(ResponseRow.requirement_id) == col(Requirement.id), isouter=True)
        .where(
            col(Requirement.project_id) == project_id, col(Requirement.version_status) != "removed"
        )
    ).all()
    words: dict[int, int] = {}
    counts: dict[int, int] = {}
    for section_id, answer in rows:
        if section_id is None:
            continue
        counts[section_id] = counts.get(section_id, 0) + 1
        words[section_id] = (
            words.get(section_id, 0) + len((answer or "").split()) + (25 if answer else 0)
        )
    out = []
    for s in sections:
        assert s.id is not None
        base = 1.0 if s.title in ("Executive Summary", "Company Profile") else 0.0
        out.append(
            OutlineSectionOut(
                id=s.id,
                title=s.title,
                order=s.order,
                page_budget=s.page_budget,
                criterion_id=s.criterion_id,
                requirement_count=counts.get(s.id, 0),
                estimated_pages=round(base + words.get(s.id, 0) / WORDS_PER_PAGE, 1),
            )
        )
    return out


@router.post("/{project_id}/consistency", response_model=list[ConflictOut])
def consistency(
    project_id: int, _: CurrentUser, session: SessionDep, settings: SettingsDep
) -> list[ConflictOut]:
    run_consistency(session, get_project(session, project_id), settings)
    return conflicts(project_id, _, session)


@router.get("/{project_id}/conflicts", response_model=list[ConflictOut])
def conflicts(project_id: int, _: CurrentUser, session: SessionDep) -> list[ConflictOut]:
    get_project(session, project_id)
    return [
        ConflictOut(id=c.id or 0, key=c.key, values=c.values, resolved=c.resolved)
        for c in session.exec(
            select(FactConflict).where(col(FactConflict.project_id) == project_id)
        ).all()
    ]


@router.put("/{project_id}/conflicts/{conflict_id}/resolve", response_model=ConflictOut)
def resolve_conflict(
    project_id: int, conflict_id: int, _: CurrentUser, session: SessionDep
) -> ConflictOut:
    conflict = session.get(FactConflict, conflict_id)
    if conflict is None or conflict.project_id != project_id:
        raise NotFoundError("Conflict not found")
    conflict.resolved = True
    session.add(conflict)
    session.commit()
    return ConflictOut(id=conflict_id, key=conflict.key, values=conflict.values, resolved=True)


@router.post("/{project_id}/addenda", response_model=JobStarted, status_code=202)
def upload_addendum(
    project_id: int,
    request: Request,
    _: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
) -> JobStarted:
    get_project(session, project_id)
    version = (
        session.exec(
            select(func.max(RfpFile.version)).where(col(RfpFile.project_id) == project_id)
        ).one()
        or 0
    ) + 1
    path, _kind = save_upload(settings, file, f"projects/{project_id}")
    rfp_file = RfpFile(
        project_id=project_id,
        role="addendum",
        version=version,
        filename=file.filename or path.name,
        stored_path=str(path),
    )
    session.add(rfp_file)
    session.commit()
    job = runner_of(request).submit(
        "addendum", {"project_id": project_id, "rfp_file_id": rfp_file.id}, project_id=project_id
    )
    assert job.id is not None
    return JobStarted(job_id=job.id, project_id=project_id)


# ---------------------------------------------------------------- package


@router.post("/{project_id}/package", response_model=JobStarted, status_code=202)
def make_package(
    project_id: int, request: Request, _: CurrentUser, session: SessionDep
) -> JobStarted:
    project = get_project(session, project_id)
    if not session.exec(
        select(OutlineSection).where(col(OutlineSection.project_id) == project_id)
    ).first():
        generate_outline(session, project)
    job = runner_of(request).submit("package", {"project_id": project_id}, project_id=project_id)
    assert job.id is not None
    return JobStarted(job_id=job.id, project_id=project_id)


@router.get("/{project_id}/package")
def package_info(project_id: int, _: CurrentUser, session: SessionDep) -> dict[str, Any]:
    project = get_project(session, project_id)
    exists = bool(project.package_path and Path(project.package_path).exists())
    return {
        "files": project.package_files if exists else [],
        "zip_name": Path(project.package_path).name if exists and project.package_path else None,
        "generated_at": project.updated_at if exists else None,
    }


@router.get("/{project_id}/package/download")
def download_package(project_id: int, _: CurrentUser, session: SessionDep) -> FileResponse:
    project = get_project(session, project_id)
    if not project.package_path or not Path(project.package_path).exists():
        raise NotFoundError("Generate the package first")
    path = Path(project.package_path)
    return FileResponse(path, media_type="application/zip", filename=path.name)


@router.get("/{project_id}/package/files/{name}")
def download_package_file(
    project_id: int, name: str, _: CurrentUser, session: SessionDep, settings: SettingsDep
) -> FileResponse:
    project = get_project(session, project_id)
    allowed = {f["name"] for f in project.package_files}
    if name not in allowed:
        raise NotFoundError("File not found in the package")
    path = settings.files_dir / "packages" / f"project-{project_id}" / "files" / name
    if not path.exists():
        raise NotFoundError("Generate the package again")
    media = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return FileResponse(
        path,
        media_type=media.get(path.suffix.lstrip("."), "application/octet-stream"),
        filename=name,
        content_disposition_type="inline",
    )


# ---------------------------------------------------------------- click-to-source (F13)


@router.get("/{project_id}/requirements/{requirement_id}/source.png")
def source_page(
    project_id: int, requirement_id: int, _: CurrentUser, session: SessionDep
) -> Response:
    req = session.get(Requirement, requirement_id)
    if req is None or req.project_id != project_id or req.rfp_file_id is None or req.page is None:
        raise NotFoundError("No source page for this requirement")
    rfp_file = session.get(RfpFile, req.rfp_file_id)
    if rfp_file is None or not Path(rfp_file.stored_path).exists():
        raise NotFoundError("Source file missing")
    with pymupdf.open(rfp_file.stored_path) as doc:
        if not doc.is_pdf or req.page > doc.page_count:
            raise ValidationFailedError("Source preview is only available for PDF files")
        page = doc[req.page - 1]
        quote = req.source_quote.strip()
        hits = (
            page.search_for(quote)
            or page.search_for(quote[:60])
            or page.search_for(" ".join(quote.split()[:6]))
        )
        for rect in hits:
            annot = page.add_highlight_annot(rect)
            annot.set_colors(stroke=(1, 0.85, 0.2))
            annot.update()
        pix = page.get_pixmap(dpi=110, annots=True)
        buffer = io.BytesIO(pix.tobytes("png"))
    return Response(
        content=buffer.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"}
    )
