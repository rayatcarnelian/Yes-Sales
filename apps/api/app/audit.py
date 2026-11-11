import uuid

from sqlalchemy.orm import Session

from app.db import admin_sessionmaker
from app.models import AuditEvent, User


def audit(
    session: Session,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    detail: dict | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor_id=None if actor is None else actor.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail or {},
        )
    )


def audit_committed(
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    detail: dict | None = None,
) -> None:
    with admin_sessionmaker()() as session:
        audit(session, actor, action, entity_type, entity_id, detail)
        session.commit()
