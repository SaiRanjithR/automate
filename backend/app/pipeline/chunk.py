"""Group parsed lines into sections (chunks) with page markers.

A chunk starts at a top-level heading ("4. Scope of Work", "4.Scope of Work", "DISCLAIMER",
"Annexure-A: ...") or at a second-level heading of the current section ("4.2 Technical Requirements").
Top-level numbers must follow the previous one (1, 2, 3 ...) so numbered list items inside a section
("2.Percentage accuracy ...") are not mistaken for sections.
"""

import re
from dataclasses import dataclass, field

from app.pipeline.parse import Line, ParsedDocument

MAX_CHUNK_CHARS = 24_000
_TOP_LEVEL = re.compile(r"^(?:section\s+)?(\d{1,2})(?:\.\s*|\s+)([A-Z][^\n]{1,80})$", re.I)
_SECOND_LEVEL = re.compile(r"^(\d{1,2})\.(\d{1,2})\.?\s*([A-Z][^\n]{1,85})$")
_ANNEX = re.compile(
    r"^(?:\d+(?:\.\d+)*\.?\s*)?(Annexure|ANNEXURE|Appendix|APPENDIX|Schedule|SCHEDULE|Form|FORM)"
    r"[- ]?([A-Z0-9]{1,4}|[IVX]{1,5})\b"
)
_MODAL = re.compile(r"\b(shall|must|should|will be|may)\b", re.I)
_CAPS = re.compile(r"^[A-Z][A-Z &/\-]{3,40}$")


@dataclass
class Chunk:
    heading: str
    section_path: str
    lines: list[tuple[int, str]] = field(default_factory=list)
    category: str = "other"

    @property
    def pages(self) -> list[int]:
        return sorted({p for p, _ in self.lines})

    @property
    def text(self) -> str:
        out: list[str] = []
        current = None
        for page, line in self.lines:
            if page != current:
                out.append(f"[[page {page}]]")
                current = page
            out.append(line)
        return "\n".join(out)


def _heading_like(line: Line, body_size: float) -> bool:
    text = line.text
    if line.is_table_row or len(text) > 95 or _MODAL.search(text):
        return False
    if text.endswith((".", ",", ";")):
        return False
    return line.bold or line.size >= body_size + 1


def _top_number(line: Line, body_size: float) -> int | None:
    if not _heading_like(line, body_size) or _SECOND_LEVEL.match(line.text):
        return None
    match = _TOP_LEVEL.match(line.text)
    return int(match.group(1)) if match else None


def _is_annex(line: Line) -> bool:
    text = line.text
    if line.is_table_row or len(text) > 120 or not _ANNEX.match(text):
        return False
    return (line.bold or ":" in text or " - " in text) and not text.endswith(".")


def _is_caps_heading(line: Line, body_size: float) -> bool:
    return bool(_CAPS.match(line.text)) and line.bold and line.size >= body_size + 1


def build_chunks(doc: ParsedDocument) -> list[Chunk]:
    body = doc.body_font_size
    chunks: list[Chunk] = []
    current = Chunk(heading="Preamble", section_path="Preamble")
    size = 0
    last_top = 0

    def start(heading: str) -> Chunk:
        nonlocal size
        if current.lines:
            chunks.append(current)
        size = 0
        return Chunk(heading=heading, section_path=heading)

    for page in doc.pages:
        for line in page.lines:
            number = _top_number(line, body)
            second = _SECOND_LEVEL.match(line.text) if _heading_like(line, body) else None
            if number is not None and number == last_top + 1:
                last_top = number
                current = start(line.text)
            elif (
                _is_annex(line)
                or _is_caps_heading(line, body)
                or (second and last_top and int(second.group(1)) == last_top)
            ):
                current = start(line.text)
            elif size + len(line.text) > MAX_CHUNK_CHARS and current.lines:
                heading = current.heading
                current = start(heading)
                current.section_path = f"{heading} (cont.)"
            current.lines.append((page.page, line.text))
            size += len(line.text) + 1
    if current.lines:
        chunks.append(current)
    return chunks


def section_number(section_path: str) -> str:
    match = re.match(r"^(?:Section\s+)?(\d+)", section_path, re.I)
    if match:
        return match.group(1)
    annex = _ANNEX.match(section_path)
    return annex.group(1)[0].upper() if annex else "0"
