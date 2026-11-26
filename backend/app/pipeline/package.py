"""Package generation (F9): ready-to-sign bid documents as DOCX + PDF, matrices as XLSX, zipped.

One content model (a list of blocks) is rendered twice: to DOCX with python-docx and to PDF with
PyMuPDF's HTML Story, so no LibreOffice is needed. Format rules from the RFP (font, size, margins)
override the defaults.
"""

import html
import logging
import re
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pymupdf
from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.shared import Inches, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlmodel import Session, col, select

from app.jobs.runner import JobContext, register
from app.models import (
    Company,
    EvaluationCriterion,
    OutlineSection,
    Project,
    Requirement,
    Response,
    SubmissionRules,
    WinTheme,
)
from app.services.profile import check_eligibility, fill_form_text

logger = logging.getLogger(__name__)

STATUS_LABEL = {
    "fully_compliant": "Fully compliant",
    "partially_compliant": "Partially compliant",
    "compliant_with_customisation": "Compliant with customisation",
    "non_compliant": "Non-compliant",
    "gap": "Gap",
    "pending": "Not drafted",
}
STATUS_FILL = {
    "fully_compliant": "C6EFCE",
    "partially_compliant": "FFEB9C",
    "compliant_with_customisation": "DDEBF7",
    "non_compliant": "FFC7CE",
    "gap": "FFC7CE",
    "pending": "EDEDED",
}
PDF_FONT = {"times": "serif", "cambria": "serif", "georgia": "serif"}

# ---------------------------------------------------------------- content model


@dataclass
class Block:
    kind: str  # title | h1 | h2 | p | small | bullets | table | runs | pagebreak | spacer
    text: str = ""
    items: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    runs: list[tuple[str, bool]] = field(default_factory=list)  # (text, highlight)


@dataclass
class DocStyle:
    font: str = "Calibri"
    size: float = 11.0
    margins_in: float = 1.0
    header: str = ""
    footer: str = ""


def style_from_rules(rules: dict[str, Any], company: Company | None, project: Project) -> DocStyle:
    fmt = rules.get("format") or {}
    return DocStyle(
        font=fmt.get("font") or "Calibri",
        size=float(fmt.get("font_size") or 11),
        margins_in=float(fmt.get("margins_in") or 1.0),
        header=f"{company.legal_name if company else ''}    |    {project.tender_no}".strip(" |"),
        footer=company.legal_name if company else "",
    )


# ---------------------------------------------------------------- renderers


def render_docx(blocks: list[Block], style: DocStyle, path: Path) -> None:
    doc = Document()
    for section in doc.sections:
        margin = Inches(style.margins_in)
        section.left_margin = section.right_margin = section.top_margin = section.bottom_margin = (
            margin
        )
        if style.header:
            section.header.paragraphs[0].text = style.header
        if style.footer:
            section.footer.paragraphs[
                0
            ].text = f"{style.footer} — Signature and seal of authorised signatory"
    normal = doc.styles["Normal"]
    normal.font.name = style.font
    normal.font.size = Pt(style.size)
    for name, size in (
        ("Title", style.size + 11),
        ("Heading 1", style.size + 5),
        ("Heading 2", style.size + 2),
    ):
        heading_style = doc.styles[name]
        heading_style.font.name = style.font
        heading_style.font.size = Pt(size)
        heading_style.font.color.rgb = RGBColor(0x1F, 0x2A, 0x44)
    for block in blocks:
        if block.kind == "title":
            doc.add_paragraph(block.text, style="Title")
        elif block.kind == "h1":
            doc.add_heading(block.text, level=1)
        elif block.kind == "h2":
            doc.add_heading(block.text, level=2)
        elif block.kind in ("p", "small"):
            para = doc.add_paragraph(block.text)
            if block.kind == "small":
                for run in para.runs:
                    run.font.size = Pt(style.size - 1.5)
        elif block.kind == "bullets":
            for item in block.items:
                doc.add_paragraph(item, style="List Bullet")
        elif block.kind == "table" and block.rows:
            table = doc.add_table(rows=0, cols=len(block.rows[0]))
            table.style = "Table Grid"
            for r, row in enumerate(block.rows):
                cells = table.add_row().cells
                for c, value in enumerate(row):
                    cells[c].text = value
                    if r == 0:
                        for run in cells[c].paragraphs[0].runs:
                            run.bold = True
        elif block.kind == "runs":
            for line in _split_runs_by_line(block.runs):
                para = doc.add_paragraph()
                for text, highlight in line:
                    run = para.add_run(text)
                    if highlight:
                        run.font.highlight_color = WD_COLOR_INDEX.YELLOW
        elif block.kind == "pagebreak":
            doc.add_page_break()
        elif block.kind == "spacer":
            doc.add_paragraph("")
    doc.save(str(path))


def _split_runs_by_line(runs: list[tuple[str, bool]]) -> list[list[tuple[str, bool]]]:
    lines: list[list[tuple[str, bool]]] = [[]]
    for text, highlight in runs:
        parts = text.split("\n")
        for i, part in enumerate(parts):
            if i > 0:
                lines.append([])
            if part:
                lines[-1].append((part, highlight))
    return [line for line in lines if line] or [[("", False)]]


def _html(blocks: list[Block]) -> str:
    out: list[str] = []
    for block in blocks:
        esc = html.escape(block.text)
        if block.kind == "title":
            out.append(f'<h1 class="title">{esc}</h1>')
        elif block.kind == "h1":
            out.append(f"<h2>{esc}</h2>")
        elif block.kind == "h2":
            out.append(f"<h3>{esc}</h3>")
        elif block.kind == "p":
            out.append(f"<p>{esc}</p>")
        elif block.kind == "small":
            out.append(f'<p class="small">{esc}</p>')
        elif block.kind == "bullets":
            out.append(
                "<ul>" + "".join(f"<li>{html.escape(i)}</li>" for i in block.items) + "</ul>"
            )
        elif block.kind == "table" and block.rows:
            head = "".join(f"<th>{html.escape(c)}</th>" for c in block.rows[0])
            body = "".join(
                "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>"
                for row in block.rows[1:]
            )
            out.append(f"<table><tr>{head}</tr>{body}</table>")
        elif block.kind == "runs":
            for line in _split_runs_by_line(block.runs):
                spans = "".join(
                    f'<span style="background-color:#fff176">{html.escape(t)}</span>'
                    if h
                    else html.escape(t)
                    for t, h in line
                )
                out.append(f"<p>{spans}</p>")
        elif block.kind == "pagebreak":
            out.append('<p class="break"></p>')
        elif block.kind == "spacer":
            out.append("<p>&#160;</p>")
    return "\n".join(out)


def render_pdf(blocks: list[Block], style: DocStyle, path: Path) -> int:
    family = PDF_FONT.get(style.font.split()[0].lower(), "sans-serif")
    css = f"""
    * {{ font-family: {family}; font-size: {style.size}pt; line-height: 1.35; }}
    h1.title {{ font-size: {style.size + 11}pt; color: #1f2a44; margin-top: 120px; }}
    h2 {{ font-size: {style.size + 4}pt; color: #1f2a44; margin-top: 14px; }}
    h3 {{ font-size: {style.size + 1.5}pt; color: #1f2a44; margin-top: 10px; }}
    p.small {{ font-size: {style.size - 1.5}pt; color: #444444; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #999999; padding: 3px; font-size: {style.size - 2}pt; vertical-align: top; }}
    th {{ font-weight: bold; }}
    p.break {{ page-break-after: always; }}
    """
    mediabox = pymupdf.paper_rect("a4")
    margin = style.margins_in * 72
    where = pymupdf.Rect(
        margin, margin + 10, mediabox.width - margin, mediabox.height - margin - 10
    )
    blocks_by_page = _split_pages(blocks)
    writer = pymupdf.DocumentWriter(str(path))
    for page_blocks in blocks_by_page:
        story = pymupdf.Story(html=_html(page_blocks), user_css=css)
        more = True
        while more:
            device = writer.begin_page(mediabox)
            more, _ = story.place(where)
            story.draw(device)
            writer.end_page()
    writer.close()
    with pymupdf.open(path) as doc:
        total = doc.page_count
        for number, page in enumerate(doc, start=1):
            if style.header:
                page.insert_text(
                    (margin, margin - 8), style.header, fontsize=8, color=(0.35, 0.35, 0.35)
                )
            footer = f"{style.footer}    Page {number} of {total}    Signature & seal: ____________"
            page.insert_text(
                (margin, mediabox.height - margin + 18),
                footer,
                fontsize=8,
                color=(0.35, 0.35, 0.35),
            )
        doc.saveIncr()
    return int(total)


def _split_pages(blocks: list[Block]) -> list[list[Block]]:
    pages: list[list[Block]] = [[]]
    for block in blocks:
        if block.kind == "pagebreak":
            pages.append([])
        else:
            pages[-1].append(block)
    return [p for p in pages if p]


# ---------------------------------------------------------------- data


@dataclass
class PackageData:
    project: Project
    company: Company | None
    rules: dict[str, Any]
    rows: list[tuple[Requirement, Response | None]]
    criteria: dict[int, EvaluationCriterion]
    sections: list[OutlineSection]
    themes: list[str]
    eligibility: list[dict[str, Any]]


def load_data(session: Session, project: Project) -> PackageData:
    assert project.id is not None
    rules_row = session.exec(
        select(SubmissionRules).where(col(SubmissionRules.project_id) == project.id)
    ).first()
    rules = rules_row.rules if rules_row else {}
    reqs = list(
        session.exec(
            select(Requirement)
            .where(
                col(Requirement.project_id) == project.id,
                col(Requirement.version_status) != "removed",
            )
            .order_by(col(Requirement.order))
        ).all()
    )
    responses = {
        r.requirement_id: r
        for r in session.exec(
            select(Response).where(col(Response.requirement_id).in_([q.id for q in reqs]))
        ).all()
    }
    company = session.get(Company, project.company_id)
    return PackageData(
        project=project,
        company=company,
        rules=rules,
        rows=[(q, responses.get(q.id or 0)) for q in reqs],
        criteria={
            c.id: c
            for c in session.exec(
                select(EvaluationCriterion).where(col(EvaluationCriterion.project_id) == project.id)
            ).all()
            if c.id
        },
        sections=list(
            session.exec(
                select(OutlineSection)
                .where(col(OutlineSection.project_id) == project.id)
                .order_by(col(OutlineSection.order))
            ).all()
        ),
        themes=[
            t.text
            for t in session.exec(
                select(WinTheme)
                .where(col(WinTheme.project_id) == project.id)
                .order_by(col(WinTheme.order))
            ).all()
        ],
        eligibility=check_eligibility(session, company, rules.get("eligibility", [])),
    )


def _today() -> str:
    return datetime.now(UTC).strftime("%d %B %Y")


def _usable(resp: Response | None) -> bool:
    return bool(resp and resp.answer and resp.status != "gap")


# ---------------------------------------------------------------- documents


def covering_letter(d: PackageData) -> list[Block]:
    c, p = d.company, d.project
    name = c.legal_name if c else "[Bidder name]"
    validity = f" ({d.rules['validity_days']} days)" if d.rules.get("validity_days") else ""
    return [
        Block("h1", name),
        Block(
            "small",
            f"{c.address if c else ''}  |  {c.email if c else ''}  |  {c.phone if c else ''}",
        ),
        Block("spacer"),
        Block("p", f"Ref: {p.tender_no or '[Tender number]'}"),
        Block("p", f"Date: {_today()}"),
        Block("spacer"),
        Block("p", "To,"),
        Block("p", p.buyer or "[Name of the tender inviting authority]"),
        Block("spacer"),
        Block("p", f"Subject: Submission of bid for {p.title or 'the above tender'}"),
        Block("spacer"),
        Block("p", "Dear Sir / Madam,"),
        Block(
            "p",
            f"We, {name}, having examined the tender document{', including all corrigenda,' if any(q.version_status != 'unchanged' for q, _ in d.rows) else ''} "
            f"hereby submit our technical and financial proposal for {p.title or 'the above tender'} in accordance with the "
            "terms and conditions of the tender.",
        ),
        Block(
            "p",
            "We confirm that the information furnished in our bid is true and correct, that our bid remains valid for the "
            f"period stated in the tender{validity}, and that we accept all terms and conditions of the tender.",
        ),
        Block("spacer"),
        Block("p", "Yours faithfully,"),
        Block("spacer"),
        Block("p", "Signature and seal: ______________________"),
        Block(
            "p", f"Name: {c.signatory_name if c and c.signatory_name else '[Authorised signatory]'}"
        ),
        Block(
            "p",
            f"Designation: {c.signatory_designation if c and c.signatory_designation else '[Designation]'}",
        ),
        Block("p", f"For and on behalf of {name}"),
    ]


def technical_proposal(d: PackageData) -> list[Block]:
    c, p = d.company, d.project
    name = c.legal_name if c else "the bidder"
    usable = [(q, r) for q, r in d.rows if _usable(r)]
    full = sum(1 for _, r in usable if r and r.status == "fully_compliant")
    blocks: list[Block] = [
        Block("title", "Technical Proposal"),
        Block("p", p.title or ""),
        Block("p", f"Tender No: {p.tender_no}"),
        Block("p", f"Submitted to: {p.buyer}"),
        Block("p", f"Submitted by: {name}"),
        Block("p", f"Date: {_today()}"),
        Block("pagebreak"),
    ]
    section_titles = [s.title for s in d.sections] or [
        "Executive Summary",
        "Company Profile",
        "Compliance Responses",
    ]
    blocks += [
        Block("h1", "Contents"),
        Block(
            "bullets",
            items=[
                f"{i + 1}. {t}"
                for i, t in enumerate(
                    [*section_titles, "Compliance Summary", "Deviations and Assumptions"]
                )
            ],
        ),
        Block("pagebreak"),
    ]

    def executive_summary(number: int) -> list[Block]:
        out = [
            Block("h1", f"{number}. Executive Summary"),
            Block(
                "p",
                f"{name} is pleased to submit this proposal for {p.title or 'the tender'}. "
                f"This proposal responds to all {len(d.rows)} requirements identified in the tender; "
                f"{full} are met in full and every answer is supported by evidence from our documents.",
            ),
        ]
        if d.themes:
            out += [Block("p", "Why us:"), Block("bullets", items=d.themes)]
        return out

    def company_profile(number: int) -> list[Block]:
        if c is None:
            return [
                Block("h1", f"{number}. Company Profile"),
                Block("p", "Company profile not provided."),
            ]
        rows = [["Item", "Details"], ["Legal name", c.legal_name], ["Address", c.address]]
        if c.year_established:
            rows.append(["Established", str(c.year_established)])
        for label, value in (
            ("GSTIN", c.gstin),
            ("PAN", c.pan),
            ("Udyam registration", c.udyam_no),
        ):
            if value:
                rows.append([label, value])
        out = [Block("h1", f"{number}. Company Profile"), Block("table", rows=rows)]
        if c.turnover:
            out += [
                Block("h2", "Annual turnover"),
                Block(
                    "table",
                    rows=[["Financial year", "Turnover (INR crore)"]]
                    + [
                        [str(t.get("fy")), f"{float(t.get('amount_inr') or 0) / 1e7:.2f}"]
                        for t in c.turnover
                    ],
                ),
            ]
        if c.certifications:
            out += [
                Block("h2", "Certifications"),
                Block(
                    "table",
                    rows=[["Certification", "Number", "Valid until"]]
                    + [
                        [
                            str(x.get("name", "")),
                            str(x.get("number", "")),
                            str(x.get("valid_until", "")),
                        ]
                        for x in c.certifications
                    ],
                ),
            ]
        return out

    def responses_block(rows: list[tuple[Requirement, Response | None]]) -> list[Block]:
        out: list[Block] = []
        for req, resp in rows:
            if not _usable(resp):
                continue
            assert resp is not None
            out.append(Block("h2", f"{req.req_code}  {req.text}"))
            out.append(Block("p", resp.answer or ""))
            sources = "; ".join(sorted({f"{x['filename']} p.{x['page']}" for x in resp.citations}))
            if sources:
                out.append(
                    Block(
                        "small",
                        f"Compliance: {STATUS_LABEL.get(resp.status, resp.status)}. Evidence: {sources}",
                    )
                )
        return out or [Block("p", "No responses in this section yet.")]

    number = 0
    if d.sections:
        for section in d.sections:
            number += 1
            if section.title == "Executive Summary":
                blocks += executive_summary(number)
            elif section.title == "Company Profile":
                blocks += company_profile(number)
            else:
                rows = [(q, r) for q, r in d.rows if q.outline_section_id == section.id]
                blocks += [Block("h1", f"{number}. {section.title}"), *responses_block(rows)]
    else:
        blocks += [
            *executive_summary(1),
            *company_profile(2),
            Block("h1", "3. Compliance Responses"),
            *responses_block(d.rows),
        ]
        number = 3

    summary = [["ID", "Requirement", "Type", "Status"]] + [
        [
            q.req_code,
            q.text[:110] + ("…" if len(q.text) > 110 else ""),
            q.type,
            STATUS_LABEL.get(r.status if r else "pending", ""),
        ]
        for q, r in d.rows
    ]
    blocks += [
        Block("pagebreak"),
        Block("h1", f"{number + 1}. Compliance Summary"),
        Block("table", rows=summary),
    ]
    deviations = [
        (q, r)
        for q, r in d.rows
        if r is None or r.status in ("gap", "partially_compliant", "non_compliant", "pending")
    ]
    blocks += [Block("h1", f"{number + 2}. Deviations and Assumptions")]
    if deviations:
        blocks.append(
            Block(
                "table",
                rows=[["ID", "Requirement", "Status", "Note"]]
                + [
                    [
                        q.req_code,
                        q.text[:100],
                        STATUS_LABEL.get(r.status if r else "pending", ""),
                        (r.gap_reason or "") if r else "Not drafted",
                    ]
                    for q, r in deviations
                ],
            )
        )
    else:
        blocks.append(Block("p", "No deviations: all requirements are met in full."))
    return blocks


def annexures(d: PackageData) -> list[Block]:
    blocks: list[Block] = []
    forms = d.rules.get("forms", [])
    financial = re.compile(r"boq|bill of quantit|financial|price|commercial", re.I)
    for i, form in enumerate(f for f in forms if not financial.search(str(f.get("title", "")))):
        if i:
            blocks.append(Block("pagebreak"))
        blocks.append(Block("h1", f"{form.get('code')}: {form.get('title')}"))
        blocks.append(
            Block("runs", runs=fill_form_text(str(form.get("text", "")), d.company, d.project))
        )
        blocks.append(Block("spacer"))
        blocks.append(
            Block("p", "Signature and seal of authorised signatory: ______________________")
        )
    if not blocks:
        blocks = [Block("h1", "Annexures"), Block("p", "The tender did not include fill-in forms.")]
    return blocks


def eligibility_checklist(d: PackageData) -> list[Block]:
    rows = [["#", "Criterion", "Evidence to attach", "Status", "Note"]] + [
        [
            str(i + 1),
            str(e.get("criterion", "")),
            str(e.get("evidence", "")),
            {"met": "Ready", "missing": "MISSING", "manual": "Check"}[e["status"]],
            str(e.get("reason", "")),
        ]
        for i, e in enumerate(d.eligibility)
    ]
    return [
        Block("h1", "Eligibility Checklist"),
        Block("p", f"{d.project.title} — {d.project.tender_no}"),
        Block("table", rows=rows)
        if len(rows) > 1
        else Block("p", "No eligibility criteria were found in the tender."),
    ]


def readme(d: PackageData, files: list[str]) -> list[Block]:
    r = d.rules
    fmt = r.get("format") or {}
    deadline = (
        d.project.deadline.strftime("%d %B %Y, %H:%M") if d.project.deadline else "Not stated"
    )
    blocks = [
        Block("h1", "Submission Checklist"),
        Block(
            "table",
            rows=[
                ["Item", "Value"],
                ["Tender", f"{d.project.title} ({d.project.tender_no})"],
                ["Deadline", deadline],
                ["Portal", r.get("portal") or "Not stated"],
                ["Bid system", (r.get("bid_system") or "Not stated").replace("_", " ")],
                ["Page limit", str(fmt.get("page_limit") or "Not stated")],
                ["Font", f"{fmt.get('font') or 'Not stated'} {fmt.get('font_size') or ''}".strip()],
                ["File naming", r.get("naming") or "Not stated"],
                [
                    "EMD",
                    f"INR {r['emd']['amount_inr']:,.0f}"
                    if r.get("emd") and r["emd"].get("amount_inr")
                    else "Not stated",
                ],
            ],
        ),
    ]
    if r.get("emd") and r["emd"].get("exemption"):
        blocks.append(Block("small", f"EMD exemption: {r['emd']['exemption']}"))
    for cover in r.get("covers", []):
        blocks += [
            Block("h2", cover.get("name", "Cover")),
            Block("bullets", items=list(cover.get("documents", []))),
        ]
    blocks += [
        Block("h2", "Files in this package"),
        Block("bullets", items=files),
        Block("h2", "Steps that need a person"),
        Block(
            "bullets",
            items=[
                "Review and approve every answer in BidReady before final submission.",
                "Enter prices in the financial bid template.",
                "Print, sign and stamp where required; apply the Class 3 DSC"
                if r.get("signing")
                else "Sign documents as required by the tender.",
                f"Upload to {r.get('portal') or 'the tender portal'} before the deadline.",
            ],
        ),
    ]
    if r.get("signing"):
        blocks.append(Block("small", f"Signing rule: {r['signing']}"))
    return blocks


# ---------------------------------------------------------------- spreadsheets


def compliance_matrix_xlsx(d: PackageData, path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Compliance Matrix"
    header = [
        "ID",
        "Section",
        "Page",
        "Requirement",
        "Mandatory",
        "Criterion",
        "Status",
        "Response",
        "Evidence",
        "Review score",
    ]
    ws.append(header)
    for req, resp in d.rows:
        crit = d.criteria.get(req.criterion_id) if req.criterion_id else None
        ws.append(
            [
                req.req_code,
                req.section_path,
                req.page,
                req.text,
                "Yes" if req.type == "mandatory" else "No",
                crit.name if crit else "",
                STATUS_LABEL.get(resp.status if resp else "pending", ""),
                (resp.answer or resp.gap_reason or "") if resp else "",
                "; ".join(
                    f"{c['filename']} p.{c['page']}" for c in (resp.citations if resp else [])
                ),
                resp.review_score if resp and resp.review_score is not None else "",
            ]
        )
        status = resp.status if resp else "pending"
        ws.cell(row=ws.max_row, column=7).fill = PatternFill(
            "solid", fgColor=STATUS_FILL.get(status, "FFFFFF")
        )
    widths = [11, 24, 6, 60, 10, 24, 22, 70, 30, 10]
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    for row in ws.iter_rows(min_row=1):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2952CC")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    if ws.sheet_properties.pageSetUpPr is not None:
        ws.sheet_properties.pageSetUpPr.fitToPage = True
    wb.save(str(path))


def boq_xlsx(d: PackageData, path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Financial Bid (BoQ)"
    form = next(
        (
            f
            for f in d.rules.get("forms", [])
            if re.search(r"boq|bill of quantit|financial|price", str(f.get("title", "")), re.I)
        ),
        None,
    )
    rows: list[list[str]] = []
    if form:
        rows = [
            [c.strip() for c in line.strip("| ").split(" | ")]
            for line in str(form.get("text", "")).splitlines()
            if " | " in line
        ]
    if not rows:
        rows = [["S.No", "Item", "Quantity", "Unit", "Unit rate (INR)", "GST %", "Total (INR)"]]
    header = rows[0]
    price_cols = {
        i for i, h in enumerate(header) if re.search(r"rate|amount|total|price|cost|gst", h, re.I)
    }
    ws.append(
        [
            f"{d.project.tender_no} — Financial bid template. Enter prices yourself; BidReady never fills prices."
        ]
    )
    ws.append(header)
    for row in rows[1:]:
        ws.append(["" if i in price_cols else value for i, value in enumerate(row)])
    for cell in ws[2]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="E8ECF5")
    for i in range(1, len(header) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 18 if i != 2 else 50
    ws.freeze_panes = "A3"
    wb.save(str(path))


# ---------------------------------------------------------------- naming and job


def file_name(d: PackageData, number: int, doc_name: str, ext: str) -> str:
    company = d.company.short_name or d.company.legal_name if d.company else "Bidder"
    tender = re.sub(r"[^A-Za-z0-9-]+", "-", d.project.tender_no or "Tender").strip("-")
    bidder = re.sub(r"[^A-Za-z0-9]+", "", company or "Bidder")
    rule = str(d.rules.get("naming") or "")
    if "<" in rule and ">" in rule:
        name = re.sub(r"<\s*tender[^>]*>", tender, rule, flags=re.I)
        name = re.sub(r"<\s*(bidder|company|firm)[^>]*>", bidder, name, flags=re.I)
        name = re.sub(
            r"<\s*(document|doc|file)[^>]*>", f"{number:02d}_{doc_name}", name, flags=re.I
        )
        name = re.sub(r"<[^>]*>", "", name)
        name = re.sub(r"\.(pdf|docx|xlsx)$", "", name.strip(), flags=re.I)
        name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")
        if name:
            return f"{name}.{ext}"
    return f"{tender}_{bidder}_{number:02d}_{doc_name}.{ext}"


def build_package(
    session: Session, project: Project, out_dir: Path
) -> tuple[Path, list[dict[str, Any]]]:
    d = load_data(session, project)
    style = style_from_rules(d.rules, d.company, project)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.iterdir():
        if old.is_file():
            old.unlink()
    produced: list[dict[str, Any]] = []

    def both(number: int, doc_name: str, blocks: list[Block], label: str) -> None:
        pdf = out_dir / file_name(d, number, doc_name, "pdf")
        docx = out_dir / file_name(d, number, doc_name, "docx")
        pages = render_pdf(blocks, style, pdf)
        render_docx(blocks, style, docx)
        produced.append({"name": pdf.name, "label": label, "format": "pdf", "pages": pages})
        produced.append({"name": docx.name, "label": label, "format": "docx", "pages": None})

    both(1, "Covering_Letter", covering_letter(d), "Covering letter")
    both(2, "Technical_Proposal", technical_proposal(d), "Technical proposal")
    matrix = out_dir / file_name(d, 3, "Compliance_Matrix", "xlsx")
    compliance_matrix_xlsx(d, matrix)
    produced.append(
        {"name": matrix.name, "label": "Compliance matrix", "format": "xlsx", "pages": None}
    )
    both(4, "Annexures_Filled", annexures(d), "Filled annexures")
    both(5, "Eligibility_Checklist", eligibility_checklist(d), "Eligibility checklist")
    boq = out_dir / file_name(d, 6, "Financial_Bid_Template", "xlsx")
    boq_xlsx(d, boq)
    produced.append(
        {
            "name": boq.name,
            "label": "Financial bid template (prices left blank)",
            "format": "xlsx",
            "pages": None,
        }
    )
    readme_pdf = out_dir / "README_Submission_Checklist.pdf"
    pages = render_pdf(
        readme(d, [f["name"] for f in produced] + [readme_pdf.name]), style, readme_pdf
    )
    produced.append(
        {"name": readme_pdf.name, "label": "Submission checklist", "format": "pdf", "pages": pages}
    )

    tender = re.sub(r"[^A-Za-z0-9-]+", "-", project.tender_no or f"project-{project.id}").strip("-")
    zip_path = out_dir.parent / f"{tender}_bid_package.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in produced:
            archive.write(out_dir / item["name"], arcname=f"{tender}/{item['name']}")
    return zip_path, produced


@register("package")
def package_job(ctx: JobContext) -> None:
    project_id = int(ctx.params["project_id"])
    with Session(ctx.engine) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")
        ctx.progress("rendering", 20, "Rendering documents")
        out_dir = ctx.settings.files_dir / "packages" / f"project-{project_id}" / "files"
        zip_path, produced = build_package(session, project, out_dir)
        project.package_path = str(zip_path)
        project.package_files = produced
        project.status = "packaged"
        session.add(project)
        session.commit()
        ctx.progress("done", 100, f"Generated {len(produced)} files", files=len(produced))
