"""All database tables. Field value sets are documented in ARCHITECTURE.md §2."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, LargeBinary, Text
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def _json(default: Any = None) -> Any:
    return Field(
        default_factory=lambda: default if default is not None else [], sa_column=Column(JSON)
    )


class TimestampMixin(SQLModel):
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class User(TimestampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    name: str = ""
    is_active: bool = True


class Company(TimestampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)
    legal_name: str = ""
    short_name: str = ""
    address: str = ""
    gstin: str = ""
    pan: str = ""
    udyam_no: str = ""
    signatory_name: str = ""
    signatory_designation: str = ""
    email: str = ""
    phone: str = ""
    website: str = ""
    year_established: int | None = None
    turnover: list[dict[str, Any]] = _json()  # [{fy, amount_inr}]
    certifications: list[dict[str, Any]] = _json()  # [{name, number, valid_until}]
    logo_path: str | None = None
    style_sample: str = Field(default="", sa_column=Column(Text))


class KnowledgeDoc(TimestampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    filename: str
    stored_path: str
    doc_type: str = "other"  # past_proposal | product | certificate | case_study | profile | other
    pages: int = 0
    status: str = "pending"  # pending | indexing | ready | failed
    error: str | None = None
    outcome: str = "unknown"  # won | lost | unknown — evidence from won bids ranks higher


class KnowledgeChunk(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    doc_id: int = Field(foreign_key="knowledgedoc.id", index=True, ondelete="CASCADE")
    company_id: int = Field(index=True)
    page: int
    chunk_index: int
    text: str = Field(sa_column=Column(Text))
    embedding: bytes = Field(sa_column=Column(LargeBinary))


class Project(TimestampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    title: str = ""
    tender_no: str = ""
    buyer: str = ""
    deadline: datetime | None = None
    status: str = "draft"  # draft | analysing | ready | failed | packaged
    readiness_score: int = 0
    outcome: str = "unknown"  # unknown | won | lost
    competition_rating: int | None = None
    go_no_go: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    tokens_used: int = 0
    package_path: str | None = None
    package_files: list[dict[str, Any]] = _json()


class RfpFile(TimestampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True, ondelete="CASCADE")
    version: int = 0
    role: str = "main"  # main | attachment | addendum
    filename: str
    stored_path: str
    pages: int = 0
    parsed_at: datetime | None = None


class RfpPage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    rfp_file_id: int = Field(foreign_key="rfpfile.id", index=True, ondelete="CASCADE")
    page: int
    text: str = Field(sa_column=Column(Text))


class EvaluationCriterion(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True, ondelete="CASCADE")
    code: str = ""
    name: str
    max_marks: float | None = None
    weight: float | None = None
    sub_criteria: list[str] = _json()
    min_qualifying_marks: float | None = None
    page: int | None = None


class OutlineSection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True, ondelete="CASCADE")
    title: str
    order: int = 0
    page_budget: float = 0.0
    criterion_id: int | None = Field(default=None, foreign_key="evaluationcriterion.id")


class Requirement(TimestampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True, ondelete="CASCADE")
    rfp_file_id: int | None = Field(default=None, foreign_key="rfpfile.id")
    req_code: str = ""
    text: str = Field(sa_column=Column(Text))
    section_path: str = ""
    page: int | None = None
    type: str = "mandatory"  # mandatory | optional
    keyword: str = ""
    category: str = "general"
    source_quote: str = Field(default="", sa_column=Column(Text))
    criterion_id: int | None = Field(default=None, foreign_key="evaluationcriterion.id")
    outline_section_id: int | None = Field(default=None, foreign_key="outlinesection.id")
    version_status: str = "unchanged"  # unchanged | modified | added | removed
    previous_text: str | None = Field(default=None, sa_column=Column(Text))
    order: int = 0


class Response(TimestampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)
    requirement_id: int = Field(foreign_key="requirement.id", unique=True, ondelete="CASCADE")
    answer: str | None = Field(default=None, sa_column=Column(Text))
    status: str = "pending"  # pending | fully_compliant | partially_compliant | non_compliant
    # | compliant_with_customisation | gap
    confidence: float = 0.0
    citations: list[dict[str, Any]] = _json()  # [{doc_id, filename, page, quote}]
    gap_reason: str | None = None
    approved: bool = False
    approval_override_reason: str | None = None
    edited_by_user: bool = False
    needs_review: bool = False
    review_score: int | None = None
    review_issues: list[dict[str, Any]] = _json()  # [{type, message, severity}]
    model: str = ""
    prompt_version: str = ""


class SubmissionRules(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", unique=True, ondelete="CASCADE")
    rules: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class WinTheme(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True, ondelete="CASCADE")
    text: str
    order: int = 0


class FactConflict(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True, ondelete="CASCADE")
    key: str
    values: list[dict[str, Any]] = _json()  # [{value, requirement_id, req_code}]
    resolved: bool = False


class AuditEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int | None = Field(default=None, index=True)
    entity: str
    entity_id: int = Field(index=True)
    action: str
    actor: str
    before: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    after: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    prompt_version: str | None = None
    at: datetime = Field(default_factory=utcnow)


class AnswerLibrary(TimestampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    requirement_text: str = Field(sa_column=Column(Text))
    answer: str = Field(sa_column=Column(Text))
    source_project_id: int | None = Field(default=None, index=True)
    source_requirement_id: int | None = Field(default=None, index=True)
    outcome: str = "unknown"
    embedding: bytes = Field(sa_column=Column(LargeBinary))


class PolicyRule(TimestampMixin, table=True):
    """A business / financial / compliance rule created in the UI (file rules live in POLICY_DIR)."""

    id: int | None = Field(default=None, primary_key=True)
    rule_key: str = Field(index=True, unique=True)
    name: str
    description: str = ""
    scope: str = "requirement"  # requirement | tender | company
    when: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    flag_if: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    severity: str = "medium"  # high | medium | low
    message: str = ""
    enabled: bool = True


class AuditRun(SQLModel, table=True):
    """One policy re-audit of a project; findings carry `new` when absent from the previous run."""

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True, ondelete="CASCADE")
    findings: list[dict[str, Any]] = _json()
    errors: list[str] = _json()
    rules_evaluated: int = 0
    resolved: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class Job(TimestampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int | None = Field(default=None, index=True)
    kind: str
    params: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "queued"  # queued | running | succeeded | failed
    stage: str = ""
    progress: int = 0
    message: str = ""
    error: str | None = None
    counts: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
