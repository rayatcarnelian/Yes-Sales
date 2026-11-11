from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit
from app.domain import BUYER_STAGES, SUPPLIER_STAGES, assert_transition
from app.errors import DomainError
from app.models import Company, Contact, ContactPermission, ResearchSource, User
from app.services.common import normalize_name, require
from app.services.research import parse_evidence


def _has_source(session: Session, company_id) -> bool:
    return session.scalar(select(ResearchSource.id).where(ResearchSource.company_id == company_id).limit(1)) is not None


def _has_human_source(session: Session, company: Company) -> bool:
    rows = session.scalars(
        select(ResearchSource).where(
            ResearchSource.company_id == company.id,
            ResearchSource.provider.in_(["manual", "http"]),
        )
    )
    for row in rows:
        if company.legal_name.lower() not in row.excerpt.lower():
            continue
        named = parse_evidence(row.excerpt).get("company")
        if named is not None and normalize_name(named) == company.normalized_name:
            return True
    return False


def _has_eligible_contact(session: Session, company_id) -> bool:
    row = session.scalar(
        select(Contact.id)
        .join(ContactPermission, ContactPermission.contact_id == Contact.id)
        .where(
            Contact.company_id == company_id,
            ContactPermission.allowed.is_(True),
            ContactPermission.opted_out.is_(False),
        )
        .limit(1)
    )
    return row is not None


def transition(session: Session, actor: User, company_id, side: str, to_stage: str) -> Company:
    company = require(session, Company, company_id, "Company")
    if side == "supplier":
        if company.role not in {"supplier", "both"} or company.supplier_stage is None:
            raise DomainError(409, "wrong_role", "This company is not on the supplier pipeline.")
        assert_transition(SUPPLIER_STAGES, company.supplier_stage, to_stage)
        if to_stage == "verify" and not _has_source(session, company.id):
            raise DomainError(422, "evidence_required", "A research source is required before verification.")
        if to_stage == "contact_eligible" and not _has_eligible_contact(session, company.id):
            raise DomainError(422, "contact_not_eligible", "An allowed, non-opted-out contact is required.")
        previous = company.supplier_stage
        company.supplier_stage = to_stage
    elif side == "buyer":
        if company.role not in {"buyer", "both"} or company.buyer_stage is None:
            raise DomainError(409, "wrong_role", "This company is not on the buyer pipeline.")
        assert_transition(BUYER_STAGES, company.buyer_stage, to_stage)
        if to_stage == "verify" and not _has_source(session, company.id):
            raise DomainError(422, "evidence_required", "A research source is required before verification.")
        if to_stage == "contact_eligible" and not _has_eligible_contact(session, company.id):
            raise DomainError(422, "contact_not_eligible", "An allowed, non-opted-out contact is required.")
        previous = company.buyer_stage
        company.buyer_stage = to_stage
    else:
        raise DomainError(422, "invalid_side", "Side must be supplier or buyer.")
    audit(session, actor, "pipeline.transition", "company", company.id, {"side": side, "from": previous, "to": to_stage})
    return company


def set_verification(session: Session, actor: User, company_id, status: str) -> Company:
    company = require(session, Company, company_id, "Company")
    if status not in {"verified", "rejected"}:
        raise DomainError(422, "invalid_status", "Verification status must be verified or rejected.")
    if status == "verified" and not _has_human_source(session, company):
        raise DomainError(
            422,
            "evidence_required",
            "Verification requires a human-recorded source that names this company. A bot import cannot verify it.",
        )
    company.verification_status = status
    audit(session, actor, "company.verification_changed", "company", company.id, {"status": status})
    return company


def next_stage(company: Company, side: str) -> str | None:
    if side == "supplier" and company.supplier_stage in SUPPLIER_STAGES:
        index = SUPPLIER_STAGES.index(company.supplier_stage)
        return None if index + 1 >= len(SUPPLIER_STAGES) else SUPPLIER_STAGES[index + 1]
    if side == "buyer" and company.buyer_stage in BUYER_STAGES:
        index = BUYER_STAGES.index(company.buyer_stage)
        return None if index + 1 >= len(BUYER_STAGES) else BUYER_STAGES[index + 1]
    return None
