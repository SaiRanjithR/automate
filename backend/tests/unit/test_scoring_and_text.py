from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import Settings
from app.core.errors import UnauthorizedError
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.pipeline.textutil import key_terms, quote_found, similarity
from app.services.scoring import (
    GoNoGoInput,
    go_no_go,
    page_budgets,
    readiness_score,
    review_score,
    word_budget_for,
)


@pytest.mark.parametrize(
    ("marks", "limit"),
    [([5, 5, 20, 30, 15, 15, 10, 5], 30), ([1, 1, 1], 7), ([10], 3), ([30, 10, 5], 12.5)],
)
def test_page_budgets_sum_to_limit(marks: list[float], limit: float) -> None:
    budgets = page_budgets(marks, limit)
    assert abs(sum(budgets) - limit) <= 0.5
    assert all(b >= 0.5 for b in budgets)
    assert all((b * 2).is_integer() for b in budgets)


def test_page_budgets_follow_marks() -> None:
    small, large = page_budgets([10, 30], 20)
    assert large > small


def test_review_score_penalties() -> None:
    assert review_score([]) == 100
    assert review_score([{"severity": "high"}, {"severity": "low"}]) == 65
    assert review_score([{"severity": "high"}] * 5) == 0


def test_readiness_is_100_only_without_blockers() -> None:
    assert readiness_score([], 10) == 100
    assert readiness_score([{"code": "form_fields", "severity": "low"}], 10) <= 95
    early = readiness_score(
        [{"code": "unapproved", "severity": "high"}], 10, approved_ratio=0.1, gap_ratio=0.3
    )
    late = readiness_score(
        [{"code": "unapproved", "severity": "high"}], 10, approved_ratio=0.9, gap_ratio=0.0
    )
    assert early <= 50 < late


def _gng(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "mandatory_total": 20,
        "mandatory_gaps": 1,
        "eligibility_failed": [],
        "days_to_deadline": 20.0,
        "gap_rows": 1,
        "drafted_rows": 20,
        "competition_rating": 2,
    }
    base.update(overrides)
    return go_no_go(GoNoGoInput(**base))  # type: ignore[arg-type]


def test_go_no_go_go_and_no_go() -> None:
    assert _gng()["decision"] == "go"
    assert _gng(mandatory_gaps=18, days_to_deadline=0.0)["decision"] == "no_go"


def test_failed_eligibility_forces_no_go() -> None:
    result = _gng(eligibility_failed=["CMMI Level 3"])
    assert result["decision"] == "no_go"
    assert "CMMI Level 3" in result["reasons"][0]


def test_competition_rating_changes_score() -> None:
    assert _gng(competition_rating=1)["score"] > _gng(competition_rating=5)["score"]


def test_word_budget_bounds() -> None:
    assert word_budget_for(None, 3) == 150
    assert 60 <= word_budget_for(0.5, 20) <= 250
    assert word_budget_for(10, 1) == 250


def test_quote_found_fuzzy_and_short() -> None:
    page = "2.4 The technical proposal shall not exceed 30 pages, using Arial font size 11 pt."
    assert quote_found("The technical proposal shall not exceed 30 pages", page)
    assert quote_found("The  technical proposal shall NOT exceed 30 pages", page)
    assert not quote_found("The bidder shall provide a drone", page)
    assert not quote_found("short", page)


def test_similarity_and_terms() -> None:
    assert similarity("train at least 300 staff", "train at least 500 staff") > 0.6
    assert "kannada" in key_terms("The interface shall be in Kannada")
    assert "shall" not in key_terms("The interface shall be in Kannada")


def test_password_and_token_round_trip() -> None:
    hashed = hash_password("s3cret-pass")
    assert verify_password("s3cret-pass", hashed)
    assert not verify_password("wrong", hashed)
    settings = Settings(_env_file=None, jwt_expire_minutes=5)  # type: ignore[call-arg]
    assert decode_token(create_token(42, settings), settings) == 42


def test_expired_token_rejected() -> None:
    import jwt

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) - timedelta(minutes=1)},
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    with pytest.raises(UnauthorizedError):
        decode_token(expired, settings)
