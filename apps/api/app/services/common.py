import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import OperatingSettings, ProviderUsage, User
from app.serialize import money


def now() -> datetime:
    return datetime.now(UTC)


def require(session: Session, model: type, entity_id: uuid.UUID, label: str):
    row = session.get(model, entity_id)
    if row is None:
        raise DomainError(404, "not_found", f"{label} was not found.")
    return row


def normalize_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def website_domain(website: str | None) -> str | None:
    if website is None or not website.strip():
        return None
    raw = website.strip()
    if "://" not in raw:
        raw = "https://" + raw
    host = urlparse(raw).hostname
    if host is None:
        return None
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def normalize_channel_value(channel: str, value: str) -> str:
    if channel == "email":
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise DomainError(422, "invalid_contact", "Email address is invalid.")
        return normalized
    if channel not in {"phone", "whatsapp"}:
        raise DomainError(422, "invalid_channel", "Channel must be email, phone, or whatsapp.")
    digits = re.sub(r"[^\d+]", "", value.strip())
    if not digits:
        raise DomainError(422, "invalid_contact", "Phone number is empty after normalization.")
    return digits


def classify_text(body: str) -> str:
    text = body.lower()
    if re.search(r"\b(unsubscribe|opt-out|opt out|do not contact|stop)\b", text):
        return "opt_out"
    if re.search(r"\b(speak to (a )?(person|human|manager)|human handoff|transfer me)\b", text):
        return "human_handoff"
    if re.search(r"\b(call me back|callback|schedule a call|please call)\b", text):
        return "callback_request"
    if re.search(r"\b(quotation|quote|price|moq|rfq)\b", text):
        return "commercial"
    return "general"


def country_code(value: str | None) -> str | None:
    if value is None:
        return None
    code = value.strip().upper()
    if len(code) != 2 or not code.isalpha():
        raise DomainError(422, "invalid_country", "Country must be a 2-letter code.")
    return code


def currency_code(value: str | None) -> str | None:
    if value is None:
        return None
    code = value.strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise DomainError(422, "invalid_currency", "Currency must be a 3-letter code.")
    return code


def settings_row(session: Session) -> OperatingSettings:
    row = session.get(OperatingSettings, 1)
    if row is None:
        raise DomainError(500, "settings_missing", "Operating settings are not initialized.")
    return row


def spent_usd(session: Session) -> Decimal:
    value = session.scalar(select(func.coalesce(func.sum(ProviderUsage.cost_usd), 0)))
    return Decimal(value or 0)


def record_usage(
    session: Session,
    provider: str,
    mode: str,
    operation: str,
    cost_usd: Decimal | int | str,
    agent_run_id: uuid.UUID | None = None,
    units: Decimal = Decimal("1"),
) -> ProviderUsage:
    current = settings_row(session)
    spent = spent_usd(session)
    cost = Decimal(cost_usd)
    if mode == "live" and spent + cost > Decimal(current.budget_ceiling_usd):
        raise DomainError(409, "budget_exceeded", "Provider budget ceiling would be exceeded.")
    usage = ProviderUsage(
        provider=provider,
        mode=mode,
        operation=operation,
        units=units,
        cost_usd=cost,
        agent_run_id=agent_run_id,
    )
    session.add(usage)
    session.flush()
    current.budget_spent_usd = spent + cost
    return usage


def public_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
    }


def public_settings(row: OperatingSettings, spent: Decimal) -> dict:
    return {
        "outbound_paused": row.outbound_paused,
        "jobs_paused": row.jobs_paused,
        "budget_ceiling_usd": money(row.budget_ceiling_usd),
        "budget_spent_usd": f"{spent.quantize(Decimal('0.000001'))}",
    }
