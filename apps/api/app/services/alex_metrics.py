import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import AlexOutcomeMetric


def record_alex_outcome(
    session: Session,
    *,
    outcome: str,
    provider_mode: str,
    actor_kind: str,
    classification: str | None = None,
    classification_method: str | None = None,
    conversation_id: uuid.UUID | None = None,
    message_id: uuid.UUID | None = None,
    call_id: uuid.UUID | None = None,
    human_decision: str | None = None,
    intervention_seconds: Decimal | None = None,
    cost_usd: Decimal | int | str = 0,
    comparable: bool = False,
    detail: dict | None = None,
) -> AlexOutcomeMetric:
    row = AlexOutcomeMetric(
        conversation_id=conversation_id,
        message_id=message_id,
        call_id=call_id,
        actor_kind=actor_kind,
        classification=classification,
        classification_method=classification_method,
        provider_mode=provider_mode,
        outcome=outcome,
        human_decision=human_decision,
        intervention_seconds=None if intervention_seconds is None else Decimal(intervention_seconds),
        cost_usd=Decimal(cost_usd),
        comparable=comparable,
        detail=detail or {},
    )
    session.add(row)
    session.flush()
    return row
