import re
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit
from app.errors import DomainError
from app.models import JobCard, JobCardReply, ServiceSheet, User
from app.schemas import ApprovalIn
from app.serialize import money, stamp
from app.services.common import classify_text, currency_code, require

_PRICE_ASK = re.compile(r"\b(how much|price|quote|quotation|cost|rm|myr)\b", re.I)
_BOOK_ASK = re.compile(r"\b(book|booking|appointment|tomorrow|slot|bay)\b", re.I)
_HUMAN = re.compile(r"\b(person|human|manager)\b", re.I)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_LEFTOVER_PRICE = re.compile(r"\d|\bRM\b|\bMYR\b|\$", re.I)


def public_sheet(row: ServiceSheet) -> dict:
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "service_name": row.service_name,
        "duration_notes": row.duration_notes,
        "currency": row.currency,
        "price": money(row.price),
        "status": row.status,
        "allowed_sentence": row.allowed_sentence,
        "approval_id": None if row.approval_id is None else str(row.approval_id),
        "created_at": stamp(row.created_at),
    }


def public_reply(row: JobCardReply) -> dict:
    return {
        "id": str(row.id),
        "job_card_id": str(row.job_card_id),
        "body": row.body,
        "sent": False,
        "live_email": False,
        "price_allowed": row.price_allowed,
        "allowed_sheet_ids": [str(item) for item in (row.allowed_sheet_ids or [])],
        "created_at": stamp(row.created_at),
    }


def public_card(row: JobCard, replies: list[JobCardReply] | None = None) -> dict:
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "contact_id": None if row.contact_id is None else str(row.contact_id),
        "vehicle": row.vehicle,
        "requested_service": row.requested_service,
        "preferred_time": row.preferred_time,
        "photo_note": row.photo_note,
        "status": row.status,
        "bay_confirmed": row.status == "bay_confirmed",
        "replies": [public_reply(item) for item in (replies or [])],
        "created_at": stamp(row.created_at),
    }


def create_sheet(session: Session, actor: User, data) -> ServiceSheet:
    company = require(session, __company(), data.company_id, "Company")
    currency = currency_code(data.currency) or "MYR"
    price = Decimal(data.price).quantize(Decimal("0.01"))
    if price <= 0:
        raise DomainError(422, "invalid_price", "Service price must be positive.")
    _assert_sentence_matches_price(data.allowed_sentence, price)
    row = ServiceSheet(
        company_id=company.id,
        service_name=data.service_name.strip(),
        duration_notes=data.duration_notes,
        currency=currency,
        price=price,
        status="draft",
        allowed_sentence=data.allowed_sentence.strip(),
    )
    session.add(row)
    session.flush()
    audit(session, actor, "service_sheet.created", "service_sheet", row.id, {"company_id": str(company.id), "status": "draft"})
    return row


def request_sheet_approval(session: Session, actor: User, sheet_id):
    from app.services.commercial import request_approval

    sheet = require(session, ServiceSheet, sheet_id, "Service sheet")
    if sheet.status == "approved":
        raise DomainError(409, "already_approved", "This service line is already approved.")
    return request_approval(
        session,
        actor,
        ApprovalIn(
            action_type="bind_price",
            subject_type="service_sheet",
            subject_id=sheet.id,
            payload={"price": money(sheet.price), "currency": sheet.currency, "service_name": sheet.service_name},
            notes="Approve the service sheet price. The assistant may repeat only this sentence.",
        ),
    )


def list_sheets(session: Session, company_id) -> list[ServiceSheet]:
    stmt = select(ServiceSheet).order_by(ServiceSheet.created_at.desc())
    if company_id is not None:
        stmt = stmt.where(ServiceSheet.company_id == company_id)
    return list(session.scalars(stmt.limit(100)))


def file_card(session: Session, actor: User, data) -> tuple[JobCard, JobCardReply]:
    company = require(session, __company(), data.company_id, "Company")
    if data.contact_id is not None:
        contact = require(session, __contact(), data.contact_id, "Contact")
        if contact.company_id != company.id:
            raise DomainError(409, "conversation_mismatch", "Contact does not belong to this shop.")
    card = JobCard(
        company_id=company.id,
        contact_id=data.contact_id,
        vehicle=data.vehicle.strip(),
        requested_service=data.requested_service.strip(),
        preferred_time=data.preferred_time,
        photo_note=data.photo_note,
        status="requested",
    )
    session.add(card)
    session.flush()
    audit(session, actor, "job_card.filed", "job_card", card.id, {"company_id": str(company.id), "status": "requested"})
    reply = draft_reply(session, actor, card, data.customer_message)
    return card, reply


def draft_reply(session: Session, actor: User, card: JobCard, message: str) -> JobCardReply:
    if card.status == "bay_confirmed":
        raise DomainError(409, "bay_already_confirmed", "This job card is already confirmed. The assistant will not rewrite it.")
    text = message.strip()
    sheets: list[ServiceSheet] = []
    if _wants_human(text):
        card.status = "handed_off"
        body = "A person at the shop will follow up. The bay is not booked and no price is stated."
    else:
        known = _approved_for_service(session, card)
        if _asks_price(text):
            sheets = _sheets_named_in_message(session, card, text)
        parts: list[str] = []
        if _asks_price(text):
            if sheets:
                parts.extend(row.allowed_sentence for row in sheets)
            else:
                card.status = "handed_off"
                parts.append("The shop will confirm the price. No price is stated in this reply.")
        if not known:
            card.status = "handed_off"
        if _asks_booking(text):
            parts.append("The bay is not confirmed. The time is only a request.")
        if not parts:
            parts.append("The shop will review this request. The bay is not confirmed and no price is stated.")
        body = " ".join(parts)
    if card.status == "bay_confirmed":
        raise DomainError(409, "bay_not_confirmed", "The assistant cannot confirm a bay.")
    _guard_body(body, [row.allowed_sentence for row in sheets])
    reply = JobCardReply(
        job_card_id=card.id,
        body=body,
        sent=False,
        allowed_sheet_ids=[str(row.id) for row in sheets],
        price_allowed=bool(sheets),
    )
    session.add(reply)
    session.flush()
    audit(
        session,
        actor,
        "job_card.reply_drafted",
        "job_card",
        card.id,
        {"sent": False, "price_allowed": reply.price_allowed, "status": card.status, "company_id": str(card.company_id)},
    )
    return reply


def list_cards(session: Session) -> list[tuple[JobCard, list[JobCardReply]]]:
    cards = list(session.scalars(select(JobCard).order_by(JobCard.created_at.desc()).limit(100)))
    if not cards:
        return []
    ids = [row.id for row in cards]
    replies = list(session.scalars(select(JobCardReply).where(JobCardReply.job_card_id.in_(ids)).order_by(JobCardReply.created_at.desc())))
    grouped: dict = {row.id: [] for row in cards}
    for reply in replies:
        grouped[reply.job_card_id].append(reply)
    return [(row, grouped[row.id]) for row in cards]


def get_card(session: Session, card_id) -> tuple[JobCard, list[JobCardReply]]:
    card = require(session, JobCard, card_id, "Job card")
    replies = list(
        session.scalars(select(JobCardReply).where(JobCardReply.job_card_id == card.id).order_by(JobCardReply.created_at.desc()))
    )
    return card, replies


def request_bay_confirmation(session: Session, actor: User, card_id):
    from app.services.commercial import request_approval

    card = require(session, JobCard, card_id, "Job card")
    if card.status == "handed_off":
        raise DomainError(409, "handed_off", "A handed-off card cannot confirm a bay until a person reviews it.")
    return request_approval(
        session,
        actor,
        ApprovalIn(
            action_type="bind_price",
            subject_type="job_card",
            subject_id=card.id,
            payload={"confirm_bay": True},
            notes="Confirm the bay. The assistant cannot do this.",
        ),
    )


def apply_binding(session: Session, actor: User, approval) -> dict:
    if approval.subject_type == "service_sheet":
        sheet = require(session, ServiceSheet, approval.subject_id, "Service sheet")
        sheet.approval_id = approval.id
        sheet.status = "approved"
        audit(session, actor, "service_sheet.approved", "service_sheet", sheet.id, {"approval_id": str(approval.id)})
        return {"executed": True, "result": "service_sheet_approved", "service_sheet_id": str(sheet.id), "payment_executed": False}
    if approval.subject_type == "job_card":
        card = require(session, JobCard, approval.subject_id, "Job card")
        card.status = "bay_confirmed"
        audit(session, actor, "job_card.bay_confirmed", "job_card", card.id, {"approval_id": str(approval.id)})
        return {"executed": True, "result": "bay_confirmed", "job_card_id": str(card.id), "payment_executed": False}
    raise DomainError(422, "invalid_action", "This approval is not a job card or service sheet.")


def _approved_rows(session: Session, card: JobCard) -> list[ServiceSheet]:
    return list(
        session.scalars(select(ServiceSheet).where(ServiceSheet.company_id == card.company_id, ServiceSheet.status == "approved"))
    )


def _approved_for_service(session: Session, card: JobCard) -> bool:
    requested = card.requested_service.lower()
    return any(row.service_name.lower() in requested for row in _approved_rows(session, card))


def _sheets_named_in_message(session: Session, card: JobCard, message: str) -> list[ServiceSheet]:
    text = message.lower()
    return [row for row in _approved_rows(session, card) if row.service_name.lower() in text]


def _wants_human(text: str) -> bool:
    classified = classify_text(text)
    return classified in {"human_handoff", "opt_out"} or _HUMAN.search(text) is not None


def _asks_price(text: str) -> bool:
    return _PRICE_ASK.search(text) is not None


def _asks_booking(text: str) -> bool:
    return _BOOK_ASK.search(text) is not None


def _assert_sentence_matches_price(sentence: str, price: Decimal) -> None:
    numbers = [Decimal(item) for item in _NUMBER.findall(sentence)]
    if not numbers:
        raise DomainError(422, "price_not_in_sentence", "The allowed sentence must contain the sheet price and no other amount.")
    target = price.quantize(Decimal("0.01"))
    if any(item.quantize(Decimal("0.01")) != target for item in numbers):
        raise DomainError(422, "price_not_in_sentence", "The allowed sentence contains an amount that is not the sheet price.")


def _guard_body(body: str, allowed_sentences: list[str]) -> None:
    remainder = body
    for sentence in allowed_sentences:
        if sentence not in remainder:
            raise DomainError(422, "price_not_allowed", "The reply did not use the approved sentence.")
        remainder = remainder.replace(sentence, " ")
    if _LEFTOVER_PRICE.search(remainder):
        raise DomainError(422, "price_not_allowed", "The reply stated a price that is not on an approved sheet line.")


def __company():
    from app.models import Company

    return Company


def __contact():
    from app.models import Contact

    return Contact
