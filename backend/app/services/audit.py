"""Audit trail writes (F23)."""

from typing import Any

from sqlmodel import Session

from app.models import AuditEvent


def record(
    session: Session,
    *,
    entity: str,
    entity_id: int,
    action: str,
    actor: str,
    project_id: int | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    prompt_version: str | None = None,
) -> None:
    session.add(
        AuditEvent(
            project_id=project_id,
            entity=entity,
            entity_id=entity_id,
            action=action,
            actor=actor,
            before=before,
            after=after,
            prompt_version=prompt_version,
        )
    )
