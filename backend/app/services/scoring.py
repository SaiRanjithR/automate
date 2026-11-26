"""Pure scoring formulas: review score, readiness, go / no-go, page budgets. Unit-tested."""

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

SEVERITY_PENALTY = {"high": 30, "medium": 15, "low": 5}


def review_score(issues: list[dict[str, Any]]) -> int:
    return max(0, 100 - sum(SEVERITY_PENALTY.get(str(i.get("severity")), 0) for i in issues))


def readiness_score(
    blockers: list[dict[str, Any]],
    checks_total: int,
    approved_ratio: float = 1.0,
    gap_ratio: float = 0.0,
) -> int:
    """100 only with zero blockers. Otherwise: 50% approvals, 20% evidence coverage,
    30% other checks passed; capped at 95."""
    if not blockers:
        return 100
    row_codes = {"mandatory_gaps", "unapproved", "needs_review"}
    other = [b for b in blockers if b.get("code") not in row_codes]
    other_checks = max(checks_total - 3, 1)
    other_failed = sum(2 if b.get("severity") == "high" else 1 for b in other)
    checks_share = max(0.0, 1 - other_failed / other_checks)
    score = 50 * approved_ratio + 20 * (1 - gap_ratio) + 30 * checks_share
    return max(0, min(95, round(score)))


@dataclass
class GoNoGoInput:
    mandatory_total: int
    mandatory_gaps: int
    eligibility_failed: list[str]
    days_to_deadline: float | None
    gap_rows: int
    drafted_rows: int
    competition_rating: int | None  # 1 (weak competition) .. 5 (very strong competition)


def go_no_go(data: GoNoGoInput) -> dict[str, Any]:
    fit = (
        1.0
        if data.mandatory_total == 0
        else (data.mandatory_total - data.mandatory_gaps) / data.mandatory_total
    )
    risk = fit  # share of mandatory requirements that are not gaps
    work_days = (data.gap_rows * 1.0 + data.drafted_rows * 5 / 60) / 6
    if data.days_to_deadline is None:
        resources = 0.7
    elif data.days_to_deadline <= 0:
        resources = 0.0
    else:
        resources = min(1.0, data.days_to_deadline / max(work_days, 0.5))
    competition = 0.5 if data.competition_rating is None else (5 - data.competition_rating) / 4
    score = 0.4 * fit + 0.3 * risk + 0.2 * resources + 0.1 * competition
    if data.eligibility_failed:
        decision = "no_go"
    elif score >= 0.65:
        decision = "go"
    elif score >= 0.5:
        decision = "review"
    else:
        decision = "no_go"
    reasons = [
        f"Evidence covers {round(fit * 100)}% of mandatory requirements ({data.mandatory_total - data.mandatory_gaps} of {data.mandatory_total}).",
        f"{data.mandatory_gaps} mandatory requirement(s) have no evidence yet."
        if data.mandatory_gaps
        else "No mandatory gaps.",
        "Deadline unknown."
        if data.days_to_deadline is None
        else f"{max(0, round(data.days_to_deadline, 1))} days left vs about {round(work_days, 1)} days of work.",
        "Competition not rated."
        if data.competition_rating is None
        else f"Competition rated {data.competition_rating} of 5.",
    ]
    if data.eligibility_failed:
        reasons.insert(0, "Eligibility not met: " + "; ".join(data.eligibility_failed))
    return {
        "decision": decision,
        "score": round(score, 3),
        "factors": {
            "fit": round(fit, 3),
            "risk": round(risk, 3),
            "resources": round(resources, 3),
            "competition": round(competition, 3),
        },
        "reasons": reasons,
        "eligibility_failed": data.eligibility_failed,
        "computed_at": datetime.now(UTC).isoformat(),
    }


def page_budgets(marks: list[float], page_limit: float) -> list[float]:
    """Split page_limit across sections by marks, rounded to 0.5 pages, min 0.5, summing to the limit."""
    if not marks:
        return []
    total = sum(marks) or len(marks)
    raw = [page_limit * (m or 1) / total for m in marks]
    budgets = [max(0.5, round(r * 2) / 2) for r in raw]
    diff = page_limit - sum(budgets)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - budgets[i], reverse=diff > 0)
    step = 0.5 if diff > 0 else -0.5
    i = 0
    while abs(diff) >= 0.5 and i < 1000:
        idx = order[i % len(order)]
        if step > 0 or budgets[idx] > 0.5:
            budgets[idx] += step
            diff -= step
        i += 1
    return budgets


def word_budget_for(page_budget: float | None, requirements_in_section: int) -> int:
    if not page_budget or requirements_in_section <= 0:
        return 150
    return max(60, min(250, math.floor(page_budget * 450 / requirements_in_section)))
