"""Logging setup. Log IDs and counts only — never RFP or knowledge-base text."""

import logging

from app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    # Third-party libraries are noisy at INFO.
    for noisy in ("httpx", "httpcore", "fastembed", "pymupdf"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
