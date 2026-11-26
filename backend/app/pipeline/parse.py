"""Parse PDF / DOCX into pages of ordered lines and table rows.

Table rows are rendered as `cell | cell | cell` lines so both Claude and the offline provider
can read them. Running headers/footers (repeated on most pages) are dropped.
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from app.pipeline.textutil import normalize

logger = logging.getLogger(__name__)
_PAGE_FOOTER = re.compile(r"^(page\s*)?\d+\s*(of\s*\d+)?$|\bpage\s*\d+\s*of\s*\d+\s*$", re.I)


@dataclass
class Line:
    text: str
    size: float = 11.0
    bold: bool = False
    is_table_row: bool = False


@dataclass
class ParsedPage:
    page: int
    lines: list[Line] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


@dataclass
class ParsedDocument:
    pages: list[ParsedPage]
    warnings: list[str] = field(default_factory=list)

    @property
    def body_font_size(self) -> float:
        sizes = Counter(
            round(line.size) for p in self.pages for line in p.lines if not line.is_table_row
        )
        return float(sizes.most_common(1)[0][0]) if sizes else 11.0


def parse_document(path: Path, kind: str, *, ocr: bool = True) -> ParsedDocument:
    if kind == "pdf":
        return _parse_pdf(path, ocr=ocr)
    if kind == "docx":
        return _parse_docx(path)
    raise ValueError(f"Unsupported document kind: {kind}")


def _cell(value: object) -> str:
    return normalize(str(value)) if value is not None else ""


def _parse_pdf(path: Path, *, ocr: bool) -> ParsedDocument:
    pages: list[ParsedPage] = []
    warnings: list[str] = []
    with pymupdf.open(path) as doc:
        for index, page in enumerate(doc, start=1):
            items: list[tuple[float, list[Line]]] = []
            table_boxes: list[pymupdf.Rect] = []
            try:
                tables = page.find_tables()
                for table in tables.tables:
                    rows = [
                        [
                            _cell(page.get_text("text", clip=pymupdf.Rect(cell)).replace("\n", " "))
                            if cell
                            else ""
                            for cell in row.cells
                        ]
                        for row in table.rows
                    ]
                    rows = [r for r in rows if any(r)]
                    width = max((len(r) for r in rows), default=0)
                    keep = [
                        i for i in range(width) if any(i < len(r) and len(r[i]) >= 2 for r in rows)
                    ]
                    rows = [[r[i] if i < len(r) else "" for i in keep] for r in rows]
                    rows = [r for n, r in enumerate(rows) if r not in rows[:n]]
                    rows = _merge_split_header([r for r in rows if any(len(c) >= 2 for c in r)])
                    if len(rows) < 2 or max(len(r) for r in rows) < 2:
                        continue
                    table_boxes.append(pymupdf.Rect(table.bbox))
                    lines = [Line(text=" | ".join(r), is_table_row=True) for r in rows]
                    items.append((table.bbox[1], lines))
            except Exception:  # table detection is best effort
                logger.warning("Table detection failed on page %s", index)

            data = page.get_text("dict")
            for block in data.get("blocks", []):
                for raw_line in block.get("lines", []):
                    spans = [s for s in raw_line.get("spans", []) if s.get("text", "").strip()]
                    if not spans:
                        continue
                    bbox = pymupdf.Rect(raw_line["bbox"])
                    if any(
                        box.contains(bbox) or (box.intersects(bbox) and _overlap(box, bbox) > 0.6)
                        for box in table_boxes
                    ):
                        continue
                    text = normalize("".join(s["text"] for s in spans))
                    size = max(float(s.get("size", 11)) for s in spans)
                    bold = any(
                        (int(s.get("flags", 0)) & 16) or "bold" in str(s.get("font", "")).lower()
                        for s in spans
                    )
                    items.append((bbox.y0, [Line(text=text, size=size, bold=bold)]))

            if sum(len(line.text) for _, group in items for line in group) < 50 and ocr:
                items = _ocr_page(page, warnings, index) or items

            items.sort(key=lambda item: item[0])
            pages.append(
                ParsedPage(page=index, lines=[line for _, group in items for line in group])
            )
    _drop_running_lines(pages)
    return ParsedDocument(pages=pages, warnings=warnings)


def _merge_split_header(rows: list[list[str]]) -> list[list[str]]:
    """Merge a header that was split over two rows (complementary empty cells)."""
    if len(rows) >= 2 and len(rows[0]) == len(rows[1]):
        first, second = rows[0], rows[1]
        if all(not a or not b for a, b in zip(first, second, strict=True)) and not any(
            c.replace(",", "").isdigit() for c in second
        ):
            return [[a or b for a, b in zip(first, second, strict=True)], *rows[2:]]
    return rows


def _overlap(box: pymupdf.Rect, line: pymupdf.Rect) -> float:
    inter = pymupdf.Rect(box) & line
    area = line.get_area()
    return inter.get_area() / area if area else 0.0


def _ocr_page(
    page: pymupdf.Page, warnings: list[str], index: int
) -> list[tuple[float, list[Line]]]:
    try:
        textpage = page.get_textpage_ocr(full=True)
        text = page.get_text("text", textpage=textpage)
    except Exception:
        warnings.append(f"Page {index} looks scanned but OCR is unavailable (install Tesseract).")
        return []
    return [
        (float(i), [Line(text=normalize(t))]) for i, t in enumerate(text.splitlines()) if t.strip()
    ]


def _drop_running_lines(pages: list[ParsedPage]) -> None:
    if len(pages) < 3:
        return
    counts = Counter(line.text for p in pages for line in {ln.text: ln for ln in p.lines}.values())
    running = {
        text for text, n in counts.items() if n >= max(3, len(pages) * 0.6) and len(text) < 120
    }
    for p in pages:
        p.lines = [
            ln
            for ln in p.lines
            if ln.text not in running and not (len(ln.text) < 120 and _PAGE_FOOTER.search(ln.text))
        ]


def _parse_docx(path: Path) -> ParsedDocument:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(str(path))
    lines: list[Line] = []
    for element in document.element.body.iterchildren():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(element, document)
            text = normalize(para.text)
            if not text:
                continue
            style = (para.style.name or "").lower() if para.style is not None else ""
            heading = style.startswith("heading") or style == "title"
            bold = heading or any(run.bold for run in para.runs if run.text.strip())
            level = re.findall(r"\d+", style)
            size = 16.0 - (int(level[0]) if level else 3) if heading else 11.0
            lines.append(Line(text=text, size=size, bold=bold))
        elif tag == "tbl":
            table = Table(element, document)
            for row in table.rows:
                cells: list[str] = []
                for cell in row.cells:
                    value = normalize(cell.text)
                    if not cells or cells[-1] != value:
                        cells.append(value)
                if any(cells):
                    lines.append(Line(text=" | ".join(cells), is_table_row=True))
    # DOCX has no fixed pages: group ~45 lines per pseudo-page for citations.
    pages = [
        ParsedPage(page=i // 45 + 1, lines=lines[i : i + 45])
        for i in range(0, max(len(lines), 1), 45)
    ]
    return ParsedDocument(pages=pages)


def count_pages(path: Path, kind: str) -> int:
    if kind == "pdf":
        with pymupdf.open(path) as doc:
            return int(doc.page_count)
    return len(_parse_docx(path).pages)
