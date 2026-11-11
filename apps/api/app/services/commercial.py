from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit, audit_committed
from app.domain import BINDING_ACTIONS
from app.errors import DomainError
from app.models import (
    Agreement,
    Approval,
    BuyerRequirement,
    CommissionRecord,
    Company,
    Match,
    NotificationEvent,
    Opportunity,
    Product,
    ProductDocument,
    Rfq,
    SupplierOffer,
    User,
)
from app.serialize import money, money4, num, stamp
from app.services.common import country_code, currency_code, now, require


def public_offer(row: SupplierOffer) -> dict:
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "product_id": None if row.product_id is None else str(row.product_id),
        "rfq_id": None if row.rfq_id is None else str(row.rfq_id),
        "version": row.version,
        "unit_price": money4(row.unit_price),
        "currency": row.currency,
        "incoterms": row.incoterms,
        "moq": num(row.moq),
        "capacity": num(row.capacity),
        "lead_time_days": row.lead_time_days,
        "origin_country": row.origin_country,
        "certifications": list(row.certifications or []),
        "delivery_terms": row.delivery_terms,
        "valid_until": stamp(row.valid_until),
        "notes": row.notes,
        "created_at": stamp(row.created_at),
    }


def public_opportunity(row: Opportunity) -> dict:
    return {
        "id": str(row.id),
        "buyer_company_id": str(row.buyer_company_id),
        "supplier_company_id": None if row.supplier_company_id is None else str(row.supplier_company_id),
        "buyer_requirement_id": None if row.buyer_requirement_id is None else str(row.buyer_requirement_id),
        "title": row.title,
        "stage": row.stage,
        "status": row.status,
        "pipeline_value": money(row.pipeline_value),
        "currency": row.currency,
        "created_at": stamp(row.created_at),
    }


def public_approval(row: Approval) -> dict:
    return {
        "id": str(row.id),
        "action_type": row.action_type,
        "status": row.status,
        "requested_by": str(row.requested_by),
        "decided_by": None if row.decided_by is None else str(row.decided_by),
        "subject_type": row.subject_type,
        "subject_id": str(row.subject_id),
        "payload": row.payload,
        "notes": row.notes,
        "decision_note": row.decision_note,
        "outcome": None if not row.payload else row.payload.get("outcome"),
        "created_at": stamp(row.created_at),
        "decided_at": stamp(row.decided_at),
    }


def _notify(session: Session, kind: str, title: str, body: str) -> None:
    founders = list(session.scalars(select(User).where(User.role == "founder", User.is_active.is_(True))))
    if not founders:
        session.add(NotificationEvent(user_id=None, kind=kind, title=title, body=body))
        return
    for founder in founders:
        session.add(NotificationEvent(user_id=founder.id, kind=kind, title=title, body=body))


def create_product(session: Session, actor: User, data) -> Product:
    company = require(session, Company, data.company_id, "Company")
    if company.role not in {"supplier", "both"}:
        raise DomainError(409, "wrong_role", "Products belong to a supplier.")
    product = Product(
        company_id=company.id,
        name=data.name.strip(),
        category=data.category,
        specifications=data.specifications,
    )
    session.add(product)
    session.flush()
    audit(session, actor, "product.created", "product", product.id, {})
    return product


def create_offer(session: Session, actor: User, data) -> SupplierOffer:
    company = require(session, Company, data.company_id, "Company")
    if company.role not in {"supplier", "both"}:
        raise DomainError(409, "wrong_role", "Quotations belong to a supplier.")
    if data.rfq_id is not None:
        require(session, Rfq, data.rfq_id, "RFQ")
    if data.product_id is not None:
        require(session, Product, data.product_id, "Product")
    version_query = select(func.max(SupplierOffer.version)).where(SupplierOffer.company_id == company.id)
    if data.rfq_id is None:
        version_query = version_query.where(SupplierOffer.rfq_id.is_(None))
    else:
        version_query = version_query.where(SupplierOffer.rfq_id == data.rfq_id)
    current = session.scalar(version_query)
    offer = SupplierOffer(
        company_id=company.id,
        product_id=data.product_id,
        rfq_id=data.rfq_id,
        version=int(current or 0) + 1,
        unit_price=data.unit_price,
        currency=currency_code(data.currency),
        incoterms=data.incoterms,
        moq=data.moq,
        capacity=data.capacity,
        lead_time_days=data.lead_time_days,
        origin_country=country_code(data.origin_country),
        certifications=data.certifications,
        delivery_terms=data.delivery_terms,
        notes=data.notes,
    )
    session.add(offer)
    session.flush()
    if data.rfq_id is not None:
        rfq = session.get(Rfq, data.rfq_id)
        if rfq is not None and rfq.status in {"draft", "sent"}:
            rfq.status = "quoted"
    audit(session, actor, "offer.recorded", "supplier_offer", offer.id, {"version": offer.version})
    return offer


def create_opportunity(session: Session, actor: User, data) -> Opportunity:
    buyer = require(session, Company, data.buyer_company_id, "Buyer")
    if buyer.role not in {"buyer", "both"}:
        raise DomainError(409, "wrong_role", "Opportunity buyer must be a buyer company.")
    if data.supplier_company_id is not None:
        supplier = require(session, Company, data.supplier_company_id, "Supplier")
        if supplier.role not in {"supplier", "both"}:
            raise DomainError(409, "wrong_role", "Opportunity supplier must be a supplier company.")
    if data.buyer_requirement_id is not None:
        require(session, BuyerRequirement, data.buyer_requirement_id, "Requirement")
    row = Opportunity(
        buyer_company_id=data.buyer_company_id,
        supplier_company_id=data.supplier_company_id,
        buyer_requirement_id=data.buyer_requirement_id,
        title=data.title.strip(),
        pipeline_value=data.pipeline_value,
        currency=currency_code(data.currency) or "USD",
    )
    session.add(row)
    session.flush()
    audit(session, actor, "opportunity.created", "opportunity", row.id, {"title": row.title})
    return row


def create_rfq(session: Session, actor: User, data) -> Rfq:
    requirement = require(session, BuyerRequirement, data.buyer_requirement_id, "Requirement")
    if data.opportunity_id is not None:
        require(session, Opportunity, data.opportunity_id, "Opportunity")
    row = Rfq(
        buyer_requirement_id=requirement.id,
        opportunity_id=data.opportunity_id,
        notes=data.notes,
        requested_samples=data.requested_samples,
        requested_documents=data.requested_documents,
    )
    session.add(row)
    session.flush()
    audit(session, actor, "rfq.created", "rfq", row.id, {})
    return row


def explain_match(requirement: BuyerRequirement, offer: SupplierOffer, product: Product | None, document_count: int) -> dict:
    matched: list[str] = []
    missing: list[str] = []
    conflicts: list[str] = []

    def compare(label: str, left, right, predicate) -> None:
        if left in (None, "") or right in (None, ""):
            missing.append(label)
        elif predicate():
            matched.append(label)
        else:
            conflicts.append(label)

    supplier_category = None if product is None else product.category
    compare(
        "category",
        requirement.product_category,
        supplier_category,
        lambda: supplier_category is not None and requirement.product_category.lower() == supplier_category.lower(),
    )
    compare(
        "moq_versus_quantity",
        requirement.desired_quantity,
        offer.moq,
        lambda: requirement.desired_quantity is not None and offer.moq is not None and requirement.desired_quantity >= offer.moq,
    )
    compare(
        "capacity",
        requirement.desired_quantity,
        offer.capacity,
        lambda: offer.capacity is not None and requirement.desired_quantity is not None and offer.capacity >= requirement.desired_quantity,
    )
    if not offer.origin_country or not requirement.destination_country:
        missing.append("origin_destination")
    else:
        matched.append("origin_destination")
    required = {item.lower() for item in (requirement.required_certifications or [])}
    offered = {item.lower() for item in (offer.certifications or [])}
    if required.issubset(offered):
        matched.append("certifications")
    else:
        conflicts.append("certifications")
    compare(
        "lead_time",
        requirement.lead_time_days,
        offer.lead_time_days,
        lambda: offer.lead_time_days is not None and requirement.lead_time_days is not None and offer.lead_time_days <= requirement.lead_time_days,
    )
    compare(
        "delivery_terms",
        requirement.delivery_terms,
        offer.delivery_terms,
        lambda: requirement.delivery_terms is not None and offer.delivery_terms is not None and requirement.delivery_terms.lower() == offer.delivery_terms.lower(),
    )
    compare(
        "currency",
        requirement.currency,
        offer.currency,
        lambda: requirement.currency is not None and offer.currency is not None and requirement.currency.upper() == offer.currency.upper(),
    )
    compare(
        "incoterms",
        requirement.incoterms,
        offer.incoterms,
        lambda: requirement.incoterms is not None and offer.incoterms is not None and requirement.incoterms.lower() == offer.incoterms.lower(),
    )
    if offer.unit_price is None:
        missing.append("unit_price")
    else:
        matched.append("unit_price_present")
    if document_count > 0:
        matched.append("documentation")
    else:
        missing.append("documentation")
    comparable = len(matched) + len(conflicts)
    score = Decimal("0") if comparable == 0 else (Decimal(len(matched)) / Decimal(comparable))
    confidence = max(Decimal("0.20"), Decimal("1") - (Decimal("0.08") * len(missing)))
    if missing:
        confidence = min(confidence, Decimal("0.70"))
    return {
        "score": score.quantize(Decimal("0.0001")),
        "confidence_cap": confidence.quantize(Decimal("0.0001")),
        "explanation": {
            "matched": matched,
            "missing": missing,
            "conflicts": conflicts,
            "limitations": [
                "Landed cost is not calculated.",
                "Unit price is only the supplier's stated price.",
                "A missing field lowers the confidence cap and is not treated as a match.",
            ],
        },
    }


def create_match(session: Session, actor: User, data) -> Match:
    opportunity = require(session, Opportunity, data.opportunity_id, "Opportunity")
    requirement = require(session, BuyerRequirement, data.buyer_requirement_id, "Requirement")
    offer = require(session, SupplierOffer, data.supplier_offer_id, "Supplier offer")
    product = None if offer.product_id is None else session.get(Product, offer.product_id)
    document_count = 0
    if product is not None:
        document_count = int(
            session.scalar(select(func.count(ProductDocument.id)).where(ProductDocument.product_id == product.id)) or 0
        )
    scored = explain_match(requirement, offer, product, document_count)
    row = Match(
        opportunity_id=opportunity.id,
        buyer_requirement_id=requirement.id,
        supplier_offer_id=offer.id,
        score=scored["score"],
        confidence_cap=scored["confidence_cap"],
        explanation=scored["explanation"],
    )
    session.add(row)
    session.flush()
    if opportunity.supplier_company_id is None:
        opportunity.supplier_company_id = offer.company_id
    if opportunity.stage == "draft":
        opportunity.stage = "quoting"
    audit(session, actor, "match.created", "match", row.id, {"score": str(row.score), "confidence_cap": str(row.confidence_cap)})
    return row


def public_match(row: Match) -> dict:
    return {
        "id": str(row.id),
        "opportunity_id": str(row.opportunity_id),
        "buyer_requirement_id": str(row.buyer_requirement_id),
        "supplier_offer_id": str(row.supplier_offer_id),
        "score": num(row.score),
        "confidence_cap": num(row.confidence_cap),
        "explanation": row.explanation,
        "created_at": stamp(row.created_at),
    }


def create_agreement(session: Session, actor: User, data) -> Agreement:
    opportunity = require(session, Opportunity, data.opportunity_id, "Opportunity")
    existing = session.scalar(select(Agreement).where(Agreement.opportunity_id == opportunity.id))
    if existing is not None:
        raise DomainError(409, "duplicate_agreement", "This opportunity already has an agreement.", {"existing_id": str(existing.id)})
    row = Agreement(opportunity_id=opportunity.id, terms=data.terms, evidence_note=data.evidence_note, status="draft")
    session.add(row)
    session.flush()
    audit(session, actor, "agreement.drafted", "agreement", row.id, {})
    return row


def create_commission_draft(session: Session, actor: User, data) -> CommissionRecord:
    opportunity = require(session, Opportunity, data.opportunity_id, "Opportunity")
    if data.agreement_id is not None:
        require(session, Agreement, data.agreement_id, "Agreement")
    row = CommissionRecord(
        opportunity_id=opportunity.id,
        agreement_id=data.agreement_id,
        terms_text=data.terms_text,
        currency=currency_code(data.currency) or "USD",
        rate_percent=None,
        contracted_amount=None,
    )
    session.add(row)
    session.flush()
    audit(session, actor, "commission.drafted", "commission_record", row.id, {})
    return row


def record_collection(session: Session, actor: User, commission_id, data) -> CommissionRecord:
    row = require(session, CommissionRecord, commission_id, "Commission record")
    if data.amount <= 0:
        raise DomainError(422, "invalid_amount", "Collected amount must be positive.")
    row.collected_amount = Decimal(row.collected_amount or 0) + Decimal(data.amount)
    if data.invoice_reference:
        row.invoice_reference = data.invoice_reference
        if row.collection_status == "none":
            row.collection_status = "invoiced"
    if row.contracted_amount is not None and row.collected_amount >= Decimal(row.contracted_amount):
        row.collection_status = "collected"
    elif row.collected_amount > 0:
        row.collection_status = "partial"
    audit(session, actor, "commission.collection_recorded", "commission_record", row.id, {"amount": str(data.amount)})
    return row


def public_commission(row: CommissionRecord) -> dict:
    return {
        "id": str(row.id),
        "opportunity_id": str(row.opportunity_id),
        "agreement_id": None if row.agreement_id is None else str(row.agreement_id),
        "terms_text": row.terms_text,
        "rate_percent": num(row.rate_percent),
        "contracted_amount": money(row.contracted_amount),
        "collected_amount": money(row.collected_amount),
        "currency": row.currency,
        "collection_status": row.collection_status,
        "invoice_reference": row.invoice_reference,
        "approval_id": None if row.approval_id is None else str(row.approval_id),
    }


def request_approval(session: Session, actor: User, data) -> Approval:
    if data.action_type not in BINDING_ACTIONS:
        raise DomainError(422, "invalid_action", "This action does not require the approval register.")
    row = Approval(
        action_type=data.action_type,
        status="pending",
        requested_by=actor.id,
        subject_type=data.subject_type,
        subject_id=data.subject_id,
        payload=data.payload,
        notes=data.notes,
    )
    session.add(row)
    session.flush()
    if data.action_type == "sign_agreement" and data.subject_type == "agreement":
        agreement = require(session, Agreement, data.subject_id, "Agreement")
        agreement.status = "pending_approval"
    _notify(session, "approval.requested", "Founder approval required", f"{data.action_type} is waiting for a decision.")
    audit(session, actor, "approval.requested", "approval", row.id, {"action_type": data.action_type})
    return row


def decide_approval(session: Session, actor: User, approval_id, decision: str, note: str) -> Approval:
    row = require(session, Approval, approval_id, "Approval")
    if actor.role != "founder":
        audit_committed(actor, "approval.denied", "approval", row.id, {"reason": "founder_required"})
        raise DomainError(403, "founder_required", "Only the founder can approve or reject binding actions.")
    if decision not in {"approved", "rejected"}:
        raise DomainError(422, "invalid_decision", "Decision must be approved or rejected.")
    if row.status != "pending":
        raise DomainError(409, "already_decided", "This approval is no longer pending.")
    row.status = decision
    row.decided_by = actor.id
    row.decision_note = note
    row.decided_at = now()
    if decision == "rejected" and row.subject_type == "agreement":
        agreement = session.get(Agreement, row.subject_id)
        if agreement is not None and agreement.status == "pending_approval":
            agreement.status = "rejected"
    _notify(session, "approval.decided", f"Approval {decision}", note or row.action_type)
    audit(session, actor, "approval.decided", "approval", row.id, {"decision": decision})
    return row


def execute_approval(session: Session, actor: User, approval_id) -> dict:
    row = require(session, Approval, approval_id, "Approval")
    stored = dict(row.payload or {}).get("outcome")
    if isinstance(stored, dict):
        return stored
    if actor.role != "founder":
        audit_committed(actor, "binding.denied", "approval", row.id, {"reason": "founder_required"})
        raise DomainError(403, "founder_required", "Only the founder can execute a binding action.")
    if row.status != "approved":
        audit_committed(actor, "binding.denied", "approval", row.id, {"reason": "approval_required", "status": row.status})
        raise DomainError(403, "approval_required", "Binding action is blocked until the founder approves it.")
    if row.action_type == "sign_agreement":
        agreement = require(session, Agreement, row.subject_id, "Agreement")
        agreement.approval_id = row.id
        agreement.status = "signed"
        agreement.signed_at = now()
        opportunity = session.get(Opportunity, agreement.opportunity_id)
        if opportunity is not None:
            opportunity.stage = "approval"
        audit(session, actor, "agreement.signed", "agreement", agreement.id, {"approval_id": str(row.id)})
        return _store_outcome(row, {"executed": True, "result": "agreement_signed", "agreement_id": str(agreement.id)})
    if row.action_type == "bind_commission":
        commission = require(session, CommissionRecord, row.subject_id, "Commission record")
        payload = row.payload or {}
        if "rate_percent" not in payload or "contracted_amount" not in payload:
            raise DomainError(422, "invalid_payload", "Commission approval payload needs rate_percent and contracted_amount.")
        commission.approval_id = row.id
        commission.rate_percent = Decimal(str(payload["rate_percent"]))
        commission.contracted_amount = Decimal(str(payload["contracted_amount"]))
        if payload.get("terms_text"):
            commission.terms_text = str(payload["terms_text"])
        audit(session, actor, "commission.bound", "commission_record", commission.id, {"approval_id": str(row.id)})
        return _store_outcome(row, {"executed": True, "result": "commission_terms_recorded", "commission_id": str(commission.id)})
    if row.action_type == "bind_price" and row.subject_type in {"service_sheet", "job_card"}:
        from app.services.job_cards import apply_binding

        return _store_outcome(row, apply_binding(session, actor, row))
    if row.action_type == "bind_price":
        audit(session, actor, "price.accepted", "approval", row.id, {"payload": row.payload})
        return _store_outcome(row, {"executed": True, "result": "price_acceptance_recorded", "payment_executed": False})
    if row.action_type == "send_outreach":
        from app.services.alex import execute_outreach

        return _store_outcome(row, execute_outreach(session, actor, row))
    if row.action_type == "payment":
        audit(session, actor, "payment.not_executed", "approval", row.id, {"reason": "platform_does_not_execute_payments"})
        return _store_outcome(row, {"executed": False, "result": "payment_not_executed", "reason": "YES SALES does not execute payments."})
    audit(session, actor, "binding.recorded", "approval", row.id, {"action_type": row.action_type})
    return _store_outcome(row, {"executed": False, "result": "recorded_only", "action_type": row.action_type})


def _store_outcome(row: Approval, outcome: dict) -> dict:
    payload = dict(row.payload or {})
    payload["outcome"] = outcome
    row.payload = payload
    return outcome


def compatible_suppliers(session: Session, requirement_id) -> dict:
    requirement = require(session, BuyerRequirement, requirement_id, "Buyer requirement")
    rows = session.execute(
        select(Company, Product)
        .join(Product, Product.company_id == Company.id)
        .where(
            Company.role.in_(["supplier", "both"]),
            Product.category.is_not(None),
            func.lower(Product.category) == requirement.product_category.lower(),
        )
        .order_by(Company.legal_name, Product.name)
    ).all()
    return {
        "requirement_id": str(requirement.id),
        "product_category": requirement.product_category,
        "suppliers": [
            {
                "company_id": str(company.id),
                "legal_name": company.legal_name,
                "product_id": str(product.id),
                "product_name": product.name,
                "category": product.category,
            }
            for company, product in rows
        ],
        "limitations": ["Compatibility uses the stored product category only. Landed cost is not calculated."],
    }


def compare_offers(session: Session, rfq_id) -> dict:
    rfq = require(session, Rfq, rfq_id, "RFQ")
    offers = list(session.scalars(select(SupplierOffer).where(SupplierOffer.rfq_id == rfq.id).order_by(SupplierOffer.version)))
    return {
        "rfq_id": str(rfq.id),
        "status": rfq.status,
        "offers": [public_offer(item) for item in offers],
        "limitations": ["Landed cost is not calculated.", "Comparison uses only stored quotation fields."],
    }


def public_agreement(row: Agreement) -> dict:
    return {
        "id": str(row.id),
        "opportunity_id": str(row.opportunity_id),
        "status": row.status,
        "terms": row.terms,
        "evidence_note": row.evidence_note,
        "approval_id": None if row.approval_id is None else str(row.approval_id),
        "signed_at": stamp(row.signed_at),
    }


def deal_board(session: Session) -> list[dict]:
    rows = list(session.scalars(select(Opportunity).order_by(Opportunity.created_at.desc()).limit(200)))
    output = []
    for row in rows:
        buyer = session.get(Company, row.buyer_company_id)
        supplier = None if row.supplier_company_id is None else session.get(Company, row.supplier_company_id)
        rfqs = list(session.scalars(select(Rfq).where(Rfq.opportunity_id == row.id).order_by(Rfq.created_at)))
        output.append(
            {
                **public_opportunity(row),
                "buyer_name": None if buyer is None else buyer.legal_name,
                "supplier_name": None if supplier is None else supplier.legal_name,
                "rfqs": [{"id": str(item.id), "status": item.status} for item in rfqs],
            }
        )
    return output
