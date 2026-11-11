import smtplib
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit, audit_committed
from app.config import get_settings
from app.db import admin_sessionmaker
from app.errors import DomainError
from app.models import Approval, Company, Contact, ContactPermission, Conversation, Message, User, WebhookEvent
from app.serialize import stamp
from app.services.common import classify_text, now, record_usage, require, settings_row


class EmailChannel:
    name = "email"

    def deliver(self, to_address: str, subject: str, body: str) -> str:
        settings = get_settings()
        if not settings.email_live:
            raise DomainError(409, "email_not_configured", "Live email is not configured.")
        message = EmailMessage()
        message["From"] = settings.smtp_from
        message["To"] = to_address
        message["Subject"] = subject or "YES SALES"
        message.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return "smtp"


class WhatsAppChannel:
    """Adapter port only. There is no live WhatsApp Business driver."""

    name = "whatsapp"

    def deliver(self, to_address: str, subject: str, body: str) -> str:
        del to_address, subject, body
        raise DomainError(501, "whatsapp_not_live", "WhatsApp Business is not connected. No message was sent.")


CHANNELS = {"email": EmailChannel(), "whatsapp": WhatsAppChannel()}


def public_message(message: Message) -> dict:
    return {
        "id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "direction": message.direction,
        "channel": message.channel,
        "body": message.body,
        "classification": message.classification,
        "provider_mode": message.provider_mode,
        "external_id": message.external_id,
        "status": message.status,
        "created_at": stamp(message.created_at),
    }


def public_conversation(row: Conversation) -> dict:
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "contact_id": str(row.contact_id),
        "channel": row.channel,
        "subject": row.subject,
        "status": row.status,
        "created_at": stamp(row.created_at),
    }


def _open_conversation(session: Session, contact: Contact, subject: str | None) -> Conversation:
    existing = session.scalar(
        select(Conversation)
        .where(
            Conversation.contact_id == contact.id,
            Conversation.channel == contact.channel,
            Conversation.status != "closed",
        )
        .order_by(Conversation.created_at.desc())
    )
    if existing is not None:
        if subject and not existing.subject:
            existing.subject = subject
        return existing
    created = Conversation(
        company_id=contact.company_id,
        contact_id=contact.id,
        channel=contact.channel,
        subject=subject,
        status="open",
    )
    session.add(created)
    session.flush()
    return created


def _log_blocked(actor: User | None, contact: Contact, body: str, code: str, detail: str) -> None:
    with admin_sessionmaker()() as session:
        conversation = _open_conversation(session, contact, None)
        session.add(
            Message(
                conversation_id=conversation.id,
                direction="outbound",
                channel=contact.channel,
                body=body,
                classification=classify_text(body),
                provider_mode="not_configured",
                status="blocked",
            )
        )
        audit(session, actor, "outbound.blocked", "contact", contact.id, {"code": code, "detail": detail})
        session.commit()


def persist_opt_out(contact_id: uuid.UUID, source: str) -> None:
    """Commit opt-out on the admin connection before the caller returns 403.

    The request session rolls back when the draft is blocked. This write has
    to survive that rollback.
    """
    with admin_sessionmaker()() as session:
        contact = session.get(Contact, contact_id)
        permission = session.scalar(select(ContactPermission).where(ContactPermission.contact_id == contact_id))
        if contact is None or permission is None:
            raise DomainError(404, "contact_not_found", "Opt-out could not be stored because the contact permission is missing.")
        permission.opted_out = True
        permission.allowed = False
        permission.opted_out_at = now()
        audit(
            session,
            None,
            "contact.opt_out",
            "contact",
            contact.id,
            {"source": source, "company_id": str(contact.company_id)},
        )
        session.commit()
    with admin_sessionmaker()() as check:
        stored = check.scalar(select(ContactPermission).where(ContactPermission.contact_id == contact_id))
        if stored is None or not stored.opted_out or stored.allowed:
            raise DomainError(500, "opt_out_not_persisted", "Opt-out was not stored. No message was sent.")


def outbound_block_reason(session: Session, contact: Contact, count_rate: bool = True) -> str | None:
    permission = session.scalar(select(ContactPermission).where(ContactPermission.contact_id == contact.id))
    if settings_row(session).outbound_paused:
        return "outbound_paused"
    if permission is None or not permission.allowed or permission.opted_out:
        return "contact_not_eligible"
    if not count_rate or permission is None:
        return None
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = session.scalar(
        select(func.count(Message.id))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.contact_id == contact.id,
            Message.direction == "outbound",
            Message.status == "sent",
            Message.created_at >= start,
        )
    )
    if sent_today is not None and int(sent_today) >= permission.daily_limit:
        return "rate_limited"
    return None


def send_message(session: Session, actor: User | None, data) -> Message:
    contact = require(session, Contact, data.contact_id, "Contact")
    if classify_text(data.body) == "commercial":
        audit_committed(actor, "outbound.blocked", "contact", contact.id, {"code": "approval_required"})
        raise DomainError(403, "approval_required", "Commercial content must be sent from an approved Alex draft.")
    blocked = outbound_block_reason(session, contact)
    if blocked == "outbound_paused":
        _log_blocked(actor, contact, data.body, blocked, "Global outbound pause is on.")
        raise DomainError(409, "outbound_paused", "Global outbound pause is on. No message was sent.")
    if blocked == "contact_not_eligible":
        _log_blocked(actor, contact, data.body, blocked, "Contact is not eligible for outreach.")
        raise DomainError(403, "contact_not_eligible", "Contact permission does not allow outreach.")
    if blocked == "rate_limited":
        _log_blocked(actor, contact, data.body, blocked, "Daily contact limit reached.")
        raise DomainError(429, "rate_limited", "Daily outreach limit for this contact has been reached.")
    if data.restricted:
        approval = session.scalar(
            select(Approval).where(
                Approval.action_type == "share_restricted",
                Approval.status == "approved",
                Approval.subject_id == contact.id,
            )
        )
        if approval is None:
            audit_committed(actor, "outbound.blocked", "contact", contact.id, {"code": "approval_required"})
            raise DomainError(403, "approval_required", "Restricted commercial information requires founder approval.")
    settings = get_settings()
    if contact.channel == "whatsapp":
        raise DomainError(501, "whatsapp_not_live", "WhatsApp Business is not connected. No message was sent.")
    if contact.channel != "email":
        raise DomainError(422, "unsupported_channel", "Alex can send email. Phone calls use the voice gateway.")
    if settings.outbound_enabled and not settings.email_live:
        audit_committed(actor, "outbound.blocked", "contact", contact.id, {"code": "email_not_configured"})
        raise DomainError(
            409,
            "email_not_configured",
            "OUTBOUND_ENABLED is true but SMTP is incomplete. Refusing to label a mock send as live.",
        )
    conversation = _open_conversation(session, contact, data.subject)
    if data.conversation_id is not None and data.conversation_id != conversation.id:
        requested = require(session, Conversation, data.conversation_id, "Conversation")
        if requested.contact_id != contact.id:
            raise DomainError(409, "conversation_mismatch", "Conversation does not belong to this contact.")
        conversation = requested
    mode = "live" if settings.email_live else "mock"
    message = Message(
        conversation_id=conversation.id,
        direction="outbound",
        channel="email",
        body=data.body,
        classification=classify_text(data.body),
        provider_mode=mode,
        status="queued",
    )
    session.add(message)
    session.flush()
    if mode == "live":
        try:
            message.external_id = EmailChannel().deliver(contact.value, data.subject or "YES SALES", data.body)
            message.status = "sent"
        except Exception as exc:
            message.status = "failed"
            audit(session, actor, "message.failed", "message", message.id, {"error": type(exc).__name__})
            record_usage(session, "smtp", "live", "email.send", 0)
            return message
    else:
        message.status = "sent"
        message.external_id = f"mock-{message.id}"
    record_usage(session, "email", mode, "email.send", 0)
    audit(
        session,
        actor,
        "message.sent",
        "message",
        message.id,
        {"provider_mode": mode, "contact_id": str(contact.id), "company_id": str(contact.company_id)},
    )
    return message


def ingest_email(session: Session, payload: dict, signature_valid: bool) -> dict:
    session.add(WebhookEvent(provider="email", signature_valid=signature_valid, payload=payload))
    session.flush()
    if not signature_valid:
        raise DomainError(401, "invalid_signature", "Webhook signature is invalid.", persist=True)
    from_email = str(payload.get("from_email", "")).strip().lower()
    body = str(payload.get("body", "")).strip()
    if not from_email or not body:
        raise DomainError(422, "invalid_payload", "Inbound email requires from_email and body.", persist=True)
    contact = session.scalar(select(Contact).where(Contact.channel == "email", Contact.normalized_value == from_email))
    if contact is None:
        raise DomainError(404, "contact_not_found", "No contact matches this email address.", persist=True)
    classification = classify_text(body)
    conversation_id = payload.get("conversation_id")
    if conversation_id:
        conversation = require(session, Conversation, uuid.UUID(str(conversation_id)), "Conversation")
    else:
        conversation = _open_conversation(session, contact, payload.get("subject"))
    if classification == "opt_out":
        persist_opt_out(contact.id, "inbound_email")
    message = Message(
        conversation_id=conversation.id,
        direction="inbound",
        channel="email",
        body=body,
        classification=classification,
        provider_mode="mock" if str(payload.get("external_id", "")).startswith("mock") or payload.get("provider_mode") == "mock" else "live",
        external_id=payload.get("external_id"),
        status="received",
    )
    if payload.get("provider_mode") in {"live", "mock", "not_configured"}:
        message.provider_mode = payload["provider_mode"]
    session.add(message)
    session.flush()
    audit(
        session,
        None,
        "message.received",
        "message",
        message.id,
        {"company_id": str(contact.company_id), "contact_id": str(contact.id), "classification": classification, "provider_mode": message.provider_mode},
    )
    if classification in {"callback_request", "human_handoff"}:
        conversation.status = "handoff"
        from app.services.orchestration import enqueue

        enqueue(
            session,
            None,
            "callback.request",
            f"callback-{message.id}",
            {"contact_id": str(contact.id), "message_id": str(message.id)},
        )
    from app.services.alex_metrics import record_alex_outcome

    record_alex_outcome(
        session,
        outcome="inbound_recorded",
        provider_mode=message.provider_mode,
        actor_kind="system",
        classification=classification,
        classification_method="deterministic",
        conversation_id=conversation.id,
        message_id=message.id,
        human_decision=None,
        comparable=False,
        detail={"live_mailbox": False},
    )
    audit(session, None, "message.received", "message", message.id, {"contact_id": str(contact.id), "classification": classification})
    return {"message": public_message(message), "conversation": public_conversation(conversation), "classification": classification}


def release_draft_message(session: Session, actor: User, approval: Approval) -> Message:
    message = require(session, Message, approval.subject_id, "Message")
    if message.status == "sent":
        return message
    if message.status != "draft" or message.direction != "outbound":
        raise DomainError(409, "not_a_draft", "Only an unsent Alex draft can be released.")
    conversation = require(session, Conversation, message.conversation_id, "Conversation")
    contact = require(session, Contact, conversation.contact_id, "Contact")
    blocked = outbound_block_reason(session, contact)
    if blocked == "outbound_paused":
        _log_blocked(actor, contact, message.body, blocked, "Global outbound pause is on.")
        raise DomainError(409, "outbound_paused", "Global outbound pause is on. The draft was not sent.")
    if blocked == "contact_not_eligible":
        _log_blocked(actor, contact, message.body, blocked, "Contact is not eligible for outreach.")
        raise DomainError(403, "contact_not_eligible", "Contact permission does not allow outreach.")
    if blocked == "rate_limited":
        _log_blocked(actor, contact, message.body, blocked, "Daily contact limit reached.")
        raise DomainError(429, "rate_limited", "Daily outreach limit for this contact has been reached.")
    settings = get_settings()
    if settings.outbound_enabled and not settings.email_live:
        raise DomainError(409, "email_not_configured", "OUTBOUND_ENABLED is true but SMTP is incomplete. The draft was not sent.")
    mode = "live" if settings.email_live else "mock"
    message.provider_mode = mode
    message.status = "queued"
    session.flush()
    if mode == "live":
        try:
            message.external_id = EmailChannel().deliver(contact.value, conversation.subject or "YES SALES", message.body)
            message.status = "sent"
        except Exception as exc:
            message.status = "failed"
            audit(session, actor, "message.failed", "message", message.id, {"error": type(exc).__name__})
            record_usage(session, "smtp", "live", "email.send", 0)
            return message
    else:
        message.status = "sent"
        message.external_id = f"mock-{message.id}"
    record_usage(session, "email", mode, "email.send", 0)
    from decimal import Decimal

    from app.services.alex_metrics import record_alex_outcome

    elapsed = None
    if approval.created_at is not None and approval.decided_at is not None:
        elapsed = Decimal(str((approval.decided_at - approval.created_at).total_seconds()))
    record_alex_outcome(
        session,
        outcome="sent",
        provider_mode=mode,
        actor_kind="human",
        classification=message.classification,
        classification_method="deterministic",
        conversation_id=message.conversation_id,
        message_id=message.id,
        human_decision="approved",
        intervention_seconds=elapsed,
        comparable=mode == "live",
        detail={"live_delivery": mode == "live", "approval_id": str(approval.id)},
    )
    audit(session, actor, "message.sent", "message", message.id, {"provider_mode": mode, "approval_id": str(approval.id), "source": "alex_draft"})
    return message


def handoff(session: Session, actor: User, conversation_id, note: str) -> Conversation:
    conversation = require(session, Conversation, conversation_id, "Conversation")
    conversation.status = "handoff"
    from app.services.alex_metrics import record_alex_outcome

    record_alex_outcome(
        session,
        outcome="handoff",
        provider_mode="not_configured",
        actor_kind="human",
        conversation_id=conversation.id,
        human_decision="handoff",
        comparable=False,
        detail={"note": note, "call_placed": False},
    )
    audit(session, actor, "conversation.handoff", "conversation", conversation.id, {"note": note})
    return conversation


def list_conversations(session: Session) -> list[dict]:
    rows = session.scalars(select(Conversation).order_by(Conversation.updated_at.desc()).limit(200)).all()
    output = []
    for row in rows:
        company = session.get(Company, row.company_id)
        contact = session.get(Contact, row.contact_id)
        latest = session.scalar(select(Message).where(Message.conversation_id == row.id).order_by(Message.created_at.desc()))
        output.append(
            {
                **public_conversation(row),
                "company_name": None if company is None else company.legal_name,
                "contact_name": None if contact is None else contact.full_name,
                "latest": None if latest is None else public_message(latest),
            }
        )
    return output


def list_messages(session: Session, conversation_id) -> list[Message]:
    require(session, Conversation, conversation_id, "Conversation")
    return list(
        session.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)).all()
    )
