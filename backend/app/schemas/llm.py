"""Structured outputs returned by LLM prompts (Claude or the offline provider).

All fields are required (nullable where a value may be absent) so the schemas work with
structured outputs, which need every property listed as required.
"""

from typing import Literal

from pydantic import BaseModel

ChunkCategory = Literal[
    "introduction",
    "instructions",
    "eligibility",
    "scope",
    "technical",
    "sla",
    "evaluation",
    "commercial",
    "forms",
    "general_conditions",
    "other",
]
ComplianceStatus = Literal[
    "fully_compliant", "partially_compliant", "non_compliant", "compliant_with_customisation", "gap"
]


class ChunkClassification(BaseModel):
    category: ChunkCategory


class ExtractedRequirement(BaseModel):
    text: str
    section_path: str
    page: int
    type: Literal["mandatory", "optional"]
    keyword: str
    category: str
    source_quote: str


class RequirementList(BaseModel):
    requirements: list[ExtractedRequirement]


class Cover(BaseModel):
    name: str
    documents: list[str]


class FormatRules(BaseModel):
    file_types: list[str]
    max_file_mb: float | None
    page_limit: int | None
    font: str | None
    font_size: float | None
    margins_in: float | None


class Emd(BaseModel):
    amount_inr: float | None
    exemption: str | None


class EligibilityItem(BaseModel):
    criterion: str
    evidence: str
    page: int | None


class FormSpec(BaseModel):
    code: str
    title: str
    page: int | None
    fields: list[str]
    text: str


class SubmissionRulesOut(BaseModel):
    title: str | None
    tender_no: str | None
    buyer: str | None
    deadline: str | None  # ISO 8601 with timezone when stated
    portal: str | None
    bid_system: str | None
    covers: list[Cover]
    format: FormatRules
    naming: str | None
    signing: str | None
    emd: Emd | None
    validity_days: int | None
    eligibility: list[EligibilityItem]
    forms: list[FormSpec]


class CriterionOut(BaseModel):
    code: str
    name: str
    max_marks: float | None
    sub_criteria: list[str]
    page: int | None


class CriteriaList(BaseModel):
    qcbs_split: str | None
    min_qualifying_marks: float | None
    criteria: list[CriterionOut]


class CriterionLink(BaseModel):
    requirement_index: int
    criterion_code: str | None


class CriterionLinks(BaseModel):
    links: list[CriterionLink]


class CitationOut(BaseModel):
    chunk_id: int
    quote: str


class DraftedResponse(BaseModel):
    answer: str
    status: ComplianceStatus
    confidence: float
    citations: list[CitationOut]
    gap_reason: str | None


class ReviewOutput(BaseModel):
    missing_parts: list[str]
    unsupported_claims: list[str]
    specificity: Literal["low", "medium", "high"]


class Fact(BaseModel):
    key: str
    value: str


class FactList(BaseModel):
    facts: list[Fact]
