"""Company-profile helpers: fill form fields and check eligibility criteria against the profile."""

import re
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, select

from app.models import Company, KnowledgeDoc, Project
from app.pipeline.textutil import key_terms

_FIELD_RULES: list[tuple[tuple[str, ...], str]] = [
    (("tender", "rfp", "reference"), "tender_no"),
    (("signatory", "authori"), "signatory_name"),
    (("designation",), "signatory_designation"),
    (("gst",), "gstin"),
    (("pan",), "pan"),
    (("udyam", "msme"), "udyam_no"),
    (("email", "e_mail"), "email"),
    (("phone", "mobile", "telephone", "contact_no"), "phone"),
    (("website",), "website"),
    (("address", "registered_office"), "address"),
    (("year", "established", "incorporat"), "year_established"),
    (("date",), "today"),
    (("place", "city"), "city"),
    (("buyer", "purchaser", "addressee"), "buyer"),
    (("bidder", "company", "firm", "organisation", "organization", "name"), "legal_name"),
]


def resolve_field(field: str, company: Company | None, project: Project | None) -> str | None:
    name = field.lower()
    for needles, target in _FIELD_RULES:
        if not any(n in name for n in needles):
            continue
        if target == "today":
            return datetime.now(UTC).strftime("%d %B %Y")
        if target == "tender_no":
            return project.tender_no if project and project.tender_no else None
        if target == "buyer":
            return project.buyer if project and project.buyer else None
        if company is None:
            return None
        if target == "city":
            parts = [p.strip() for p in company.address.split(",") if p.strip()]
            return parts[-2] if len(parts) >= 2 else (parts[0] if parts else None)
        value = getattr(company, target, None)
        return str(value) if value not in (None, "") else None
    return None


def fill_form_text(
    text: str, company: Company | None, project: Project | None
) -> list[tuple[str, bool]]:
    """Return runs of (text, unfilled) with placeholders replaced by profile values."""
    runs: list[tuple[str, bool]] = []
    position = 0
    for match in re.finditer(r"\[([^\]]{2,60})\]|<([^>]{2,60})>|_{5,}", text):
        runs.append((text[position : match.start()], False))
        label = match.group(1) or match.group(2) or ""
        value = (
            resolve_field(re.sub(r"[^a-z0-9]+", "_", label.lower()), company, project)
            if label
            else None
        )
        if value:
            runs.append((value, False))
        else:
            runs.append((match.group(0), True))
        position = match.end()
    runs.append((text[position:], False))
    return [r for r in runs if r[0]]


def unfilled_fields(
    form: dict[str, Any], company: Company | None, project: Project | None
) -> list[str]:
    return [f for f in form.get("fields", []) if resolve_field(f, company, project) is None]


def check_eligibility(
    session: Session, company: Company | None, items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Classify each eligibility criterion as met / missing / manual with a reason."""
    docs = list(
        session.exec(
            select(KnowledgeDoc).where(
                col(KnowledgeDoc.company_id) == (company.id if company else -1)
            )
        ).all()
    )
    doc_types = {d.doc_type for d in docs}
    cert_names = (
        " ".join(c.get("name", "") for c in company.certifications).lower() if company else ""
    )
    results: list[dict[str, Any]] = []
    for item in items:
        criterion = str(item.get("criterion", ""))
        low = criterion.lower()
        status, reason = "manual", "Check this criterion manually."
        if "turnover" in low:
            amounts = re.findall(r"(?:inr|rs\.?|₹)\s*([\d.,]+)\s*(crore|cr|lakh)?", low)
            need = 0.0
            if amounts:
                number, unit = amounts[0]
                need = float(number.replace(",", "")) * (
                    1e7 if unit in ("crore", "cr") else 1e5 if unit == "lakh" else 1
                )
            turnover = [
                float(t.get("amount_inr") or 0) for t in (company.turnover if company else [])
            ]
            if not turnover:
                status, reason = "missing", "Add turnover by year to the company profile."
            else:
                recent = turnover[-3:]
                average = sum(recent) / len(recent)
                ok = average >= need if need else True
                status = "met" if ok else "missing"
                reason = f"Average of last {len(recent)} years: INR {average / 1e7:.2f} crore" + (
                    "" if ok else f" (needs {need / 1e7:.2f} crore)"
                )
        elif any(k in low for k in ("iso", "cmmi", "certif")):
            needed = re.findall(r"(iso\s*\d{4,5}|cmmi[^,;.]*level\s*\d|cmmi\s*level\s*\d)", low)
            missing = [n for n in needed if not all(t in cert_names for t in key_terms(n))]
            if needed and not missing:
                status, reason = "met", "Certificates listed in the company profile."
            elif needed:
                status, reason = (
                    "missing",
                    "Not in profile: " + ", ".join(m.upper() for m in missing),
                )
        elif any(k in low for k in ("experience", "similar", "projects", "work order")):
            if doc_types & {"case_study", "past_proposal"}:
                status, reason = "met", "Past proposals / case studies are in the knowledge base."
            else:
                status, reason = "missing", "Upload case studies or past proposals as evidence."
        elif any(k in low for k in ("registered", "incorporat", "established")):
            if company and company.year_established:
                years = datetime.now(UTC).year - company.year_established
                need_years = re.findall(r"(\d+)\s*years", low)
                ok = not need_years or years >= int(need_years[0])
                status = "met" if ok else "missing"
                reason = f"Established {company.year_established} ({years} years)."
            else:
                status, reason = "missing", "Add the year of establishment to the company profile."
        elif "blacklist" in low or "debarred" in low:
            status, reason = "manual", "Self-declaration required (see annexures)."
        results.append({**item, "status": status, "reason": reason})
    return results
