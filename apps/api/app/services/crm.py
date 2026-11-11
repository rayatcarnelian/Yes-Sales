import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.errors import DomainError
from app.models import (
    AuditEvent,
    BuyerRequirement,
    Company,
    Contact,
    ContactPermission,
    Conversation,
    ResearchSource,
    SupplierOffer,
    User,
)
from app.serialize import num, stamp
from app.services.common import country_code, currency_code, normalize_channel_value, normalize_name, require, website_domain


def public_company(company: Company) -> dict:
    return {
        "id": str(company.id),
        "legal_name": company.legal_name,
        "country": company.country,
        "website": company.website,
        "website_domain": company.website_domain,
        "role": company.role,
        "category": company.category,
        "verification_status": company.verification_status,
        "supplier_stage": company.supplier_stage,
        "buyer_stage": company.buyer_stage,
        "summary": company.summary,
        "is_test": company.is_test,
        "created_at": stamp(company.created_at),
        "updated_at": stamp(company.updated_at),
    }


def public_contact(contact: Contact, permission: ContactPermission | None) -> dict:
    payload: dict[str, object] = {
        "id": str(contact.id),
        "company_id": str(contact.company_id),
        "full_name": contact.full_name,
        "title": contact.title,
        "channel": contact.channel,
        "value": contact.value,
        "is_public_business": contact.is_public_business,
        "source_url": contact.source_url,
        "created_at": stamp(contact.created_at),
    }
    if permission is not None:
        payload["permission"] = {
            "allowed": permission.allowed,
            "opted_out": permission.opted_out,
            "opted_out_at": stamp(permission.opted_out_at),
            "consent_for_callback": permission.consent_for_callback,
            "authorization_basis": permission.authorization_basis,
            "daily_limit": permission.daily_limit,
            "notes": permission.notes,
        }
    return payload


def public_requirement(row: BuyerRequirement) -> dict:
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "product_category": row.product_category,
        "specifications": row.specifications,
        "desired_quantity": num(row.desired_quantity),
        "moq_acceptable": num(row.moq_acceptable),
        "destination_country": row.destination_country,
        "required_certifications": list(row.required_certifications or []),
        "lead_time_days": row.lead_time_days,
        "delivery_terms": row.delivery_terms,
        "currency": row.currency,
        "incoterms": row.incoterms,
        "notes": row.notes,
        "created_at": stamp(row.created_at),
    }


def create_company(session: Session, actor: User, data) -> Company:
    if data.role not in {"supplier", "buyer", "both"}:
        raise DomainError(422, "invalid_role", "Role must be supplier, buyer, or both.")
    normalized = normalize_name(data.legal_name)
    country = country_code(data.country)
    domain = website_domain(data.website)
    existing = session.scalar(
        select(Company).where(Company.normalized_name == normalized, Company.country == country)
    )
    if existing is not None:
        raise DomainError(409, "duplicate_company", "A company with this name and country already exists.", {"existing_id": str(existing.id)})
    if domain is not None:
        by_domain = session.scalar(select(Company).where(Company.website_domain == domain))
        if by_domain is not None:
            raise DomainError(409, "duplicate_company", "A company with this website domain already exists.", {"existing_id": str(by_domain.id)})
    company = Company(
        legal_name=data.legal_name.strip(),
        normalized_name=normalized,
        country=country,
        website=data.website.strip() if data.website else None,
        website_domain=domain,
        role=data.role,
        category=data.category,
        summary=data.summary,
        is_test=data.is_test,
        supplier_stage="discover" if data.role in {"supplier", "both"} else None,
        buyer_stage="discover" if data.role in {"buyer", "both"} else None,
    )
    session.add(company)
    session.flush()
    audit(session, actor, "company.created", "company", company.id, {"legal_name": company.legal_name})
    return company


def list_companies(session: Session, q: str | None, country: str | None, role: str | None, verification: str | None, category: str | None) -> list[Company]:
    stmt = select(Company).order_by(Company.legal_name)
    if q:
        stmt = stmt.where(Company.legal_name.ilike(f"%{q.strip()}%"))
    if country:
        stmt = stmt.where(Company.country == country_code(country))
    if role:
        stmt = stmt.where(Company.role == role)
    if verification:
        stmt = stmt.where(Company.verification_status == verification)
    if category:
        stmt = stmt.where(Company.category.ilike(f"%{category.strip()}%"))
    return list(session.scalars(stmt.limit(200)))


def company_profile(session: Session, company_id: uuid.UUID) -> dict:
    company = require(session, Company, company_id, "Company")
    contacts = list(session.scalars(select(Contact).where(Contact.company_id == company.id).order_by(Contact.full_name)))
    contact_ids = [item.id for item in contacts]
    permissions = {}
    if contact_ids:
        for permission in session.scalars(select(ContactPermission).where(ContactPermission.contact_id.in_(contact_ids))):
            permissions[permission.contact_id] = permission
    sources = list(session.scalars(select(ResearchSource).where(ResearchSource.company_id == company.id)))
    requirements = list(session.scalars(select(BuyerRequirement).where(BuyerRequirement.company_id == company.id)))
    offers = list(session.scalars(select(SupplierOffer).where(SupplierOffer.company_id == company.id)))
    conversations = list(session.scalars(select(Conversation).where(Conversation.company_id == company.id)))
    activity_filters = [AuditEvent.entity_id == company.id, AuditEvent.detail["company_id"].astext == str(company.id)]
    if contact_ids:
        activity_filters.append(AuditEvent.entity_id.in_(contact_ids))
    activity = list(
        session.scalars(select(AuditEvent).where(or_(*activity_filters)).order_by(AuditEvent.created_at.desc()).limit(30))
    )
    return {
        "company": public_company(company),
        "contacts": [public_contact(item, permissions.get(item.id)) for item in contacts],
        "sources": [
            {
                "id": str(item.id),
                "source_url": item.source_url,
                "source_title": item.source_title,
                "retrieved_at": stamp(item.retrieved_at),
                "excerpt": item.excerpt,
                "provider": item.provider,
                "provider_mode": item.provider_mode,
                "evidence_fields": item.evidence_fields,
            }
            for item in sources
        ],
        "requirements": [public_requirement(item) for item in requirements],
        "offers": [
            {
                "id": str(item.id),
                "version": item.version,
                "unit_price": num(item.unit_price),
                "currency": item.currency,
                "rfq_id": None if item.rfq_id is None else str(item.rfq_id),
            }
            for item in offers
        ],
        "conversations": [
            {"id": str(item.id), "status": item.status, "channel": item.channel, "subject": item.subject}
            for item in conversations
        ],
        "activity": [
            {
                "id": str(item.id),
                "action": item.action,
                "entity_type": item.entity_type,
                "created_at": stamp(item.created_at),
                "detail": item.detail,
            }
            for item in activity
        ],
    }


def create_contact(session: Session, actor: User, company_id: uuid.UUID, data) -> tuple[Contact, ContactPermission]:
    company = require(session, Company, company_id, "Company")
    if data.channel not in {"email", "phone", "whatsapp"}:
        raise DomainError(422, "invalid_channel", "Channel must be email, phone, or whatsapp.")
    if data.authorization_basis not in {"public_business", "explicit_consent", "unknown"}:
        raise DomainError(422, "invalid_authorization", "Authorization basis is invalid.")
    normalized = normalize_channel_value(data.channel, data.value)
    existing = session.scalar(
        select(Contact).where(
            Contact.company_id == company.id,
            Contact.channel == data.channel,
            Contact.normalized_value == normalized,
        )
    )
    if existing is not None:
        raise DomainError(409, "duplicate_contact", "This contact channel already exists on the company.", {"existing_id": str(existing.id)})
    contact = Contact(
        company_id=company.id,
        full_name=data.full_name.strip(),
        title=data.title,
        channel=data.channel,
        value=data.value.strip(),
        normalized_value=normalized,
        is_public_business=data.is_public_business,
        source_url=data.source_url,
    )
    session.add(contact)
    session.flush()
    permission = ContactPermission(
        contact_id=contact.id,
        allowed=data.allowed,
        authorization_basis=data.authorization_basis,
        consent_for_callback=data.consent_for_callback,
        daily_limit=data.daily_limit,
    )
    session.add(permission)
    audit(session, actor, "contact.created", "contact", contact.id, {"company_id": str(company.id), "channel": contact.channel})
    return contact, permission


def update_permission(session: Session, actor: User, contact_id: uuid.UUID, data) -> ContactPermission:
    contact = require(session, Contact, contact_id, "Contact")
    permission = session.scalar(select(ContactPermission).where(ContactPermission.contact_id == contact.id))
    if permission is None:
        raise DomainError(404, "not_found", "Contact permission was not found.")
    if data.authorization_basis not in {"public_business", "explicit_consent", "unknown"}:
        raise DomainError(422, "invalid_authorization", "Authorization basis is invalid.")
    if permission.opted_out and data.allowed and not data.clear_opt_out:
        raise DomainError(409, "opted_out", "This contact has opted out. Outreach stays blocked.")
    if data.clear_opt_out:
        if actor.role != "founder":
            raise DomainError(403, "founder_required", "Only the founder can clear an opt-out.")
        permission.opted_out = False
        permission.opted_out_at = None
        audit(session, actor, "contact.opt_out_cleared", "contact", contact.id, {})
    permission.allowed = data.allowed
    permission.authorization_basis = data.authorization_basis
    permission.consent_for_callback = data.consent_for_callback
    permission.daily_limit = data.daily_limit
    permission.notes = data.notes
    audit(session, actor, "contact.permission_updated", "contact", contact.id, {"allowed": permission.allowed})
    return permission


def create_requirement(session: Session, actor: User, data) -> BuyerRequirement:
    company = require(session, Company, data.company_id, "Company")
    if company.role not in {"buyer", "both"}:
        raise DomainError(409, "wrong_role", "Requirements can only be stored for a buyer.")
    row = BuyerRequirement(
        company_id=company.id,
        product_category=data.product_category.strip(),
        specifications=data.specifications,
        desired_quantity=data.desired_quantity,
        moq_acceptable=data.moq_acceptable,
        destination_country=country_code(data.destination_country),
        required_certifications=data.required_certifications,
        lead_time_days=data.lead_time_days,
        delivery_terms=data.delivery_terms,
        currency=currency_code(data.currency),
        incoterms=data.incoterms,
        notes=data.notes,
    )
    session.add(row)
    session.flush()
    audit(session, actor, "requirement.created", "buyer_requirement", row.id, {"company_id": str(company.id)})
    return row


def search_contacts(session: Session, q: str | None) -> list[tuple[Contact, ContactPermission | None]]:
    stmt = select(Contact).order_by(Contact.full_name)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Contact.full_name.ilike(like), Contact.value.ilike(like)))
    contacts = list(session.scalars(stmt.limit(200)))
    output = []
    for contact in contacts:
        permission = session.scalar(select(ContactPermission).where(ContactPermission.contact_id == contact.id))
        output.append((contact, permission))
    return output
