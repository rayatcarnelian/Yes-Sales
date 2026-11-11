import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    email: str
    password: str


class UserIn(BaseModel):
    email: str
    full_name: str
    password: str = Field(min_length=8)
    role: str = "operator"


class CompanyIn(BaseModel):
    legal_name: str = Field(min_length=2)
    country: str
    website: str | None = None
    role: str
    category: str | None = None
    summary: str | None = None
    is_test: bool = False


class ContactIn(BaseModel):
    full_name: str
    title: str | None = None
    channel: str
    value: str
    is_public_business: bool = True
    source_url: str | None = None
    allowed: bool = False
    authorization_basis: str = "unknown"
    consent_for_callback: bool = False
    daily_limit: int = Field(default=3, ge=0, le=50)


class PermissionIn(BaseModel):
    allowed: bool
    authorization_basis: str = "unknown"
    consent_for_callback: bool = False
    daily_limit: int = Field(default=3, ge=0, le=50)
    clear_opt_out: bool = False
    notes: str | None = None


class RequirementIn(BaseModel):
    company_id: uuid.UUID
    product_category: str
    specifications: dict = Field(default_factory=dict)
    desired_quantity: Decimal | None = None
    moq_acceptable: Decimal | None = None
    destination_country: str | None = None
    required_certifications: list[str] = Field(default_factory=list)
    lead_time_days: int | None = None
    delivery_terms: str | None = None
    currency: str | None = None
    incoterms: str | None = None
    notes: str | None = None


class OpportunityIn(BaseModel):
    buyer_company_id: uuid.UUID
    supplier_company_id: uuid.UUID | None = None
    buyer_requirement_id: uuid.UUID | None = None
    title: str
    pipeline_value: Decimal = Decimal("0")
    currency: str = "USD"


class TransitionIn(BaseModel):
    side: str
    to_stage: str


class VerificationIn(BaseModel):
    status: str


class ServiceSheetIn(BaseModel):
    company_id: uuid.UUID
    service_name: str = Field(min_length=2)
    duration_notes: str | None = None
    currency: str = "MYR"
    price: Decimal
    allowed_sentence: str = Field(min_length=2)


class JobCardIn(BaseModel):
    company_id: uuid.UUID
    vehicle: str = Field(min_length=2)
    requested_service: str = Field(min_length=2)
    preferred_time: str | None = None
    photo_note: str | None = None
    customer_message: str = Field(min_length=1)
    contact_id: uuid.UUID | None = None


class JobCardReplyIn(BaseModel):
    customer_message: str = Field(min_length=1)


class SourceIn(BaseModel):
    company_id: uuid.UUID
    source_url: str
    source_title: str | None = None
    retrieved_at: datetime | None = None
    excerpt: str = Field(min_length=1)
    provider: str = "manual"


class ExtractIn(BaseModel):
    source_id: uuid.UUID


class ResearchJobIn(BaseModel):
    agent: str
    query: str
    country: str | None = None
    category: str | None = None
    idempotency_key: str
    company_id: uuid.UUID | None = None


class MessageIn(BaseModel):
    contact_id: uuid.UUID
    body: str = Field(min_length=1)
    subject: str | None = None
    restricted: bool = False
    conversation_id: uuid.UUID | None = None


class InboundEmailIn(BaseModel):
    from_email: str
    body: str
    subject: str | None = None
    external_id: str | None = None
    conversation_id: uuid.UUID | None = None


class OfferIn(BaseModel):
    company_id: uuid.UUID
    product_id: uuid.UUID | None = None
    rfq_id: uuid.UUID | None = None
    unit_price: Decimal | None = None
    currency: str | None = None
    incoterms: str | None = None
    moq: Decimal | None = None
    capacity: Decimal | None = None
    lead_time_days: int | None = None
    origin_country: str | None = None
    certifications: list[str] = Field(default_factory=list)
    delivery_terms: str | None = None
    notes: str | None = None


class RfqIn(BaseModel):
    buyer_requirement_id: uuid.UUID
    opportunity_id: uuid.UUID | None = None
    notes: str | None = None
    requested_samples: list = Field(default_factory=list)
    requested_documents: list = Field(default_factory=list)


class MatchIn(BaseModel):
    opportunity_id: uuid.UUID
    buyer_requirement_id: uuid.UUID
    supplier_offer_id: uuid.UUID


class AgreementIn(BaseModel):
    opportunity_id: uuid.UUID
    terms: dict = Field(default_factory=dict)
    evidence_note: str | None = None


class CommissionDraftIn(BaseModel):
    opportunity_id: uuid.UUID
    agreement_id: uuid.UUID | None = None
    terms_text: str | None = None
    currency: str = "USD"


class CollectionIn(BaseModel):
    amount: Decimal
    invoice_reference: str | None = None


class ApprovalIn(BaseModel):
    action_type: str
    subject_type: str
    subject_id: uuid.UUID
    payload: dict = Field(default_factory=dict)
    notes: str | None = None


class DecisionIn(BaseModel):
    decision: str
    note: str = ""


class TaskIn(BaseModel):
    task_type: str
    idempotency_key: str
    payload: dict = Field(default_factory=dict)
    max_attempts: int = Field(default=5, ge=1, le=20)
    deadline_at: datetime | None = None


class PauseIn(BaseModel):
    paused: bool


class BudgetIn(BaseModel):
    budget_ceiling_usd: Decimal


class CallMockIn(BaseModel):
    company_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    mode: str
    transcript: str = "TEST mock voice transcript"
    request_callback: bool = False


class CallOutboundIn(BaseModel):
    contact_id: uuid.UUID
    mode: str


class ToolIn(BaseModel):
    agent: str
    tool: str
    payload: dict = Field(default_factory=dict)


class SalesPlayIn(BaseModel):
    brief: str = Field(min_length=1, max_length=4000)
    country: str | None = None
    excerpt: str = ""
    company_id: uuid.UUID | None = None
    source_url: str = ""


class ProductIn(BaseModel):
    company_id: uuid.UUID
    name: str
    category: str | None = None
    specifications: dict = Field(default_factory=dict)


class HandoffIn(BaseModel):
    note: str = ""


class ClassifyIn(BaseModel):
    body: str = Field(min_length=1)


class DraftIn(BaseModel):
    contact_id: uuid.UUID
    body: str = Field(min_length=1)
    subject: str | None = None


class FollowUpIn(BaseModel):
    contact_id: uuid.UUID
    body: str = Field(min_length=1)
    subject: str | None = None
    delay_hours: int = Field(default=24, ge=1, le=720)
    idempotency_key: str = Field(min_length=1)


class QuoteRequestIn(BaseModel):
    supplier_company_ids: list[uuid.UUID]
