"""API request / response models."""

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    id: int
    email: str
    name: str


class Turnover(BaseModel):
    fy: str
    amount_inr: float = Field(ge=0)


class Certification(BaseModel):
    name: str
    number: str = ""
    valid_until: str = ""


class CompanyIn(BaseModel):
    legal_name: str = Field(min_length=2)
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
    year_established: int | None = Field(default=None, ge=1800, le=2100)
    turnover: list[Turnover] = []
    certifications: list[Certification] = []
    style_sample: str = ""

    @field_validator("gstin")
    @classmethod
    def _gstin(cls, value: str) -> str:
        value = value.strip().upper()
        if value and not GSTIN_RE.match(value):
            raise ValueError("GSTIN must be 15 characters, e.g. 29ABCDE1234F1Z5")
        return value

    @field_validator("pan")
    @classmethod
    def _pan(cls, value: str) -> str:
        value = value.strip().upper()
        if value and not PAN_RE.match(value):
            raise ValueError("PAN must be 10 characters, e.g. ABCDE1234F")
        return value


class CompanyOut(CompanyIn):
    id: int
    legal_name: str = ""


class KnowledgeDocOut(BaseModel):
    id: int
    filename: str
    doc_type: str
    pages: int
    status: str
    error: str | None
    outcome: str
    created_at: datetime


class KnowledgeDocPatch(BaseModel):
    doc_type: (
        Literal["past_proposal", "case_study", "profile", "product", "certificate", "other"] | None
    ) = None
    outcome: Literal["won", "lost", "unknown"] | None = None


class SearchHit(BaseModel):
    chunk_id: int
    filename: str
    page: int
    text: str
    score: float


class JobOut(BaseModel):
    id: int
    project_id: int | None
    kind: str
    status: str
    stage: str
    progress: int
    message: str
    error: str | None
    counts: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class JobStarted(BaseModel):
    job_id: int
    project_id: int | None = None


class ProjectSummary(BaseModel):
    id: int
    title: str
    tender_no: str
    buyer: str
    deadline: datetime | None
    status: str
    readiness_score: int
    outcome: str
    competition_rating: int | None
    go_no_go: dict[str, Any] | None
    created_at: datetime
    counts: dict[str, int]
    latest_job: JobOut | None
    files: list[dict[str, Any]]
    has_package: bool


class WinThemesIn(BaseModel):
    themes: list[str] = Field(max_length=3)

    @field_validator("themes")
    @classmethod
    def _clean(cls, value: list[str]) -> list[str]:
        return [t.strip() for t in value if t.strip()]


class CriterionOut(BaseModel):
    id: int
    code: str
    name: str
    max_marks: float | None
    sub_criteria: list[str]
    page: int | None
    requirement_count: int


class ReviewIssue(BaseModel):
    type: str
    message: str
    severity: Literal["high", "medium", "low"]


class ResponseOut(BaseModel):
    id: int
    answer: str | None
    status: str
    confidence: float
    citations: list[dict[str, Any]]
    gap_reason: str | None
    approved: bool
    approval_override_reason: str | None
    edited_by_user: bool
    needs_review: bool
    review_score: int | None
    review_issues: list[ReviewIssue]
    model: str
    updated_at: datetime


class RequirementOut(BaseModel):
    id: int
    req_code: str
    text: str
    section_path: str
    page: int | None
    type: str
    keyword: str
    category: str
    source_quote: str
    criterion_id: int | None
    criterion_name: str | None
    outline_section_id: int | None
    version_status: str
    previous_text: str | None
    rfp_file_id: int | None
    response: ResponseOut | None


class RequirementList(BaseModel):
    items: list[RequirementOut]
    total: int
    summary: dict[str, int]


class RequirementPatch(BaseModel):
    text: str | None = None
    type: Literal["mandatory", "optional"] | None = None
    criterion_id: int | None = None


class ResponsePatch(BaseModel):
    answer: str | None = None
    status: (
        Literal[
            "fully_compliant",
            "partially_compliant",
            "non_compliant",
            "compliant_with_customisation",
            "gap",
        ]
        | None
    ) = None
    approved: bool | None = None
    override_reason: str | None = None


class RedraftIn(BaseModel):
    hint: str | None = Field(default=None, max_length=500)


class CompetitionIn(BaseModel):
    competition_rating: int = Field(ge=1, le=5)


class OutcomeIn(BaseModel):
    outcome: Literal["unknown", "won", "lost"]


class OutlineSectionOut(BaseModel):
    id: int
    title: str
    order: int
    page_budget: float
    criterion_id: int | None
    requirement_count: int
    estimated_pages: float


class ConflictOut(BaseModel):
    id: int
    key: str
    values: list[dict[str, Any]]
    resolved: bool


class AuditOut(BaseModel):
    id: int
    action: str
    actor: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    at: datetime
