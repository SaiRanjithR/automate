"""Zero-code policy hot-swap: rules from the UI and from JSON/YAML files, re-audit highlights new exceptions."""

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.services.policy import evaluate, max_amount_inr, max_days, max_percent, parse_rules
from tests.conftest import SAMPLES

PROFILE = json.loads((SAMPLES / "company" / "company_profile.json").read_text())


def _project(client: TestClient) -> int:
    client.put("/api/company", json=PROFILE)
    with (SAMPLES / "company" / "Nimbus_Company_Profile.pdf").open("rb") as handle:
        client.post(
            "/api/knowledge",
            files={"files": ("Nimbus_Company_Profile.pdf", handle)},
            data={"doc_type": "profile"},
        )
    with (SAMPLES / "hmis-tender" / "rfp.pdf").open("rb") as handle:
        started = client.post(
            "/api/projects", files={"main": ("rfp.pdf", handle, "application/pdf")}
        ).json()
    client.post(f"/api/projects/{started['project_id']}/draft")
    return int(started["project_id"])


def test_value_extraction() -> None:
    assert max_percent("a penalty of 0.5% per day, capped at 10 percent") == 10
    assert max_amount_inr("EMD of INR 5(Five) Lakh; PBG of Rs. 2 crore") == 2e7
    assert max_days("payment within 90 days or 4 weeks") == 90
    assert max_days("support for 5 years") == 5 * 365


def test_condition_operators() -> None:
    specs, errors = parse_rules(
        [
            {
                "id": "combo",
                "name": "Combo",
                "flag_if": {
                    "all": [
                        {"field": "requirement.type", "op": "eq", "value": "Mandatory"},
                        {
                            "any": [
                                {
                                    "field": "answer.text",
                                    "op": "contains_any",
                                    "value": ["free", "unlimited"],
                                },
                                {"not": {"field": "answer.approved", "op": "is_true"}},
                            ]
                        },
                    ]
                },
            }
        ]
    )
    assert not errors
    rule = specs[0]
    assert evaluate(
        rule.flag_if,
        {"requirement.type": "mandatory", "answer.text": "x", "answer.approved": False},
    )
    assert not evaluate(
        rule.flag_if, {"requirement.type": "mandatory", "answer.text": "x", "answer.approved": True}
    )
    assert not evaluate(
        rule.flag_if,
        {"requirement.type": "optional", "answer.text": "free", "answer.approved": False},
    )


def test_invalid_rules_are_reported_not_fatal() -> None:
    specs, errors = parse_rules(
        [
            {
                "id": "ok",
                "name": "Fine",
                "flag_if": {"field": "answer.word_count", "op": "gt", "value": 200},
            },
            {
                "id": "bad-field",
                "name": "Bad",
                "flag_if": {"field": "answer.colour", "op": "eq", "value": 1},
            },
            {
                "id": "bad-regex",
                "name": "Bad",
                "flag_if": {"field": "answer.text", "op": "matches", "value": "("},
            },
        ]
    )
    assert [s.id for s in specs] == ["ok"]
    assert any("unknown field 'answer.colour'" in e for e in errors)
    assert any("invalid regular expression" in e for e in errors)


def test_ui_rule_then_rerun_highlights_new_exceptions(auth_client: TestClient) -> None:
    project_id = _project(auth_client)
    first = auth_client.post(f"/api/projects/{project_id}/audit").json()
    assert all(not f["new"] for f in first["findings"])  # first run sets the baseline

    rule = {
        "id": "No Kannada claims",
        "name": "Answer mentions Kannada",
        "scope": "requirement",
        "flag_if": {"field": "answer.text", "op": "contains", "value": "Kannada"},
        "severity": "high",
        "message": "{requirement.code}: check the Kannada claim",
    }
    created = auth_client.post("/api/policies", json=rule)
    assert created.status_code == 201, created.text
    assert created.json()["id"] == "no-kannada-claims"
    assert auth_client.post("/api/policies", json=rule).status_code == 409

    second = auth_client.post(f"/api/projects/{project_id}/audit").json()
    new = [f for f in second["findings"] if f["new"]]
    assert new and all(f["rule_id"] == "no-kannada-claims" for f in new)
    assert new[0]["message"].endswith("check the Kannada claim") and new[0]["target"]["req_code"]
    assert second["new_count"] == len(new)

    # The exception blocks readiness because it is high severity.
    blockers = auth_client.get(f"/api/projects/{project_id}/validate").json()["blockers"]
    assert any(b["code"] == "policy" for b in blockers)

    # Disabling the rule resolves it on the next run.
    db_id = created.json()["db_id"]
    auth_client.patch(f"/api/policies/{db_id}", json={"enabled": False})
    third = auth_client.post(f"/api/projects/{project_id}/audit").json()
    assert third["resolved"] >= len(new)
    assert not any(f["rule_id"] == "no-kannada-claims" for f in third["findings"])


def test_file_rules_hot_reload_without_restart(
    auth_client: TestClient, test_settings: Settings
) -> None:
    project_id = _project(auth_client)
    policy_dir: Path = test_settings.policy_dir
    policy_dir.mkdir(parents=True, exist_ok=True)
    auth_client.post(f"/api/projects/{project_id}/audit")

    (policy_dir / "finance.yaml").write_text(
        yaml.safe_dump(
            {
                "rules": [
                    {
                        "id": "uptime-commitment",
                        "name": "Uptime commitment above 99.5%",
                        "when": {"field": "requirement.text", "op": "matches", "value": "uptime"},
                        "flag_if": {"field": "requirement.max_percent", "op": "gte", "value": 99.5},
                        "severity": "medium",
                        "message": "{requirement.code}: {requirement.max_percent}% uptime needs ops sign-off",
                    },
                    {
                        "id": "broken",
                        "name": "Broken",
                        "flag_if": {"field": "nope", "op": "eq", "value": 1},
                    },
                ]
            }
        )
    )
    policies = auth_client.get("/api/policies").json()
    file_rules = [r for r in policies["rules"] if r["source"] == "file:finance.yaml"]
    assert [r["id"] for r in file_rules] == ["uptime-commitment"] and not file_rules[0]["editable"]
    assert any("broken" in e for e in policies["errors"])

    run = auth_client.post(f"/api/projects/{project_id}/audit").json()
    flagged = [f for f in run["findings"] if f["rule_id"] == "uptime-commitment"]
    assert flagged and all(f["new"] for f in flagged)
    assert "99.5% uptime needs ops sign-off" in flagged[0]["message"]
    assert any("broken" in e for e in run["errors"])


def test_import_and_export(auth_client: TestClient) -> None:
    payload = {
        "rules": [
            {
                "id": "emd",
                "name": "EMD",
                "scope": "tender",
                "flag_if": {"field": "tender.emd_inr", "op": "gt", "value": 0},
            }
        ]
    }
    assert auth_client.post("/api/policies/import", json=payload).json() == {
        "created": 1,
        "updated": 0,
        "errors": [],
    }
    assert auth_client.post("/api/policies/import", json=payload).json()["updated"] == 1
    exported = auth_client.get("/api/policies/export").json()
    assert exported["rules"][0]["id"] == "emd"
    fields = auth_client.get("/api/policies/fields").json()
    assert any(f["name"] == "requirement.max_percent" for f in fields)
