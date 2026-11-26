"""Upload storage with content-type sniffing and size limits."""

import re
import uuid
import zipfile
from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import ValidationFailedError

_CHUNK = 1024 * 1024
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def sniff_kind(path: Path) -> str | None:
    """Return 'pdf' or 'docx' based on file content, or None if neither."""
    with path.open("rb") as handle:
        head = handle.read(8)
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
        except zipfile.BadZipFile:
            return None
        if "[Content_Types].xml" in names and any(n.startswith("word/") for n in names):
            return "docx"
    return None


def safe_filename(name: str) -> str:
    cleaned = _SAFE_NAME.sub("_", Path(name).name).strip("._") or "file"
    return cleaned[:120]


def save_upload(settings: Settings, upload: UploadFile, folder: str) -> tuple[Path, str]:
    """Stream an upload to disk; return (path, kind). Rejects oversize or non PDF/DOCX files."""
    original = upload.filename or "upload"
    target_dir = settings.files_dir / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{uuid.uuid4().hex[:12]}_{safe_filename(original)}"
    limit = settings.max_upload_mb * 1024 * 1024
    written = 0
    with target.open("wb") as out:
        while chunk := upload.file.read(_CHUNK):
            written += len(chunk)
            if written > limit:
                out.close()
                target.unlink(missing_ok=True)
                raise ValidationFailedError(
                    f"{original} is larger than the {settings.max_upload_mb} MB limit"
                )
            out.write(chunk)
    kind = sniff_kind(target)
    if kind is None:
        target.unlink(missing_ok=True)
        raise ValidationFailedError(f"{original} is not a PDF or Word (.docx) file")
    return target, kind
