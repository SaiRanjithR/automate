"""Offline, deterministic provider implementing every prompt with rules and regexes.

It lets the app run end to end without an API key (demo fallback) and makes tests reproducible.
Output quality is lower than Claude's, but it follows the same guardrails: answers are built only
from verbatim evidence sentences, and missing evidence becomes a gap.
"""

import re
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.errors import LLMError
from app.llm.client import LLMResult, UsageMeter
from app.pipeline.textutil import (
    PAGE_MARKER,
    key_terms,
    normalize,
    snake_case,
    split_sentences,
    words,
)
from app.schemas.llm import (
    ChunkClassification,
    CitationOut,
    Cover,
    CriteriaList,
    CriterionLink,
    CriterionLinks,
    CriterionOut,
    DraftedResponse,
    EligibilityItem,
    Emd,
    ExtractedRequirement,
    Fact,
    FactList,
    FormatRules,
    FormSpec,
    RequirementList,
    ReviewOutput,
    SubmissionRulesOut,
)

T = TypeVar("T", bound=BaseModel)
VERSION = "offline@1"

# ---------------------------------------------------------------- classification

_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    # Order matters: the first category whose keyword appears in the heading wins.
    (
        "forms",
        (
            "annexure",
            "appendix",
            "format for",
            "form ",
            "non-disclosure",
            "affidavit",
            "power of attorney",
        ),
    ),
    (
        "introduction",
        (
            "disclaimer",
            "important notice",
            "introduction",
            "background",
            "overview",
            "purpose",
            "landscape",
            "glossary",
            "abbreviation",
            "definitions",
            "assumption",
            "dependenc",
            "invitation",
        ),
    ),
    (
        "evaluation",
        ("evaluation", "scoring", "marks", "qcbs", "selection method", "award criteria"),
    ),
    (
        "eligibility",
        ("eligibility", "pre-qualification", "prequalification", "qualification criteria"),
    ),
    (
        "instructions",
        (
            "instruction",
            "submission",
            "how to submit",
            "important dates",
            "bid process",
            "tender details",
            "key dates",
            "schedule of bidding",
        ),
    ),
    ("sla", ("service level", "sla", "maintenance", "warranty", "penalt", "helpdesk", "support")),
    ("commercial", ("commercial", "payment", "price", "financial", "boq", "bill of quantities")),
    (
        "technical",
        (
            "technical",
            "specification",
            "hosting",
            "security",
            "integration",
            "architecture",
            "hardware",
            "infrastructure",
        ),
    ),
    (
        "scope",
        (
            "scope",
            "functional",
            "deliverable",
            "implementation",
            "training",
            "requirements",
            "responsibilit",
            "project management",
            "timeline",
            "change management",
        ),
    ),
    ("general_conditions", ("general conditions", "terms and conditions", "contract", "legal")),
]


def classify(variables: dict[str, Any]) -> ChunkClassification:
    heading = str(variables.get("heading", "")).lower()
    for category, keys in _CATEGORY_KEYWORDS:
        if any(k in heading for k in keys):
            return ChunkClassification(category=category)
    body = str(variables.get("text", "")).lower()
    best, best_hits = "other", 0
    for category, keys in _CATEGORY_KEYWORDS:
        hits = sum(body.count(k) for k in keys)
        if hits > best_hits:
            best, best_hits = category, hits
    return ChunkClassification(category=best)


# ---------------------------------------------------------------- requirements

_MANDATORY = re.compile(
    r"\b(shall|must|will be required to|is required to|are required to|mandatory)\b", re.I
)
_OPTIONAL = re.compile(r"\b(should|may|desirable|preferably|preferred)\b", re.I)
_DOC_SUBJECT = re.compile(
    r"^(this|the|such|these|any)\s+(rfp|tender|bid document|document|information|assumptions?|statements?|"
    r"rfp document|tender document|corrigend\w*|addend\w*)\b",
    re.I,
)
_BIDDER_WORDS = re.compile(
    r"\b(bidders?|vendors?|suppliers?|contractors?|service providers?|agency|agencies|applicants?|"
    r"consultants?|firms?|solution|system|platform|application|software|you|your)\b",
    re.I,
)
_BUYER_SUBJECT = re.compile(
    r"^(the\s+)?(purchaser|buyer|department|authority|society|mission|client|tender inviting|"
    r"evaluation committee|committee|employer|government)\b",
    re.I,
)
_CLAUSE = re.compile(r"^(\d+(?:\.\d+){1,3})\.?\s*(?=[A-Za-z(\"\u201c])")
_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\.?\s*([A-Z][^.]{2,70})$")
_CATEGORY_TERMS: list[tuple[str, tuple[str, ...]]] = [
    ("security", ("security", "encrypt", "access control", "audit trail", "password", "vapt")),
    ("hosting", ("hosting", "cloud", "data centre", "data center", "uptime", "disaster recovery")),
    ("integration", ("integrat", "hl7", "fhir", "abdm", "api", "interface", "sms gateway")),
    ("training", ("train",)),
    ("support", ("support", "helpdesk", "help desk", "maintenance", "amc", "warranty")),
    ("sla", ("response time", "resolution", "penalt", "service level")),
    ("implementation", ("go-live", "go live", "implement", "deploy", "rollout", "migration")),
    ("eligibility", ("turnover", "experience", "certif", "registered", "blacklist")),
    ("commercial", ("price", "payment", "gst", "invoice")),
    ("functional", ("module", "registration", "billing", "pharmacy", "laboratory", "report")),
]


def _category(text: str) -> str:
    low = text.lower()
    for category, keys in _CATEGORY_TERMS:
        if any(k in low for k in keys):
            return category
    return "general"


def _paged_lines(chunk_text: str) -> list[tuple[int, str]]:
    page = 1
    out: list[tuple[int, str]] = []
    for raw in chunk_text.splitlines():
        marker = PAGE_MARKER.fullmatch(raw.strip())
        if marker:
            page = int(marker.group(1))
            continue
        line = raw.strip()
        if line:
            out.append((page, line))
    return out


def _paragraphs(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Join wrapped lines into paragraphs: a new paragraph starts at a clause number, bullet,
    table row or heading, or after a line ending with sentence punctuation."""
    paragraphs: list[tuple[int, str]] = []
    current: list[str] = []
    start_page = 1

    def flush() -> None:
        if current:
            paragraphs.append((start_page, normalize(" ".join(current))))
            current.clear()

    for page, line in lines:
        starts_new = bool(
            _CLAUSE.match(line)
            or line.startswith(("•", "-", "\u2013", "|"))
            or re.match(r"^[a-z]\)|^\([a-z]\)|^\(?[ivx]+\)", line)
            or " | " in line
            or _HEADING.match(line)
        )
        if starts_new or not current:
            flush()
            start_page = page
        current.append(line)
        if " | " in line or _HEADING.match(line) or line.endswith((".", ":", ";")):
            flush()
    flush()
    return paragraphs


_WILL = re.compile(
    r"\b(will|is responsible for|are responsible for|is expected to|are expected to)\b", re.I
)
_BULLET = re.compile(
    r"^(?:[•\-\u2013\u25aa\u25cf\uf0b7o]|[a-z]\)|\([a-z]\)|\(?[ivx]+\)|\d+[.)])\s+"
)
_FLAGS = ("mandatory", "desirable", "optional", "m", "d", "yes")


_DISCLAIMER = re.compile(
    r"^(?:for example|for instance|e\.g\.|illustration)|"
    r"own investigations?|own analysis|its own assessment|no representation or warranty|"
    r"without being under any obligation|absolute discretion|does not purport|not be appropriate for all",
    re.I,
)


def _obligation(
    sentence: str, buyer_aliases: list[str], strict_should: bool
) -> tuple[str, str] | None:
    """Return (type, keyword) when the sentence puts an obligation on the bidder or its solution."""
    if len(sentence.split()) < 5 or _DISCLAIMER.search(sentence):
        return None
    if _BUYER_SUBJECT.match(sentence) or _DOC_SUBJECT.match(sentence):
        return None
    low = sentence.lower()
    if any(low.startswith(alias) for alias in buyer_aliases):
        return None
    mandatory = _MANDATORY.search(sentence)
    if mandatory:
        subject = sentence[: mandatory.start()]
        if any(alias in subject.lower() for alias in buyer_aliases):
            return None
        return "mandatory", mandatory.group(1).lower()
    for pattern, kind in ((_WILL, "mandatory"), (_OPTIONAL, "optional")):
        match = pattern.search(sentence)
        if not match:
            continue
        subject = sentence[: match.start()]
        if not _BIDDER_WORDS.search(subject) or any(a in subject.lower() for a in buyer_aliases):
            return None
        keyword = match.group(1).lower()
        if kind == "optional" and keyword == "should" and strict_should:
            kind = "mandatory"
        return kind, keyword
    return None


def _is_lead_in(sentence: str, buyer_aliases: list[str]) -> bool:
    """'The training should cover the following areas:' introduces a list of requirements."""
    low = sentence.lower()
    if _BUYER_SUBJECT.match(sentence) or _DOC_SUBJECT.match(sentence):
        return False
    if any(low.startswith(alias) for alias in buyer_aliases):
        return False
    return bool(_MANDATORY.search(sentence) or _OPTIONAL.search(sentence) or _WILL.search(sentence))


def extract_requirements(variables: dict[str, Any]) -> RequirementList:
    chunk_text = str(variables.get("chunk_text", ""))
    base_section = str(variables.get("section_path", ""))
    buyer_aliases = [str(a).lower() for a in variables.get("buyer_aliases", []) if a]
    category = str(variables.get("category", ""))
    strict_should = category == "eligibility"
    price_like = category in ("commercial", "forms")
    section = base_section
    lead_in: tuple[str, str] | None = None  # (lead-in text, type) for the list that follows
    items: list[ExtractedRequirement] = []

    def add(text: str, quote: str, page: int, kind: str, keyword: str, path: str) -> None:
        items.append(
            ExtractedRequirement(
                text=normalize(text),
                section_path=path.strip() or base_section,
                page=page,
                type=kind,
                keyword=keyword,
                category=_category(text),
                source_quote=normalize(quote),
            )
        )

    for page, para in _paragraphs(_paged_lines(chunk_text)):
        heading = _HEADING.match(para)
        if heading and not _MANDATORY.search(para):
            section = f"{heading.group(1)} {heading.group(2).strip()}"
            lead_in = None
            continue
        if " | " in para:
            cells = [c.strip() for c in para.strip("| ").split(" | ") if c.strip()]
            flagged = _table_row_requirement(para, page, section)
            if flagged:
                items.extend(flagged)
                continue
            if not cells or cells[0].lower().rstrip(".") in (
                "no",
                "s.no",
                "sr. no",
                "sl. no",
                "#",
                "sno",
            ):
                continue  # header row
            if all(len(c.split()) <= 4 for c in cells) and not lead_in:
                continue  # short labels
            if lead_in and len(cells) > 2:
                lead_in = None  # a wider table is a new table, not the list the lead-in introduced
                if all(len(c.split()) <= 4 for c in cells):
                    continue
            if lead_in:
                item = max(cells, key=len)
                if len(item.split()) >= 2 and not re.fullmatch(r"[\d.]+", item):
                    add(
                        f"{lead_in[0]}: {item.rstrip('.')}.",
                        item,
                        page,
                        lead_in[1],
                        "list",
                        section,
                    )
                continue
            for cell in cells:
                bullets = [
                    b.strip(" ;.")
                    for b in re.split(r"\s*[•\u25aa\u25cf\uf0b7]\s*", cell)
                    if b.strip()
                ]
                if not price_like and (
                    len(bullets) > 1 or cell.lstrip().startswith(("•", "\u25aa", "\uf0b7"))
                ):
                    for bullet in bullets:
                        if len(bullet.split()) >= 5:
                            found = _obligation(bullet, buyer_aliases, strict_should)
                            kind, keyword = found if found else ("mandatory", "deliverable")
                            add(bullet.rstrip(".") + ".", bullet, page, kind, keyword, section)
                    continue
                for sentence in split_sentences(cell):
                    found = _obligation(sentence, buyer_aliases, strict_should)
                    if found:
                        add(sentence, sentence, page, found[0], found[1], section)
            continue

        clause = _CLAUSE.match(para)
        clause_id = clause.group(1) if clause else None
        body = para[clause.end() :] if clause else para
        is_bullet = bool(_BULLET.match(body))
        body = _BULLET.sub("", body)
        path = f"{clause_id} {section.split(' ', 1)[-1]}" if clause_id else section
        if lead_in and is_bullet and len(body.split()) >= 2:
            add(f"{lead_in[0]}: {body.rstrip('.;')}.", body, page, lead_in[1], "list", path)
            continue
        lead_in = None
        for sentence in split_sentences(body):
            if sentence.rstrip().endswith(":") and _is_lead_in(sentence, buyer_aliases):
                lead_in = (
                    sentence.rstrip(" :"),
                    "mandatory" if not _OPTIONAL.search(sentence) or strict_should else "optional",
                )
                continue
            found = _obligation(sentence, buyer_aliases, strict_should)
            if not found:
                continue
            add(sentence, sentence, page, found[0], found[1], path)
    return RequirementList(requirements=items)


def _table_row_requirement(row: str, page: int, section: str) -> list[ExtractedRequirement]:
    cells = [c.strip() for c in row.strip("| ").split(" | ") if c.strip()]
    if len(cells) < 2:
        return []
    flag = cells[-1].lower()
    if flag not in _FLAGS:
        return []
    description = max(cells[:-1], key=len)
    if len(description.split()) < 3:
        return []
    mandatory = flag in ("mandatory", "m", "yes")
    ref = cells[0] if cells[0] != description else ""
    text = (
        description
        if _MANDATORY.search(description)
        else f"The solution shall provide {description[0].lower()}{description[1:]}"
    )
    return [
        ExtractedRequirement(
            text=normalize(text.rstrip(".") + "."),
            section_path=f"{section} {ref}".strip(),
            page=page,
            type="mandatory" if mandatory else "optional",
            keyword="mandatory" if mandatory else "desirable",
            category=_category(description),
            source_quote=description,
        )
    ]


# ---------------------------------------------------------------- submission rules

_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
_DATE = re.compile(
    rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTHS}|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*,?\s+(\d{{4}})",
    re.I,
)
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b")
_TIME = re.compile(r"(\d{1,2})[:.](\d{2})\s*(hrs|hours|ist|am|pm)?", re.I)


def _parse_deadline(text: str) -> str | None:
    strong = ("last date", "deadline", "submission end", "due date", "closing date")
    return _deadline_with(text, strong) or _deadline_with(text, ("bid submission",))


def _deadline_with(text: str, keywords: tuple[str, ...]) -> str | None:
    for line in text.splitlines():
        low = line.lower()
        if not any(k in low for k in keywords):
            continue
        if any(
            k in low for k in ("quer", "clarification", "pre-bid", "pre bid", "sale of", "download")
        ):
            continue
        date = _DATE.search(line)
        numeric = _NUMERIC_DATE.search(line)
        if date:
            day, month, year = date.groups()
            parsed = datetime.strptime(f"{day} {month[:3]} {year}", "%d %b %Y")
        elif numeric:
            day, month, year = numeric.groups()
            try:
                parsed = datetime(int(year), int(month), int(day))
            except ValueError:
                continue
            date = numeric
        else:
            continue
        time = _TIME.search(line[date.end() :])
        if time:
            hour, minute = int(time.group(1)), int(time.group(2))
            suffix = (time.group(3) or "").lower()
            if suffix == "pm" and hour < 12:
                hour += 12
            parsed = parsed.replace(hour=hour, minute=minute)
        else:
            parsed = parsed.replace(hour=17, minute=0)
        indian = re.search(r"\bist\b|india|cppp|eprocure|\bgem\b|lakh|crore|₹", text, re.I)
        tz = "+05:30" if ("ist" in low or indian) else ""
        return parsed.strftime("%Y-%m-%dT%H:%M:00") + tz
    return None


_ORG_WORDS = re.compile(
    r"\b(government|ministry|department|corporation|authority|limited|ltd|society|mission|board|"
    r"council|university|institute|marketplace|e-marketplace|emarketplace|bank|commission|municipal)\b",
    re.I,
)


def _organisation_line(lines: list[tuple[int, str]]) -> str | None:
    """Fallback buyer: the first short line on page 1-2 naming an organisation."""
    for page, line in lines[:60]:
        if page > 2:
            break
        if 5 <= len(line) <= 90 and _ORG_WORDS.search(line) and not re.search(r"\d{3,}", line):
            text = re.sub(r"^(?:for|by|issued by)\s+", "", line.strip(), flags=re.I)
            return text.strip(" ,.:;")
    return None


def _emd_amount(flat: str) -> str | None:
    match = re.search(
        r"(?:EMD|Earnest Money(?: Deposit)?)[^.]{0,80}?(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)\s*(?:\([A-Za-z ]+\)\s*)?(lakhs?|lacs?|crores?|cr)?",
        flat,
        re.I,
    )
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    unit = (match.group(2) or "").lower()
    if unit.startswith(("lakh", "lac")):
        value *= 100_000
    elif unit.startswith(("crore", "cr")):
        value *= 10_000_000
    return str(value)


def _exemption_sentence(text: str) -> str | None:
    for _, para in _paragraphs(_paged_lines(text)):
        for sentence in split_sentences(para):
            low = sentence.lower()
            if "exempt" in low and any(
                k in low for k in ("emd", "earnest", "mse", "msme", "udyam", "startup")
            ):
                return re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", sentence)
    return None


def _first(pattern: str, text: str, flags: int = re.I) -> str | None:
    match = re.search(pattern, text, flags)
    return normalize(match.group(1)).strip(" .,:;") if match else None


def _sentence_with(text: str, *needles: str) -> str | None:
    for _, para in _paragraphs(_paged_lines(text)):
        clause = _CLAUSE.match(para)
        body = para[clause.end() :] if clause else para
        for sentence in split_sentences(body):
            low = sentence.lower()
            if any(n in low for n in needles):
                return sentence
    return None


def extract_rules(variables: dict[str, Any]) -> SubmissionRulesOut:
    text = str(variables.get("text", ""))
    flat = normalize(PAGE_MARKER.sub(" ", text))
    lines = _paged_lines(text)

    covers: list[Cover] = []
    current: Cover | None = None
    for _, line in lines:
        header = re.match(
            r"^(?:\d+(?:\.\d+)*\s+)?(Cover[- ]?\d+|Envelope[- ]?\d+|Volume[- ]?[IVX\d]+)\s*\(?([^):]*)\)?",
            line,
            re.I,
        )
        if header:
            name = normalize(f"{header.group(1)} {header.group(2)}".strip())
            current = Cover(name=name.replace("  ", " "), documents=[])
            covers.append(current)
            continue
        if current is not None:
            bullet = re.match(r"^(?:[a-z]\)|\([a-z]\)|[•\-\u2013])\s*(.+)$", line)
            if bullet:
                current.documents.append(bullet.group(1).strip(" ;."))
            elif _CLAUSE.match(line) or _HEADING.match(line):
                current = None

    font_match = re.search(
        r"\b(Arial|Times New Roman|Calibri|Verdana|Cambria)\b[^.]{0,40}?(\d{1,2})\s*(?:pt|point)",
        flat,
        re.I,
    )
    size_match = re.search(r"font size (?:of )?(\d{1,2})", flat, re.I)
    page_limit = _first(
        r"(?:not exceed|maximum of|limited to|no more than)\s+(\d{1,3})\s+(?:\(\w+\)\s+)?pages",
        flat,
    )
    margins = _first(r"margins? of (\d(?:\.\d)?)\s*(?:inch|in\b|\")", flat) or _first(
        r"(\d(?:\.\d)?)\s*(?:inch|\")\s+margins?", flat
    )
    max_mb = _first(r"(\d{1,3})\s*MB", flat)
    file_types = (
        sorted({t.upper() for t in re.findall(r"\b(pdf|docx|xlsx|xls)\b", flat, re.I)}) or []
    )

    emd_amount = _emd_amount(flat)
    emd_exemption = _exemption_sentence(text)

    eligibility: list[EligibilityItem] = []
    forms: list[FormSpec] = []
    in_eligibility = False
    for page, line in lines:
        low = line.lower()
        if _HEADING.match(line) or re.match(r"^(Annexure|Appendix|Form|Schedule)\b", line, re.I):
            in_eligibility = ("eligib" in low or "qualification" in low) and not low.startswith(
                ("annexure", "appendix", "form", "schedule")
            )
        if in_eligibility and " | " in line:
            cells = [c.strip() for c in line.strip("| ").split(" | ")]
            if len(cells) >= 3 and re.match(r"^\d+\.?$", cells[0]):
                eligibility.append(
                    EligibilityItem(criterion=cells[1], evidence=cells[2], page=page)
                )

    form_heads = [
        (i, m)
        for i, (_, line) in enumerate(lines)
        if (
            m := re.match(
                r"^(?:\d+(?:\.\d+)*\.?\s*)?((?:Annexure|ANNEXURE|Appendix|APPENDIX|Form|FORM)[- ]?[A-Z0-9]{1,4})\s*[:\-\u2013]\s*(.+)$",
                line,
            )
        )
    ]
    for index, (start, match) in enumerate(form_heads):
        end = form_heads[index + 1][0] if index + 1 < len(form_heads) else len(lines)
        body = "\n".join(para for _, para in _paragraphs(lines[start + 1 : end]))
        placeholders = re.findall(r"\[([^\]]{2,60})\]|<([^>]{2,60})>", body)
        fields: list[str] = []
        for a, b in placeholders:
            name = snake_case(a or b)
            if name not in fields:
                fields.append(name)
        forms.append(
            FormSpec(
                code=normalize(match.group(1)).replace(" ", "-"),
                title=match.group(2).strip(),
                page=lines[start][0],
                fields=fields,
                text=body,
            )
        )

    portal = None
    if re.search(r"cppp|eprocure\.gov\.in|central public procurement", flat, re.I):
        portal = "Central Public Procurement Portal (CPPP)"
    elif re.search(r"\bGeM\b|gem\.gov\.in", flat):
        portal = "Government e-Marketplace (GeM)"

    return SubmissionRulesOut(
        title=_first(
            r"(?:Request for Proposal|RFP|Tender)\s+(?:\(RFP\)\s+)?for\s+(?:the\s+)?([^\n]{10,160}?)(?:\s+(?:Tender|RFP|Bid|NIT)\s+No|\.|$)",
            flat,
        ),
        tender_no=_first(
            r"(?:Tender|RFP|Bid|NIT|RFQ|RFI)\s+(?:No|Number|Reference|Ref)\.?\s*[:\-\u2013]?\s*([A-Z0-9][A-Za-z0-9/\-.]{4,40}[A-Za-z0-9])",
            flat,
            0,
        ),
        buyer=_first(
            r"(?:issued by|Issued by|Tender Inviting Authority)\s*[:\-]?\s*([^.\n]{5,100}?)(?:,|\.|\s+Tender|$)",
            flat[:3000],
            0,
        )
        or _organisation_line(lines),
        deadline=_parse_deadline(text),
        portal=portal,
        bid_system="two_bid"
        if re.search(r"two[- ]bid|two[- ]cover|two[- ]envelope", flat, re.I)
        or (
            re.search(r"technical bid", flat, re.I)
            and re.search(r"(?:commercial|financial|price) bid", flat, re.I)
        )
        else None,
        covers=covers,
        format=FormatRules(
            file_types=file_types,
            max_file_mb=float(max_mb) if max_mb else None,
            page_limit=int(page_limit) if page_limit else None,
            font=font_match.group(1) if font_match else None,
            font_size=float(font_match.group(2))
            if font_match
            else (float(size_match.group(1)) if size_match else None),
            margins_in=float(margins) if margins else None,
        ),
        naming=_first(
            r"(?:named|naming convention|file name)[^:\"“]{0,40}[:\-]?\s*[\"“]?(<[^\n\"”]+>(?:[^\s\"”]*)?)",
            flat,
        ),
        signing=_sentence_with(
            text, "digitally signed", "digital signature", "signed and stamped", "dsc"
        ),
        emd=Emd(amount_inr=float(emd_amount.replace(",", "")), exemption=emd_exemption)
        if emd_amount
        else None,
        validity_days=int(v)
        if (v := _first(r"valid(?:ity)? (?:for|of) (\d{2,3}) days", flat))
        else None,
        eligibility=eligibility,
        forms=forms,
    )


# ---------------------------------------------------------------- evaluation criteria


def extract_criteria(variables: dict[str, Any]) -> CriteriaList:
    text = str(variables.get("text", ""))
    flat = normalize(PAGE_MARKER.sub(" ", text))
    criteria: list[CriterionOut] = []
    for page, line in _paged_lines(text):
        if " | " not in line:
            continue
        cells = [c.strip() for c in line.strip("| ").split(" | ")]
        if len(cells) < 3 or not re.match(r"^[A-Z]?\d+\.?$", cells[0]):
            continue
        marks = re.match(r"^(\d+(?:\.\d+)?)$", cells[-1])
        if not marks:
            continue
        subs = (
            [s.strip() for s in re.split(r";|,(?![^()]*\))", cells[2]) if s.strip()]
            if len(cells) > 3
            else []
        )
        criteria.append(
            CriterionOut(
                code=cells[0].rstrip("."),
                name=cells[1],
                max_marks=float(marks.group(1)),
                sub_criteria=subs,
                page=page,
            )
        )
    qcbs = (
        re.search(r"(\d{2})\s*:\s*(\d{2})", flat)
        if re.search(r"qcbs|weightage|weight", flat, re.I)
        else None
    )
    minimum = _first(
        r"minimum (?:qualifying )?(?:technical )?(?:score|marks) (?:of )?(\d{2,3})", flat
    )
    return CriteriaList(
        qcbs_split=f"{qcbs.group(1)}:{qcbs.group(2)}" if qcbs else None,
        min_qualifying_marks=float(minimum) if minimum else None,
        criteria=criteria,
    )


_CRITERION_HINTS: dict[str, tuple[str, ...]] = {
    "experience": ("eligibility",),
    "solution": (
        "functional",
        "technical",
        "security",
        "hosting",
        "integration",
        "general",
        "commercial",
    ),
    "approach": ("functional", "technical", "security", "hosting", "integration"),
    "implementation": ("implementation", "training"),
    "plan": ("implementation", "training"),
    "team": ("training",),
    "support": ("support", "sla"),
    "sla": ("support", "sla"),
    "maintenance": ("support", "sla"),
}


def link_criteria(variables: dict[str, Any]) -> CriterionLinks:
    criteria: list[dict[str, Any]] = list(variables.get("criteria_list", []))
    requirements: list[dict[str, Any]] = list(variables.get("requirement_list", []))
    links: list[CriterionLink] = []
    for index, req in enumerate(requirements):
        req_terms = key_terms(req["text"])
        best_code, best_score = None, 0.0
        for crit in criteria:
            crit_text = f"{crit['name']} {' '.join(crit.get('sub_criteria', []))}"
            score = float(len(req_terms & key_terms(crit_text)))
            name = crit["name"].lower()
            for hint, categories in _CRITERION_HINTS.items():
                if hint in name and req.get("category") in categories:
                    score += 1.5
            if score > best_score:
                best_code, best_score = crit["code"], score
        links.append(
            CriterionLink(
                requirement_index=index, criterion_code=best_code if best_score >= 1 else None
            )
        )
    return CriterionLinks(links=links)


# ---------------------------------------------------------------- drafting and review

_LEAD = {
    "fully_compliant": "We fully comply with this requirement.",
    "partially_compliant": "We partially comply with this requirement.",
}


def draft(variables: dict[str, Any]) -> DraftedResponse:
    requirement = str(variables.get("requirement", ""))
    evidence: list[dict[str, Any]] = list(variables.get("evidence_list", []))
    budget = int(variables.get("word_budget", 150))
    req_terms = key_terms(requirement)
    if ": " in requirement:
        # "The training should cover the following areas: X" is about X
        item_terms = key_terms(requirement.rsplit(": ", 1)[1])
        if len(item_terms) >= 2:
            req_terms = item_terms
    if not req_terms or not evidence:
        return DraftedResponse(
            answer="",
            status="gap",
            confidence=0.0,
            citations=[],
            gap_reason="No relevant evidence in the knowledge base.",
        )

    scored: list[tuple[float, int, str, set[str]]] = []
    for chunk in evidence:
        for raw_sentence in split_sentences(chunk["text"]):
            sentence = re.sub(r"^\d+\.\s+", "", raw_sentence)
            if len(sentence.split()) < 3:
                continue
            overlap = req_terms & key_terms(sentence)
            if len(overlap) < 2 or len(overlap) / len(req_terms) < 0.25:
                continue
            score = len(overlap) / len(req_terms) + 0.25 * float(chunk.get("score", 0))
            scored.append((score, int(chunk["chunk_id"]), sentence, overlap))
    scored.sort(key=lambda item: item[0], reverse=True)

    chosen: list[tuple[int, str]] = []
    covered: set[str] = set()
    total_words = 10
    for _, chunk_id, sentence, overlap in scored:
        if len(chosen) >= 3 or (not (overlap - covered) and chosen):
            continue
        if total_words + len(sentence.split()) > budget:
            continue
        chosen.append((chunk_id, sentence))
        covered |= overlap
        total_words += len(sentence.split())

    # Numbers in the requirement that the evidence contradicts lower the coverage.
    coverage = len(covered) / len(req_terms)
    if coverage < 0.34 or not chosen:
        missing = ", ".join(sorted(req_terms - covered)[:6])
        return DraftedResponse(
            answer="",
            status="gap",
            confidence=round(coverage, 2),
            citations=[],
            gap_reason=f"No evidence found in your documents for: {missing}.",
        )
    status = "fully_compliant" if coverage >= 0.6 else "partially_compliant"
    body = " ".join(_to_first_person(s) for _, s in chosen)
    return DraftedResponse(
        answer=f"{_LEAD[status]} {body}",
        status=status,
        confidence=round(min(0.95, 0.4 + coverage * 0.6), 2),
        citations=[CitationOut(chunk_id=cid, quote=s) for cid, s in chosen],
        gap_reason=None
        if status == "fully_compliant"
        else f"Not covered by evidence: {', '.join(sorted(req_terms - covered)[:6])}.",
    )


def _to_first_person(sentence: str) -> str:
    return sentence


def review(variables: dict[str, Any]) -> ReviewOutput:
    requirement = str(variables.get("requirement", ""))
    answer = str(variables.get("answer", ""))
    quotes: list[str] = list(variables.get("quote_list", []))
    answer_terms = key_terms(answer)
    parts = [
        p for p in re.split(r",|;|\band\b|\bincluding\b", requirement) if len(key_terms(p)) >= 2
    ]
    missing = []
    for part in parts:
        terms = key_terms(part)
        if terms and len(terms & answer_terms) / len(terms) < 0.34:
            missing.append(normalize(part).strip(" ."))
    unsupported = []
    quoted = " ".join(quotes).lower()
    for sentence in split_sentences(answer):
        if sentence in _LEAD.values():
            continue
        if re.search(r"\d", sentence) and normalize(sentence).lower() not in quoted:
            unsupported.append(sentence)
    numbers = len(re.findall(r"\d+", answer))
    proper = len(re.findall(r"(?<!^)(?<!\. )\b[A-Z][a-z]+", answer))
    specificity = (
        "high" if numbers >= 2 and proper >= 3 else "medium" if numbers or proper >= 3 else "low"
    )
    return ReviewOutput(
        missing_parts=missing[:5], unsupported_claims=unsupported[:5], specificity=specificity
    )


# ---------------------------------------------------------------- facts

_FACT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "headcount",
        re.compile(
            r"(\d{2,5})\s*(?:\+\s*)?(?:employees|professionals|people|staff members|-member team|member team)",
            re.I,
        ),
    ),
    (
        "years_in_business",
        re.compile(r"(\d{1,2})\+?\s+years (?:in business|of (?:experience|operations))", re.I),
    ),
    ("sla_response_hours", re.compile(r"(\d{1,2})[- ]hour (?:response|critical)", re.I)),
    ("uptime_percent", re.compile(r"(\d{2}\.\d{1,2})\s*%\s*(?:uptime|availability)", re.I)),
    (
        "hospitals_deployed",
        re.compile(r"(\d{1,4})\s+(?:district |public |government )?hospitals", re.I),
    ),
    (
        "staff_trained",
        re.compile(
            r"trained\s+(\d{2,5})|(\d{2,5})\s+(?:staff|users) (?:were |have been )?trained", re.I
        ),
    ),
    ("go_live_months", re.compile(r"go[- ]live (?:with)?in\s+(\d{1,2})\s+months", re.I)),
]


def extract_facts(variables: dict[str, Any]) -> FactList:
    answer = str(variables.get("answer", ""))
    facts: list[Fact] = []
    for key, pattern in _FACT_PATTERNS:
        for match in pattern.finditer(answer):
            value = next((g for g in match.groups() if g), None)
            if value:
                facts.append(Fact(key=key, value=value))
    return FactList(facts=facts)


# ---------------------------------------------------------------- provider

_HANDLERS: dict[str, Callable[[dict[str, Any]], BaseModel]] = {
    "classify_chunk": classify,
    "extract_requirements": extract_requirements,
    "extract_submission_rules": extract_rules,
    "extract_criteria": extract_criteria,
    "link_requirements_to_criteria": link_criteria,
    "draft_response": draft,
    "review_response": review,
    "extract_facts": extract_facts,
}


class OfflineLLM:
    name = "offline"

    def complete(
        self,
        prompt_name: str,
        variables: dict[str, Any],
        schema: type[T],
        usage: UsageMeter | None = None,
    ) -> LLMResult[T]:
        handler = _HANDLERS.get(prompt_name)
        if handler is None:
            raise LLMError(f"Offline provider has no handler for {prompt_name}")
        value = schema.model_validate(handler(variables).model_dump())
        return LLMResult(value=value, prompt_version=f"{prompt_name}@{VERSION}", model="offline")


__all__ = ["OfflineLLM", "words"]
