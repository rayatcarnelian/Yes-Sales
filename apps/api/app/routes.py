import hmac
import json
import uuid

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import admin_sessionmaker, system_session
from app.deps import get_current_user, get_db
from app.errors import DomainError
from app.models import Approval, BuyerRequirement, Company, Contact, ContactPermission, Rfq, User, UserCredential
from app.schemas import (
    AgreementIn,
    ApprovalIn,
    BudgetIn,
    CallMockIn,
    CallOutboundIn,
    CollectionIn,
    CommissionDraftIn,
    CompanyIn,
    ContactIn,
    ClassifyIn,
    DecisionIn,
    DraftIn,
    FollowUpIn,
    ExtractIn,
    HandoffIn,
    LoginIn,
    MatchIn,
    MessageIn,
    OfferIn,
    OpportunityIn,
    PauseIn,
    PermissionIn,
    ProductIn,
    QuoteRequestIn,
    RequirementIn,
    ResearchJobIn,
    RfqIn,
    SourceIn,
    TaskIn,
    ToolIn,
    TransitionIn,
    ServiceSheetIn,
    SalesPlayIn,
    JobCardIn,
    JobCardReplyIn,
    UserIn,
    VerificationIn,
)
from app.security import create_token, hash_password, verify_password, webhook_signature_valid
from app.services import alex, bot_import, commercial, commercial_audit, comms, crm, files, job_cards, orchestration, pipeline, research, sales_team
from app.services.common import public_settings, public_user, settings_row, spent_usd
from app.audit import audit

router = APIRouter()


@router.get("/health")
def health() -> dict:
    with admin_sessionmaker()() as session:
        session.execute(select(1))
    return {"status": "ok", "service": "yes-sales-api"}


@router.post("/auth/login")
def login(body: LoginIn) -> dict:
    with admin_sessionmaker()() as session:
        user = session.scalar(select(User).where(User.email == body.email.strip().lower()))
        credential = None if user is None else session.get(UserCredential, user.id)
        if user is None or credential is None or not user.is_active or not verify_password(body.password, credential.password_hash):
            raise DomainError(401, "invalid_login", "Email or password is incorrect.")
        audit(session, user, "auth.login", "user", user.id, {})
        session.commit()
        return {"access_token": create_token(user.id, user.email, user.role), "token_type": "bearer", "user": public_user(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return public_user(user)


@router.post("/users", status_code=201)
def create_user(body: UserIn, actor: User = Depends(get_current_user)) -> dict:
    if actor.role != "founder":
        raise DomainError(403, "founder_required", "Only the founder can create users.")
    if body.role not in {"founder", "operator", "agent"}:
        raise DomainError(422, "invalid_role", "Role must be founder, operator, or agent.")
    with admin_sessionmaker()() as session:
        email = body.email.strip().lower()
        if session.scalar(select(User).where(User.email == email)) is not None:
            raise DomainError(409, "duplicate_user", "A user with this email already exists.")
        user = User(email=email, full_name=body.full_name.strip(), role=body.role, is_active=True)
        session.add(user)
        session.flush()
        session.add(UserCredential(user_id=user.id, password_hash=hash_password(body.password)))
        audit(session, actor, "user.created", "user", user.id, {"role": user.role})
        session.commit()
        return public_user(user)


@router.post("/companies", status_code=201)
def create_company(body: CompanyIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return crm.public_company(crm.create_company(session, user, body))


@router.get("/companies")
def list_companies(
    q: str | None = None,
    country: str | None = None,
    role: str | None = None,
    verification: str | None = None,
    category: str | None = None,
    session: Session = Depends(get_db),
) -> dict:
    rows = crm.list_companies(session, q, country, role, verification, category)
    return {"companies": [crm.public_company(row) for row in rows]}


@router.get("/companies/{company_id}")
def get_company(company_id: uuid.UUID, session: Session = Depends(get_db)) -> dict:
    profile = crm.company_profile(session, company_id)
    company = session.get(Company, company_id)
    profile["next_supplier_stage"] = None if company is None else pipeline.next_stage(company, "supplier")
    profile["next_buyer_stage"] = None if company is None else pipeline.next_stage(company, "buyer")
    return profile


@router.post("/companies/{company_id}/contacts", status_code=201)
def create_contact(company_id: uuid.UUID, body: ContactIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    contact, permission = crm.create_contact(session, user, company_id, body)
    return crm.public_contact(contact, permission)


@router.post("/contacts/{contact_id}/permissions")
def update_permission(contact_id: uuid.UUID, body: PermissionIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    permission = crm.update_permission(session, user, contact_id, body)
    contact = session.get(Contact, contact_id)
    if contact is None:
        raise DomainError(404, "not_found", "Contact was not found.")
    return crm.public_contact(contact, permission)


@router.get("/contacts")
def search_contacts(q: str | None = None, session: Session = Depends(get_db)) -> dict:
    return {"contacts": [crm.public_contact(contact, permission) for contact, permission in crm.search_contacts(session, q)]}


@router.post("/buyer-requirements", status_code=201)
def create_requirement(body: RequirementIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return crm.public_requirement(crm.create_requirement(session, user, body))


@router.get("/buyer-requirements/{requirement_id}/compatible-suppliers")
def compatible_suppliers(requirement_id: uuid.UUID, session: Session = Depends(get_db)) -> dict:
    return commercial.compatible_suppliers(session, requirement_id)


@router.post("/companies/{company_id}/transitions")
def transition(company_id: uuid.UUID, body: TransitionIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return crm.public_company(pipeline.transition(session, user, company_id, body.side, body.to_stage))


@router.post("/companies/{company_id}/verification")
def verification(company_id: uuid.UUID, body: VerificationIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return crm.public_company(pipeline.set_verification(session, user, company_id, body.status))


@router.get("/pipeline/{side}")
def pipeline_board(side: str, session: Session = Depends(get_db)) -> dict:
    if side not in {"suppliers", "buyers"}:
        raise DomainError(404, "not_found", "Pipeline must be suppliers or buyers.")
    role = "supplier" if side == "suppliers" else "buyer"
    rows = session.scalars(select(Company).where(Company.role.in_([role, "both"])).order_by(Company.legal_name)).all()
    return {"side": side, "companies": [crm.public_company(row) for row in rows]}


@router.post("/integrations/grok-bot/imports")
async def grok_bot_ingest(request: Request, x_grok_bot_token: str | None = Header(default=None)) -> dict:
    configured = get_settings().grok_bot_token.strip()
    supplied = (x_grok_bot_token or "").strip()
    if not configured:
        raise DomainError(503, "grok_bot_not_configured", "Set GROK_BOT_TOKEN before a Grok bot can post here. This door stays closed until then.")
    if len(supplied) != len(configured) or not hmac.compare_digest(supplied, configured):
        raise DomainError(401, "invalid_token", "Grok bot token is invalid.")
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise DomainError(422, "invalid_payload", "Bot import body must be JSON.") from exc
    if not isinstance(payload, dict):
        raise DomainError(422, "invalid_payload", "Bot import body must be a JSON object.")
    rows = bot_import.rows_from_payload(payload)
    session = system_session()
    try:
        founder = session.scalar(select(User).where(User.role == "founder", User.is_active.is_(True)))
        if founder is None:
            raise DomainError(503, "founder_missing", "A founder user is required to store a bot import.")
        results = bot_import.import_records(session, founder, rows)
        session.commit()
        return {"results": results, "verification_trusted": False, "outreach_authorized": False, "grok_credit_control": "none"}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.post("/research/bot-imports")
async def import_bot_outputs(request: Request, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise DomainError(422, "import_required", "Attach a CSV or JSON file.")
        content = await upload.read()
        filename = getattr(upload, "filename", None) or "import.json"
        rows = bot_import.rows_from_upload(filename, content)
    else:
        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise DomainError(422, "invalid_payload", "Bot import body must be JSON.") from exc
        if not isinstance(payload, dict):
            raise DomainError(422, "invalid_payload", "Bot import body must be a JSON object.")
        rows = bot_import.rows_from_payload(payload)
    return {
        "results": bot_import.import_records(session, user, rows),
        "verification_trusted": False,
        "outreach_authorized": False,
    }


@router.get("/research/bot-imports")
def get_bot_imports(session: Session = Depends(get_db)) -> dict:
    return {"imports": [bot_import.public_import(row) for row in bot_import.list_imports(session)]}


@router.post("/research/sources", status_code=201)
def create_source(body: SourceIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return research.public_source(research.record_source(session, user, body))


@router.post("/research/extract")
def extract_source(body: ExtractIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return research.public_source(research.extract_source(session, user, body.source_id))


@router.post("/research/jobs", status_code=201)
def research_job(body: ResearchJobIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    if body.agent not in {"atlas", "orion", "bengal", "meridian", "hunter"}:
        raise DomainError(422, "unknown_agent", "Research agent is not recognized.")
    task, replayed = orchestration.enqueue(
        session,
        user,
        "research.search",
        body.idempotency_key,
        {
            "agent": body.agent,
            "query": body.query,
            "country": body.country,
            "category": body.category,
            "company_id": None if body.company_id is None else str(body.company_id),
        },
    )
    return {"task": orchestration.public_task(task), "idempotent_replay": replayed}


@router.post("/messages/send", status_code=201)
def send_message(body: MessageIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return comms.public_message(comms.send_message(session, user, body))


@router.get("/conversations")
def conversations(session: Session = Depends(get_db)) -> dict:
    return {"conversations": comms.list_conversations(session)}


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: uuid.UUID, session: Session = Depends(get_db)) -> dict:
    return {"messages": [comms.public_message(item) for item in comms.list_messages(session, conversation_id)]}


@router.get("/contacts/{contact_id}/context")
def contact_context(contact_id: uuid.UUID, session: Session = Depends(get_db)) -> dict:
    return alex.contact_context(session, contact_id)


@router.post("/alex/classify")
def classify_note(body: ClassifyIn, user: User = Depends(get_current_user)) -> dict:
    del user
    return alex.classify_message(body.body)


@router.post("/alex/drafts", status_code=201)
def create_draft(body: DraftIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return alex.draft_reply(session, user, body.contact_id, body.body, body.subject)


@router.post("/alex/follow-ups", status_code=201)
def schedule_followup(body: FollowUpIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return alex.schedule_followup(session, user, body.contact_id, body.body, body.subject, body.delay_hours, body.idempotency_key)


@router.post("/conversations/{conversation_id}/handoff")
def handoff(conversation_id: uuid.UUID, body: HandoffIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return comms.public_conversation(comms.handoff(session, user, conversation_id, body.note))


@router.post("/webhooks/email/inbound")
async def inbound_email(request: Request, x_yes_signature: str | None = Header(default=None)) -> dict:
    raw = await request.body()
    valid = webhook_signature_valid(raw, x_yes_signature)
    try:
        payload = json.loads(raw.decode() or "{}")
    except json.JSONDecodeError as exc:
        raise DomainError(422, "invalid_payload", "Webhook body must be JSON.") from exc
    session = system_session()
    try:
        result = comms.ingest_email(session, payload, valid)
        session.commit()
        return result
    except DomainError as exc:
        if exc.persist:
            session.commit()
        else:
            session.rollback()
        raise
    finally:
        session.close()


@router.post("/opportunities", status_code=201)
def create_opportunity(body: OpportunityIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return commercial.public_opportunity(commercial.create_opportunity(session, user, body))


@router.get("/opportunities")
def list_opportunities(session: Session = Depends(get_db)) -> dict:
    return {"opportunities": commercial.deal_board(session)}


@router.post("/products", status_code=201)
def create_product(body: ProductIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    product = commercial.create_product(session, user, body)
    return {"id": str(product.id), "name": product.name, "category": product.category, "company_id": str(product.company_id)}


@router.post("/products/{product_id}/documents", status_code=201)
async def upload_document(
    product_id: uuid.UUID,
    upload: UploadFile = File(...),
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    content = await upload.read()
    row = files.save_document(session, user, product_id, upload.filename or "document", upload.content_type or "", content)
    return {"id": str(row.id), "filename": row.filename, "content_type": row.content_type, "byte_size": row.byte_size}


@router.get("/documents/{document_id}")
def download_document(document_id: uuid.UUID, session: Session = Depends(get_db)):
    return files.open_document(session, document_id)


@router.post("/supplier-offers", status_code=201)
def create_offer(body: OfferIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return commercial.public_offer(commercial.create_offer(session, user, body))


@router.post("/rfqs", status_code=201)
def create_rfq(body: RfqIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    row = commercial.create_rfq(session, user, body)
    return {
        "id": str(row.id),
        "status": row.status,
        "buyer_requirement_id": str(row.buyer_requirement_id),
        "opportunity_id": None if row.opportunity_id is None else str(row.opportunity_id),
        "requested_samples": row.requested_samples,
        "requested_documents": row.requested_documents,
    }


@router.post("/rfqs/{rfq_id}/request-quotes")
def request_quotes(rfq_id: uuid.UUID, body: QuoteRequestIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    rfq = session.get(Rfq, rfq_id)
    if rfq is None:
        raise DomainError(404, "not_found", "RFQ was not found.")
    requirement = session.get(BuyerRequirement, rfq.buyer_requirement_id)
    sent = []
    skipped = []
    for supplier_id in body.supplier_company_ids:
        contact = session.scalar(
            select(Contact)
            .join(ContactPermission, ContactPermission.contact_id == Contact.id)
            .where(
                Contact.company_id == supplier_id,
                Contact.channel == "email",
                ContactPermission.allowed.is_(True),
                ContactPermission.opted_out.is_(False),
            )
        )
        if contact is None:
            skipped.append({"company_id": str(supplier_id), "reason": "no_eligible_email"})
            continue
        category = requirement.product_category if requirement is not None else "the requested product"
        draft = alex.draft_reply(
            session,
            user,
            contact.id,
            f"Please prepare a quotation for {category}. RFQ {rfq.id}.",
            f"RFQ {rfq.id}",
        )
        audit(
            session,
            user,
            "rfq.quote_requested",
            "rfq",
            rfq.id,
            {"company_id": str(supplier_id), "approval_id": draft["approval"]["id"], "sent": False},
        )
        sent.append(
            {
                "company_id": str(supplier_id),
                "approval_id": draft["approval"]["id"],
                "message_status": draft["message"]["status"],
                "provider_mode": draft["provider_mode"],
                "sent": False,
            }
        )
    return {"sent": False, "requests": sent, "skipped": skipped, "status": rfq.status, "live_email": False}


@router.get("/rfqs/{rfq_id}/compare")
def compare_rfq(rfq_id: uuid.UUID, session: Session = Depends(get_db)) -> dict:
    return commercial.compare_offers(session, rfq_id)


@router.post("/matches", status_code=201)
def create_match(body: MatchIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return commercial.public_match(commercial.create_match(session, user, body))


@router.post("/agreements", status_code=201)
def create_agreement(body: AgreementIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return commercial.public_agreement(commercial.create_agreement(session, user, body))


@router.post("/commission-records", status_code=201)
def create_commission(body: CommissionDraftIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return commercial.public_commission(commercial.create_commission_draft(session, user, body))


@router.post("/commission-records/{commission_id}/collections")
def collect_commission(commission_id: uuid.UUID, body: CollectionIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return commercial.public_commission(commercial.record_collection(session, user, commission_id, body))


@router.post("/approvals", status_code=201)
def create_approval(body: ApprovalIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return commercial.public_approval(commercial.request_approval(session, user, body))


@router.get("/approvals")
def list_approvals(status: str | None = None, session: Session = Depends(get_db)) -> dict:
    stmt = select(Approval).order_by(Approval.created_at.desc()).limit(200)
    if status:
        stmt = stmt.where(Approval.status == status)
    return {"approvals": [commercial.public_approval(row) for row in session.scalars(stmt)]}


@router.post("/approvals/{approval_id}/decide")
def decide(approval_id: uuid.UUID, body: DecisionIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return commercial.public_approval(commercial.decide_approval(session, user, approval_id, body.decision, body.note))


@router.post("/approvals/{approval_id}/execute")
def execute(approval_id: uuid.UUID, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return commercial.execute_approval(session, user, approval_id)


@router.post("/service-sheets", status_code=201)
def create_service_sheet(body: ServiceSheetIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return job_cards.public_sheet(job_cards.create_sheet(session, user, body))


@router.get("/service-sheets")
def list_service_sheets(company_id: uuid.UUID | None = None, session: Session = Depends(get_db)) -> dict:
    return {"service_sheets": [job_cards.public_sheet(row) for row in job_cards.list_sheets(session, company_id)]}


@router.post("/service-sheets/{sheet_id}/request-approval", status_code=201)
def approve_service_sheet(sheet_id: uuid.UUID, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return commercial.public_approval(job_cards.request_sheet_approval(session, user, sheet_id))


@router.post("/job-cards", status_code=201)
def file_job_card(body: JobCardIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    card, reply = job_cards.file_card(session, user, body)
    return {**job_cards.public_card(card, [reply]), "reply": job_cards.public_reply(reply)}


@router.get("/job-cards")
def list_job_cards(session: Session = Depends(get_db)) -> dict:
    return {"job_cards": [job_cards.public_card(card, replies) for card, replies in job_cards.list_cards(session)]}


@router.get("/job-cards/{card_id}")
def read_job_card(card_id: uuid.UUID, session: Session = Depends(get_db)) -> dict:
    card, replies = job_cards.get_card(session, card_id)
    return job_cards.public_card(card, replies)


@router.post("/job-cards/{card_id}/reply", status_code=201)
def reply_job_card(card_id: uuid.UUID, body: JobCardReplyIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    card, _ = job_cards.get_card(session, card_id)
    reply = job_cards.draft_reply(session, user, card, body.customer_message)
    return {**job_cards.public_card(card, [reply]), "reply": job_cards.public_reply(reply)}


@router.post("/job-cards/{card_id}/request-bay", status_code=201)
def request_job_bay(card_id: uuid.UUID, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return commercial.public_approval(job_cards.request_bay_confirmation(session, user, card_id))


@router.post("/calls/mock", status_code=201)
def mock_call(body: CallMockIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return orchestration.public_call(orchestration.create_mock_call(session, user, body))


@router.post("/calls/outbound", status_code=201)
def outbound_call(body: CallOutboundIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    call = orchestration.request_outbound_call(session, user, body)
    return {**orchestration.public_call(call), "placed": call.status == "initiated"}


@router.get("/calls")
def list_calls(session: Session = Depends(get_db)) -> dict:
    return {"calls": [orchestration.public_call(row) for row in orchestration.list_calls(session)]}


@router.post("/internal/calls", status_code=201)
async def gateway_call(request: Request, x_voice_token: str | None = Header(default=None)) -> dict:
    expected = get_settings().voice_gateway_token
    if not x_voice_token or not hmac.compare_digest(x_voice_token, expected):
        raise DomainError(401, "invalid_token", "Voice gateway token is invalid.")
    payload = await request.json()
    session = system_session()
    try:
        call = orchestration.log_gateway_call(session, payload)
        session.commit()
        return orchestration.public_call(call)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.post("/agents/invoke")
def invoke(body: ToolIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return orchestration.invoke_tool(session, user, body.agent, body.tool, body.payload)


@router.get("/sales-team")
def sales_team_roster(user: User = Depends(get_current_user)) -> dict:
    del user
    return sales_team.roster()


@router.post("/sales-team/run")
def sales_team_run(body: SalesPlayIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return sales_team.run_play(
        session,
        user,
        body.brief,
        body.country,
        body.excerpt,
        body.company_id,
        body.source_url,
    )


@router.get("/audit/commercial")
def commercial_audit_report(session: Session = Depends(get_db)) -> dict:
    return commercial_audit.public_report(session)


@router.get("/dashboard/kpis")
def kpis(session: Session = Depends(get_db)) -> dict:
    return orchestration.dashboard(session)


@router.get("/integrations")
def integrations(session: Session = Depends(get_db)) -> dict:
    del session
    return orchestration.integration_status()


@router.get("/settings")
def get_settings_view(session: Session = Depends(get_db)) -> dict:
    return public_settings(settings_row(session), spent_usd(session))


@router.post("/settings/outbound-pause")
def pause(body: PauseIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    row = orchestration.set_pause(session, user, body.paused)
    return public_settings(row, spent_usd(session))


@router.post("/settings/jobs-pause")
def jobs_pause(body: PauseIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    row = orchestration.set_jobs_pause(session, user, body.paused)
    return public_settings(row, spent_usd(session))


@router.post("/settings/budget")
def budget(body: BudgetIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    row = orchestration.set_budget(session, user, body.budget_ceiling_usd)
    return public_settings(row, spent_usd(session))


@router.post("/tasks", status_code=201)
def create_task(body: TaskIn, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    if body.task_type not in orchestration.HANDLERS:
        raise DomainError(422, "unknown_task", "Task type is not registered.")
    row, replayed = orchestration.enqueue(session, user, body.task_type, body.idempotency_key, body.payload, body.max_attempts, body.deadline_at)
    return {"task": orchestration.public_task(row), "idempotent_replay": replayed}


@router.post("/tasks/external", status_code=201)
async def external_task(request: Request, x_scheduler_token: str | None = Header(default=None)) -> dict:
    expected = get_settings().scheduler_token
    if not x_scheduler_token or not hmac.compare_digest(x_scheduler_token, expected):
        raise DomainError(401, "invalid_token", "Scheduler token is invalid.")
    payload = await request.json()
    session = system_session()
    try:
        row, replayed = orchestration.enqueue(
            session,
            None,
            str(payload["task_type"]),
            str(payload["idempotency_key"]),
            payload.get("payload") or {},
        )
        session.commit()
        return {"task": orchestration.public_task(row), "idempotent_replay": replayed}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.get("/tasks")
def list_tasks(status: str | None = None, session: Session = Depends(get_db)) -> dict:
    return {"tasks": [orchestration.public_task(row) for row in orchestration.list_tasks(session, status)]}


@router.post("/tasks/process")
def process_tasks(limit: int = 20, session: Session = Depends(get_db)) -> dict:
    del session
    return {"results": orchestration.process_due(limit)}


@router.post("/tasks/{task_id}/retry")
def retry(task_id: uuid.UUID, session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return orchestration.public_task(orchestration.retry_task(session, user, task_id))


@router.get("/notifications")
def notifications(session: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    from app.models import NotificationEvent

    rows = session.scalars(
        select(NotificationEvent)
        .where((NotificationEvent.user_id == user.id) | (NotificationEvent.user_id.is_(None)))
        .order_by(NotificationEvent.created_at.desc())
        .limit(100)
    )
    return {
        "notifications": [
            {"id": str(row.id), "kind": row.kind, "title": row.title, "body": row.body, "created_at": row.created_at.isoformat()}
            for row in rows
        ]
    }


@router.get("/audit-events")
def audit_events(session: Session = Depends(get_db)) -> dict:
    from app.models import AuditEvent

    rows = session.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(200))
    return {
        "events": [
            {
                "id": str(row.id),
                "actor_id": None if row.actor_id is None else str(row.actor_id),
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": None if row.entity_id is None else str(row.entity_id),
                "detail": row.detail,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }
