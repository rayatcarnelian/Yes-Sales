import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=text("now()"))


def _updated() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=text("now()"))


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _uuid()
    email: Mapped[str] = mapped_column(Text, unique=True)
    full_name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    supabase_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class UserCredential(Base):
    __tablename__ = "user_credentials"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[uuid.UUID] = _uuid()
    legal_name: Mapped[str] = mapped_column(Text)
    normalized_name: Mapped[str] = mapped_column(Text)
    country: Mapped[str] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(Text)
    website_domain: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(Text, default="unverified")
    supplier_stage: Mapped[str | None] = mapped_column(Text)
    buyer_stage: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[uuid.UUID] = _uuid()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    full_name: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text)
    normalized_value: Mapped[str] = mapped_column(Text)
    is_public_business: Mapped[bool] = mapped_column(Boolean, default=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class ContactPermission(Base):
    __tablename__ = "contact_permissions"
    id: Mapped[uuid.UUID] = _uuid()
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), unique=True)
    allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_for_callback: Mapped[bool] = mapped_column(Boolean, default=False)
    authorization_basis: Mapped[str] = mapped_column(Text, default="unknown")
    daily_limit: Mapped[int] = mapped_column(Integer, default=3)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class ResearchSource(Base):
    __tablename__ = "research_sources"
    id: Mapped[uuid.UUID] = _uuid()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    source_url: Mapped[str] = mapped_column(Text)
    source_title: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    excerpt: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text)
    provider_mode: Mapped[str] = mapped_column(Text)
    evidence_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()


class Product(Base):
    __tablename__ = "products"
    id: Mapped[uuid.UUID] = _uuid()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    specifications: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class ProductDocument(Base):
    __tablename__ = "product_documents"
    id: Mapped[uuid.UUID] = _uuid()
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))
    doc_type: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text)
    byte_size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = _created()


class BuyerRequirement(Base):
    __tablename__ = "buyer_requirements"
    id: Mapped[uuid.UUID] = _uuid()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    product_category: Mapped[str] = mapped_column(Text)
    specifications: Mapped[dict] = mapped_column(JSONB, default=dict)
    desired_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    moq_acceptable: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    destination_country: Mapped[str | None] = mapped_column(Text)
    required_certifications: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    delivery_terms: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str | None] = mapped_column(Text)
    incoterms: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Opportunity(Base):
    __tablename__ = "opportunities"
    id: Mapped[uuid.UUID] = _uuid()
    buyer_company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    supplier_company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    buyer_requirement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("buyer_requirements.id"))
    title: Mapped[str] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(Text, default="draft")
    status: Mapped[str] = mapped_column(Text, default="open")
    pipeline_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(Text, default="USD")
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Rfq(Base):
    __tablename__ = "rfqs"
    id: Mapped[uuid.UUID] = _uuid()
    buyer_requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("buyer_requirements.id"))
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("opportunities.id"))
    status: Mapped[str] = mapped_column(Text, default="draft")
    notes: Mapped[str | None] = mapped_column(Text)
    requested_samples: Mapped[list] = mapped_column(JSONB, default=list)
    requested_documents: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class SupplierOffer(Base):
    __tablename__ = "supplier_offers"
    id: Mapped[uuid.UUID] = _uuid()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))
    rfq_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rfqs.id"))
    version: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    currency: Mapped[str | None] = mapped_column(Text)
    incoterms: Mapped[str | None] = mapped_column(Text)
    moq: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    capacity: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    origin_country: Mapped[str | None] = mapped_column(Text)
    certifications: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    delivery_terms: Mapped[str | None] = mapped_column(Text)
    valid_until: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = _uuid()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"))
    channel: Mapped[str] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="open")
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = _uuid()
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    direction: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    classification: Mapped[str | None] = mapped_column(Text)
    provider_mode: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class Call(Base):
    __tablename__ = "calls"
    id: Mapped[uuid.UUID] = _uuid()
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"))
    direction: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(Text)
    provider_mode: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    transcript: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    consent_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    external_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[uuid.UUID] = _uuid()
    opportunity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("opportunities.id"))
    buyer_requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("buyer_requirements.id"))
    supplier_offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("supplier_offers.id"))
    score: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    confidence_cap: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    explanation: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created()


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[uuid.UUID] = _uuid()
    action_type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending")
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    subject_type: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Agreement(Base):
    __tablename__ = "agreements"
    id: Mapped[uuid.UUID] = _uuid()
    opportunity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("opportunities.id"), unique=True)
    status: Mapped[str] = mapped_column(Text, default="draft")
    terms: Mapped[dict] = mapped_column(JSONB, default=dict)
    evidence_note: Mapped[str | None] = mapped_column(Text)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("approvals.id"))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class CommissionRecord(Base):
    __tablename__ = "commission_records"
    id: Mapped[uuid.UUID] = _uuid()
    opportunity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("opportunities.id"))
    agreement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agreements.id"))
    terms_text: Mapped[str | None] = mapped_column(Text)
    rate_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    contracted_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    collected_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(Text, default="USD")
    collection_status: Mapped[str] = mapped_column(Text, default="none")
    invoice_reference: Mapped[str | None] = mapped_column(Text)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("approvals.id"))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[uuid.UUID] = _uuid()
    agent_name: Mapped[str] = mapped_column(Text)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"))
    status: Mapped[str] = mapped_column(Text)
    input: Mapped[dict] = mapped_column(JSONB, default=dict)
    output: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    created_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = _uuid()
    task_type: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(Text, unique=True)
    status: Mapped[str] = mapped_column(Text, default="queued")
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = _uuid()
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[uuid.UUID] = _uuid()
    provider: Mapped[str] = mapped_column(Text)
    signature_valid: Mapped[bool] = mapped_column(Boolean)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created()


class NotificationEvent(Base):
    __tablename__ = "notification_events"
    id: Mapped[uuid.UUID] = _uuid()
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


class ProviderUsage(Base):
    __tablename__ = "provider_usage"
    id: Mapped[uuid.UUID] = _uuid()
    provider: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(Text)
    operation: Mapped[str] = mapped_column(Text)
    units: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=1)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"))
    created_at: Mapped[datetime] = _created()


class CommercialAuditRun(Base):
    __tablename__ = "commercial_audit_runs"
    id: Mapped[uuid.UUID] = _uuid()
    environment: Mapped[str] = mapped_column(Text)
    database_name: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created()


class CommercialAuditCase(Base):
    __tablename__ = "commercial_audit_cases"
    id: Mapped[uuid.UUID] = _uuid()
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("commercial_audit_runs.id"))
    code: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class AlexOutcomeMetric(Base):
    __tablename__ = "alex_outcome_metrics"
    id: Mapped[uuid.UUID] = _uuid()
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"))
    call_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id"))
    actor_kind: Mapped[str] = mapped_column(Text)
    classification: Mapped[str | None] = mapped_column(Text)
    classification_method: Mapped[str | None] = mapped_column(Text)
    provider_mode: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text)
    human_decision: Mapped[str | None] = mapped_column(Text)
    intervention_seconds: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    comparable: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()


class BotImport(Base):
    __tablename__ = "bot_imports"
    id: Mapped[uuid.UUID] = _uuid()
    task_id: Mapped[str] = mapped_column(Text)
    agent_name: Mapped[str] = mapped_column(Text)
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    research_source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("research_sources.id"))
    company_identity: Mapped[str] = mapped_column(Text)
    company_type: Mapped[str] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    product_category: Mapped[str | None] = mapped_column(Text)
    source_urls: Mapped[list] = mapped_column(JSONB, default=list)
    verification_date: Mapped[date | None] = mapped_column(Date)
    claimed_verification_status: Mapped[str | None] = mapped_column(Text)
    stored_verification_status: Mapped[str | None] = mapped_column(Text)
    contact_eligibility: Mapped[str | None] = mapped_column(Text)
    source_document_reference: Mapped[str | None] = mapped_column(Text)
    import_status: Mapped[str] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    claim_evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()


class ServiceSheet(Base):
    __tablename__ = "service_sheets"
    id: Mapped[uuid.UUID] = _uuid()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    service_name: Mapped[str] = mapped_column(Text)
    duration_notes: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(Text, default="MYR")
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(Text, default="draft")
    allowed_sentence: Mapped[str] = mapped_column(Text)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("approvals.id"))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class JobCard(Base):
    __tablename__ = "job_cards"
    id: Mapped[uuid.UUID] = _uuid()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"))
    vehicle: Mapped[str] = mapped_column(Text)
    requested_service: Mapped[str] = mapped_column(Text)
    preferred_time: Mapped[str | None] = mapped_column(Text)
    photo_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="requested")
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class JobCardReply(Base):
    __tablename__ = "job_card_replies"
    id: Mapped[uuid.UUID] = _uuid()
    job_card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_cards.id"))
    body: Mapped[str] = mapped_column(Text)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_sheet_ids: Mapped[list] = mapped_column(JSONB, default=list)
    price_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = _created()


class OperatingSettings(Base):
    __tablename__ = "operating_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    outbound_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    jobs_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    budget_ceiling_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=25)
    budget_spent_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    updated_at: Mapped[datetime] = _updated()
