"""Live compliance review of one drafted answer (F20): code checks + review_response prompt."""

import re
from typing import Any

from app.llm.client import LLM, UsageMeter
from app.schemas.llm import ReviewOutput
from app.services.scoring import review_score

BANNED_PHRASES = (
    "world-class",
    "world class",
    "best-in-class",
    "best in class",
    "cutting-edge",
    "cutting edge",
    "state-of-the-art",
    "state of the art",
    "industry-leading",
    "seamless",
    "synergy",
    "one-stop",
)


def review_answer(
    llm: LLM,
    *,
    requirement: str,
    mandatory: bool,
    answer: str,
    citations: list[dict[str, Any]],
    word_budget: int,
    usage: UsageMeter | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    if not citations:
        issues.append(
            {
                "type": "unsupported_claim",
                "message": "The answer cites no evidence.",
                "severity": "high",
            }
        )
    word_count = len(answer.split())
    if word_count > word_budget:
        issues.append(
            {
                "type": "over_budget",
                "message": f"{word_count} words; the budget for this section is {word_budget}.",
                "severity": "medium",
            }
        )
    lowered = answer.lower()
    found = [p for p in BANNED_PHRASES if p in lowered]
    if found:
        issues.append(
            {
                "type": "generic",
                "message": f"Filler phrase(s): {', '.join(found)}.",
                "severity": "medium",
            }
        )

    result = llm.complete(
        "review_response",
        {
            "requirement": requirement,
            "answer": answer,
            "quotes": "\n".join(f"- {c['quote']}" for c in citations),
            "quote_list": [c["quote"] for c in citations],
        },
        ReviewOutput,
        usage,
    ).value
    for part in result.missing_parts:
        issues.append(
            {
                "type": "missing_part",
                "message": f"Not addressed: {part}",
                "severity": "high" if mandatory else "medium",
            }
        )
    for claim in result.unsupported_claims:
        short = re.sub(r"\s+", " ", claim)[:140]
        issues.append(
            {
                "type": "unsupported_claim",
                "message": f"Not backed by a citation: {short}",
                "severity": "medium",
            }
        )
    if result.specificity == "low":
        issues.append(
            {
                "type": "generic",
                "message": "Add specific proof: project, client, numbers, outcome.",
                "severity": "low",
            }
        )
    return review_score(issues), issues
