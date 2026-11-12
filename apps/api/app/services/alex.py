import json
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import get_settings
from app.errors import DomainError
from app.models import (
    Approval,
    BuyerRequirement,
    Company,
    Contact,
    ContactPermission,
    Conversation,
    Message,
    SupplierOffer,
    User,
)
from app.schemas import ApprovalIn
from app.services.common import MODEL_CALL_USD, classify_text, record_usage, require, require_model_budget
from app.services.comms import _open_conversation, outbound_block_reason, public_message, release_draft_message

LIMITATIONS = [
    "The draft quotes stored names and the inbound text. It does not add a price, commission, delivery date, or contract.",
    "Landed cost is not calculated.",
    "Nothing is sent until a founder executes the send_outreach approval.",
    "Classification uses the deterministic rules. xAI is used only when XAI_API_KEY is set.",
]


def classify_message(body: str, session: Session | None = None) -> dict:
    settings = get_settings()
    label = classify_text(body)
    if not settings.xai_api_key or session is None:
        return {
            "classification": label,
            "provider_mode": "not_configured",
            "method": "deterministic",
            "live_model_called": False,
        }
    require_model_budget(session, MODEL_CALL_USD)
    try:
        model_label = _classify_with_xai(body)
    except (DomainError, httpx.HTTPError, json.JSONDecodeError):
        return {
            "classification": label,
            "provider_mode": "not_configured",
            "method": "deterministic",
            "live_model_called": False,
        }
    if model_label not in {"opt_out", "human_handoff", "callback_request", "commercial", "general"}:
        model_label = label
    record_usage(session, "xai", "live", "alex.classify", MODEL_CALL_USD)
    return {
        "classification": model_label,
        "provider_mode": "live",
        "method": "xai",
        "live_model_called": True,
    }


def _classify_with_xai(body: str) -> str:
    settings = get_settings()
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "classification": {
                "type": "string",
                "enum": ["opt_out", "human_handoff", "callback_request", "commercial", "general"],
            }
        },
        "required": ["classification"],
    }
    response = httpx.post(
        f"{settings.xai_base_url}/responses",
        headers={"Authorization": f"Bearer {settings.xai_api_key}"},
        json={
            "model": settings.xai_model,
            "store": False,
            "input": [
                {
                    "role": "system",
                    "content": "Classify the message. Do not invent facts and do not draft a reply.",
                },
                {"role": "user", "content": body},
            ],
            "text": {"format": {"type": "json_schema", "name": "message_class", "strict": True, "schema": schema}},
        },
        timeout=30,
    )
    response.raise_for_status()
    text_out = ""
    for item in response.json().get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text_out = content.get("text") or ""
    if not text_out:
        raise DomainError(502, "xai_empty", "xAI returned no classification.")
    return str(json.loads(text_out)["classification"])


def contact_context(session: Session, contact_id: uuid.UUID) -> dict:
    contact = require(session, Contact, contact_id, "Contact")
    company = require(session, Company, contact.company_id, "Company")
    permission = session.scalar(select(ContactPermission).where(ContactPermission.contact_id == contact.id))
    requirements = list(session.scalars(select(BuyerRequirement).where(BuyerRequirement.company_id == company.id)))
    offers = list(session.scalars(select(SupplierOffer).where(SupplierOffer.company_id == company.id)))
    messages = list(
        session.scalars(
            select(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(Conversation.contact_id == contact.id)
            .order_by(Message.created_at.desc())
            .limit(8)
        )
    )
    return {
        "contact": {
            "id": str(contact.id),
            "full_name": contact.full_name,
            "channel": contact.channel,
            "value": contact.value,
        },
        "company": {
            "id": str(company.id),
            "legal_name": company.legal_name,
            "role": company.role,
            "country": company.country,
            "category": company.category,
            "supplier_stage": company.supplier_stage,
            "buyer_stage": company.buyer_stage,
            "verification_status": company.verification_status,
        },
        "permission": None
        if permission is None
        else {
            "allowed": permission.allowed,
            "opted_out": permission.opted_out,
            "consent_for_callback": permission.consent_for_callback,
            "daily_limit": permission.daily_limit,
            "authorization_basis": permission.authorization_basis,
        },
        "requirements": [
            {
                "id": str(item.id),
                "product_category": item.product_category,
                "desired_quantity": None if item.desired_quantity is None else str(item.desired_quantity),
                "destination_country": item.destination_country,
                "required_certifications": item.required_certifications,
            }
            for item in requirements
        ],
        "offers": [
            {
                "id": str(item.id),
                "version": item.version,
                "currency": item.currency,
                "incoterms": item.incoterms,
                "origin_country": item.origin_country,
            }
            for item in offers
        ],
        "recent_messages": [public_message(item) for item in reversed(messages)],
        "limitations": [
            "Context is limited to rows stored for this contact and company.",
            "Offer prices are omitted from Alex context so a draft cannot copy them.",
            "Landed cost is not calculated.",
        ],
    }


def _draft_body(contact: Contact, company: Company, inbound: str, classification: str) -> str:
    excerpt = " ".join(inbound.split())[:240]
    if classification in {"callback_request", "human_handoff"}:
        holding = "A person at YES SALES will follow up. This note does not place a call."
    else:
        holding = "We are not stating a price, commission, delivery date, or contract in this message."
    return (
        f"Hello {contact.full_name},\n\n"
        f"This is Alex at YES SALES, writing about {company.legal_name}.\n"
        f"We received: \"{excerpt}\".\n"
        f"{holding}\n"
    )


def draft_reply(session: Session, actor: User, contact_id: uuid.UUID, inbound: str, subject: str | None) -> dict:
    contact = require(session, Contact, contact_id, "Contact")
    if contact.channel != "email":
        raise DomainError(422, "unsupported_channel", "Alex drafts email. Phone calls use the voice gateway.")
    classified = classify_message(inbound, session)
    if classified["classification"] == "opt_out":
        from app.services.comms import persist_opt_out

        persist_opt_out(contact.id, "alex_draft")
        raise DomainError(403, "contact_not_eligible", "Opt-out received. No draft was created and no message was sent.")
    blocked = outbound_block_reason(session, contact, count_rate=False)
    if blocked == "contact_not_eligible":
        audit(session, actor, "alex.draft_denied", "contact", contact.id, {"code": blocked})
        raise DomainError(403, "contact_not_eligible", "Contact permission does not allow a draft.")
    company = require(session, Company, contact.company_id, "Company")
    conversation = _open_conversation(session, contact, subject)
    if classified["classification"] in {"callback_request", "human_handoff"}:
        conversation.status = "handoff"
        from app.services.orchestration import enqueue

        enqueue(
            session,
            actor,
            "callback.request",
            f"callback-draft-{contact.id}-{conversation.id}",
            {"contact_id": str(contact.id)},
        )
    message = Message(
        conversation_id=conversation.id,
        direction="outbound",
        channel="email",
        body=_draft_body(contact, company, inbound, classified["classification"]),
        classification=classified["classification"],
        provider_mode="mock",
        status="draft",
    )
    session.add(message)
    session.flush()
    from app.services.commercial import public_approval, request_approval

    approval = request_approval(
        session,
        actor,
        ApprovalIn(
            action_type="send_outreach",
            subject_type="message",
            subject_id=message.id,
            payload={"contact_id": str(contact.id), "conversation_id": str(conversation.id)},
            notes="Alex draft is waiting for founder approval before any send.",
        ),
    )
    from app.services.alex_metrics import record_alex_outcome

    record_alex_outcome(
        session,
        outcome="draft_created",
        provider_mode="mock",
        actor_kind="ai" if classified["method"] == "xai" else "system",
        classification=classified["classification"],
        classification_method=classified["method"],
        conversation_id=conversation.id,
        message_id=message.id,
        human_decision="pending",
        comparable=False,
        detail={"sent": False, "live_model_called": classified["live_model_called"]},
    )
    audit(
        session,
        actor,
        "alex.draft_created",
        "message",
        message.id,
        {"approval_id": str(approval.id), "sent": False, "company_id": str(company.id), "provider_mode": "mock"},
    )
    return {
        "message": public_message(message),
        "approval": public_approval(approval),
        "classification": classified,
        "sent": False,
        "provider_mode": "mock",
        "live_email": False,
        "limitations": LIMITATIONS,
    }


def schedule_followup(session: Session, actor: User, contact_id: uuid.UUID, body: str, subject: str | None, delay_hours: int, idempotency_key: str) -> dict:
    contact = require(session, Contact, contact_id, "Contact")
    if contact.channel != "email":
        raise DomainError(422, "unsupported_channel", "Follow-ups are email tasks.")
    from app.services.orchestration import enqueue, public_task

    task, replayed = enqueue(
        session,
        actor,
        "email.followup",
        idempotency_key,
        {"contact_id": str(contact.id), "body": body, "subject": subject},
        delay_seconds=delay_hours * 3600,
    )
    audit(session, actor, "alex.followup_scheduled", "task", task.id, {"delay_hours": delay_hours, "sent": False})
    return {"task": public_task(task), "idempotent_replay": replayed, "sent": False}


def execute_outreach(session: Session, actor: User, approval: Approval) -> dict:
    message = release_draft_message(session, actor, approval)
    return {
        "executed": True,
        "result": "message_sent",
        "message_id": str(message.id),
        "provider_mode": message.provider_mode,
        "live_email": message.provider_mode == "live",
        "live_call": False,
    }
