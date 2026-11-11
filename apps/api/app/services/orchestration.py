import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit, audit_committed
from app.config import get_settings
from app.db import system_session
from app.domain import AGENT_COUNTRY, AGENT_TOOLS, assert_tool
from app.errors import DomainError
from app.models import (
    AgentRun,
    AuditEvent,
    Call,
    Company,
    Contact,
    ContactPermission,
    NotificationEvent,
    Task,
    User,
)
from app.serialize import money, stamp
from app.services.common import classify_text, now, record_usage, require, settings_row, spent_usd
from app.services.research import MockResearchProvider


def public_task(row: Task) -> dict:
    return {
        "id": str(row.id),
        "task_type": row.task_type,
        "idempotency_key": row.idempotency_key,
        "status": row.status,
        "payload": row.payload,
        "attempt": row.attempt,
        "max_attempts": row.max_attempts,
        "next_run_at": stamp(row.next_run_at),
        "deadline_at": stamp(row.deadline_at),
        "last_error": row.last_error,
        "result": row.result,
        "created_at": stamp(row.created_at),
    }


def enqueue(
    session: Session,
    actor: User | None,
    task_type: str,
    idempotency_key: str,
    payload: dict,
    max_attempts: int = 5,
    deadline_at=None,
    delay_seconds: int = 0,
) -> tuple[Task, bool]:
    existing = session.scalar(select(Task).where(Task.idempotency_key == idempotency_key))
    if existing is not None:
        return existing, True
    row = Task(
        task_type=task_type,
        idempotency_key=idempotency_key,
        payload=payload,
        max_attempts=max_attempts,
        deadline_at=deadline_at,
        next_run_at=now() + timedelta(seconds=max(0, delay_seconds)),
        status="queued",
    )
    session.add(row)
    session.flush()
    audit(session, actor, "task.enqueued", "task", row.id, {"task_type": task_type, "idempotency_key": idempotency_key})
    return row, False


def retry_task(session: Session, actor: User, task_id) -> Task:
    row = require(session, Task, task_id, "Task")
    if row.status == "succeeded":
        return row
    if row.status not in {"failed", "dead"}:
        raise DomainError(409, "not_retryable", "Only failed or dead tasks can be restarted.")
    row.status = "queued"
    row.next_run_at = now()
    row.last_error = None
    if row.attempt >= row.max_attempts:
        row.max_attempts = row.attempt + 1
    audit(session, actor, "task.restarted", "task", row.id, {})
    return row


def _actor(session: Session) -> User | None:
    return session.scalar(select(User).where(User.role == "founder", User.is_active.is_(True)))


def _handle_fail_once(session: Session, task: Task) -> dict:
    succeed_on = int(task.payload.get("succeed_on_attempt", 2))
    if task.attempt < succeed_on:
        raise RuntimeError("intentional failure")
    key = task.idempotency_key
    existing = list(session.scalars(select(AuditEvent).where(AuditEvent.action == "task.applied")))
    if any((item.detail or {}).get("idempotency_key") == key for item in existing):
        return {"applied": False}
    audit(session, None, "task.applied", "task", task.id, {"idempotency_key": key})
    return {"applied": True}


def _handle_spend(session: Session, task: Task) -> dict:
    cost = Decimal(str(task.payload.get("cost_usd", "0")))
    record_usage(session, "test", "live", "test.spend", cost)
    return {"charged": str(cost)}


def _handle_research(session: Session, task: Task) -> dict:
    agent = str(task.payload.get("agent", "orion"))
    country = task.payload.get("country") or AGENT_COUNTRY.get(agent)
    provider = MockResearchProvider()
    companies = provider.search(str(task.payload.get("query", "")), country)
    run = AgentRun(
        agent_name=agent,
        task_id=task.id,
        status="succeeded",
        input=task.payload,
        output={"companies": companies, "provider_mode": provider.mode},
        finished_at=now(),
    )
    session.add(run)
    session.flush()
    record_usage(session, provider.name, provider.mode, "research.search", 0, run.id)
    return {
        "companies": companies,
        "provider_mode": provider.mode,
        "note": "Mock research provider does not invent companies. Record a source with evidence before extraction.",
        "agent_run_id": str(run.id),
    }


def _handle_followup(session: Session, task: Task) -> dict:
    from app.services.alex import draft_reply
    from app.services.comms import _log_blocked, outbound_block_reason

    contact = require(session, Contact, uuid.UUID(str(task.payload["contact_id"])), "Contact")
    body = str(task.payload.get("body", "Following up on your sourcing request."))
    blocked = outbound_block_reason(session, contact, count_rate=False)
    if blocked in {"contact_not_eligible", "outbound_paused", "rate_limited"}:
        _log_blocked(None, contact, body, blocked, "Follow-up was not sent.")
        return {"sent": False, "blocked": blocked}
    actor = _actor(session)
    if actor is None:
        raise DomainError(409, "founder_missing", "A founder user is required to hold the follow-up draft.")
    try:
        drafted = draft_reply(session, actor, contact.id, body, task.payload.get("subject"))
    except DomainError as exc:
        if exc.code in {"contact_not_eligible", "outbound_paused", "rate_limited"}:
            return {"sent": False, "blocked": exc.code}
        raise
    return {
        "sent": False,
        "blocked": None,
        "awaiting_approval": True,
        "approval_id": drafted["approval"]["id"],
        "provider_mode": "mock",
        "message_id": drafted["message"]["id"],
    }


def _handle_callback(session: Session, task: Task) -> dict:
    contact_id = task.payload.get("contact_id")
    founder = _actor(session)
    session.add(
        NotificationEvent(
            user_id=None if founder is None else founder.id,
            kind="callback.requested",
            title="Human callback requested",
            body="A callback was requested. No outbound call was placed.",
        )
    )
    return {"call_placed": False, "contact_id": contact_id, "handoff": True}


HANDLERS = {
    "test.fail_once": _handle_fail_once,
    "test.spend": _handle_spend,
    "research.search": _handle_research,
    "email.followup": _handle_followup,
    "callback.request": _handle_callback,
}


def _process_one(task_id) -> dict:
    session = system_session()
    try:
        task = session.get(Task, task_id)
        if task is None:
            return {"id": str(task_id), "status": "missing"}
        if task.deadline_at is not None and task.deadline_at < datetime.now(UTC):
            task.status = "dead"
            task.last_error = "deadline passed"
            session.commit()
            return public_task(task)
        handler = HANDLERS.get(task.task_type)
        if handler is None:
            task.status = "dead"
            task.last_error = "no handler"
            session.commit()
            return public_task(task)
        task.attempt += 1
        task.status = "running"
        session.flush()
        try:
            result = handler(session, task)
        except Exception as exc:
            session.rollback()
            session.close()
            session = system_session()
            task = session.get(Task, task_id)
            if task is None:
                return {"id": str(task_id), "status": "missing"}
            task.attempt += 1
            task.last_error = str(exc)[:500]
            task.status = "dead" if task.attempt >= task.max_attempts else "failed"
            task.next_run_at = datetime.now(UTC) + timedelta(seconds=min(3600, 5 * (2**task.attempt)))
            audit(session, None, "task.failed", "task", task.id, {"error": task.last_error, "status": task.status})
            session.commit()
            return public_task(task)
        task.status = "succeeded"
        task.result = result
        task.last_error = None
        audit(session, None, "task.succeeded", "task", task.id, {"task_type": task.task_type})
        session.commit()
        return public_task(task)
    finally:
        session.close()


def process_due(limit: int = 20) -> list[dict]:
    session = system_session()
    try:
        if settings_row(session).jobs_paused:
            return []
        current = datetime.now(UTC)
        ids = list(
            session.scalars(
                select(Task.id)
                .where(
                    Task.status.in_(["queued", "failed"]),
                    Task.next_run_at <= current,
                    Task.attempt < Task.max_attempts,
                )
                .order_by(Task.next_run_at)
                .limit(limit)
            )
        )
    finally:
        session.close()
    return [_process_one(task_id) for task_id in ids]


def dashboard(session: Session) -> dict:
    from app.models import (
        AgentRun,
        Approval,
        CommissionRecord,
        Conversation,
        Match,
        Opportunity,
        ProviderUsage,
        Rfq,
        SupplierOffer,
    )

    verified_suppliers = session.scalar(
        select(func.count(Company.id)).where(
            Company.role.in_(["supplier", "both"]),
            Company.verification_status == "verified",
        )
    )
    qualified_buyers = session.scalar(
        select(func.count(Company.id)).where(
            Company.role.in_(["buyer", "both"]),
            Company.buyer_stage.in_(["qualification", "match", "rfq", "deal"]),
        )
    )
    active_conversations = session.scalar(
        select(func.count(Conversation.id)).where(Conversation.status.in_(["open", "waiting", "handoff"]))
    )
    rfq_count = session.scalar(select(func.count(Rfq.id)))
    quotations = session.scalar(select(func.count(SupplierOffer.id)))
    matched = session.scalar(select(func.count(func.distinct(Match.opportunity_id))))
    pending = session.scalar(select(func.count(Approval.id)).where(Approval.status == "pending"))
    pipeline_value = session.scalar(
        select(func.coalesce(func.sum(Opportunity.pipeline_value), 0)).where(Opportunity.status == "open")
    )
    contracted = session.scalar(select(func.coalesce(func.sum(CommissionRecord.contracted_amount), 0)))
    collected = session.scalar(select(func.coalesce(func.sum(CommissionRecord.collected_amount), 0)))
    agent_errors = session.scalar(select(func.count(AgentRun.id)).where(AgentRun.status == "failed"))
    api_costs = session.scalar(select(func.coalesce(func.sum(ProviderUsage.cost_usd), 0)))
    settings = get_settings()
    return {
        "verified_suppliers": int(verified_suppliers or 0),
        "qualified_buyers": int(qualified_buyers or 0),
        "active_conversations": int(active_conversations or 0),
        "rfqs": int(rfq_count or 0),
        "supplier_quotations": int(quotations or 0),
        "matched_opportunities": int(matched or 0),
        "deals_requiring_approval": int(pending or 0),
        "pipeline_value": money(Decimal(pipeline_value or 0)),
        "contracted_commissions": money(Decimal(contracted or 0)),
        "collected_commissions": money(Decimal(collected or 0)),
        "agent_errors": int(agent_errors or 0),
        "api_costs": f"{Decimal(api_costs or 0).quantize(Decimal('0.000001'))}",
        "integrations": integration_status(),
        "outbound_paused": settings_row(session).outbound_paused,
        "jobs_paused": settings_row(session).jobs_paused,
        "budget_spent_usd": f"{spent_usd(session).quantize(Decimal('0.000001'))}",
        "budget_ceiling_usd": money(settings_row(session).budget_ceiling_usd),
        "llm_mode_hint": settings.llm_mode,
    }


def integration_status() -> dict:
    settings = get_settings()
    if settings.email_live:
        email = "live"
    elif settings.outbound_enabled:
        email = "not_configured"
    else:
        email = "mock"
    return {
        "email": email,
        "voice": "configured_unverified" if settings.voice_mode == "live" else "mock",
        "live_call_verified": False,
        "llm": settings.llm_mode,
        "whatsapp": "not_configured",
        "grok_bot": "live" if settings.xai_api_key else "not_configured",
        "grok_connected": bool(settings.xai_api_key),
        "grok_bot_ingest": "ready" if settings.grok_bot_token.strip() else "not_configured",
        "grok_credit_control": "none",
        "database": "live",
        "outbound_enabled": settings.outbound_enabled,
    }


def set_pause(session: Session, actor: User, paused: bool):
    if actor.role != "founder":
        audit_committed(actor, "settings.denied", "operating_settings", None, {"reason": "founder_required"})
        raise DomainError(403, "founder_required", "Only the founder can change the global outbound pause.")
    row = settings_row(session)
    row.outbound_paused = paused
    audit(session, actor, "settings.pause_changed", "operating_settings", None, {"paused": paused})
    return row


def set_jobs_pause(session: Session, actor: User, paused: bool):
    if actor.role != "founder":
        audit_committed(actor, "settings.denied", "operating_settings", None, {"reason": "founder_required", "setting": "jobs_paused"})
        raise DomainError(403, "founder_required", "Only the founder can pause app jobs.")
    row = settings_row(session)
    row.jobs_paused = paused
    audit(
        session,
        actor,
        "settings.jobs_pause_changed",
        "operating_settings",
        None,
        {"jobs_paused": paused, "grok_credit_control": "none"},
    )
    return row


def set_budget(session: Session, actor: User, ceiling: Decimal):
    if actor.role != "founder":
        raise DomainError(403, "founder_required", "Only the founder can change the budget ceiling.")
    if ceiling < 0:
        raise DomainError(422, "invalid_budget", "Budget ceiling cannot be negative.")
    row = settings_row(session)
    row.budget_ceiling_usd = ceiling
    audit(session, actor, "settings.budget_changed", "operating_settings", None, {"budget_ceiling_usd": str(ceiling)})
    return row


def create_mock_call(session: Session, actor: User, data) -> Call:
    if data.mode not in {"buyer", "supplier"}:
        raise DomainError(422, "invalid_mode", "Call mode must be buyer or supplier.")
    if data.contact_id is not None:
        require(session, Contact, data.contact_id, "Contact")
    if data.company_id is not None:
        require(session, Company, data.company_id, "Company")
    call = Call(
        company_id=data.company_id,
        contact_id=data.contact_id,
        direction="inbound",
        mode=data.mode,
        provider_mode="mock",
        status="completed",
        transcript=data.transcript,
        summary=(
            "Mock voice session. No carrier was contacted and no recording was made. "
            f"Transcript classification: {classify_text(data.transcript)}. "
            "No price, commission, or contract was agreed."
        ),
        consent_checked=False,
    )
    session.add(call)
    session.flush()
    if data.request_callback:
        enqueue(session, actor, "callback.request", f"callback-call-{call.id}", {"contact_id": None if data.contact_id is None else str(data.contact_id), "call_id": str(call.id)})
    audit(session, actor, "call.mock_completed", "call", call.id, {"provider_mode": "mock"})
    return call


def request_outbound_call(session: Session, actor: User, data) -> Call:
    contact = require(session, Contact, data.contact_id, "Contact")
    permission = session.scalar(select(ContactPermission).where(ContactPermission.contact_id == contact.id))
    if permission is None or not permission.consent_for_callback or permission.opted_out:
        audit_committed(actor, "call.blocked", "contact", contact.id, {"reason": "consent_required"})
        raise DomainError(403, "consent_required", "Outbound callbacks require stored consent and no opt-out.")
    if settings_row(session).outbound_paused:
        audit_committed(actor, "call.blocked", "contact", contact.id, {"reason": "outbound_paused"})
        raise DomainError(409, "outbound_paused", "Global outbound pause blocks phone callbacks.")
    settings = get_settings()
    if settings_row(session).budget_ceiling_usd <= spent_usd(session):
        audit_committed(actor, "call.blocked", "contact", contact.id, {"reason": "budget_exceeded"})
        raise DomainError(409, "budget_exceeded", "Provider budget ceiling is already reached. No call was placed.")
    if settings.voice_mode != "live":
        summary = "Twilio or xAI realtime credentials are not configured. No call was placed."
        status = "blocked"
        action = "call.not_configured"
    else:
        summary = "Consent is stored, but no carrier call was placed. Live calling is not verified until a real test call succeeds."
        status = "authorized"
        action = "call.authorized"
    call = Call(
        company_id=contact.company_id,
        contact_id=contact.id,
        direction="outbound",
        mode=data.mode,
        provider_mode="not_configured",
        status=status,
        summary=summary,
        consent_checked=True,
    )
    session.add(call)
    session.flush()
    audit(session, actor, action, "call", call.id, {"provider_mode": "not_configured", "placed": False})
    return call


def public_call(row: Call) -> dict:
    return {
        "id": str(row.id),
        "company_id": None if row.company_id is None else str(row.company_id),
        "contact_id": None if row.contact_id is None else str(row.contact_id),
        "direction": row.direction,
        "mode": row.mode,
        "provider_mode": row.provider_mode,
        "status": row.status,
        "transcript": row.transcript,
        "summary": row.summary,
        "consent_checked": row.consent_checked,
        "created_at": stamp(row.created_at),
    }


def log_gateway_call(session: Session, payload: dict) -> Call:
    mode = payload.get("provider_mode", "mock")
    if mode not in {"live", "mock", "not_configured"}:
        mode = "mock"
    if mode == "live" and not (payload.get("model_socket_opened") and get_settings().voice_mode == "live"):
        mode = "not_configured"
    call = Call(
        company_id=None if not payload.get("company_id") else uuid.UUID(str(payload["company_id"])),
        contact_id=None if not payload.get("contact_id") else uuid.UUID(str(payload["contact_id"])),
        direction=payload.get("direction", "inbound"),
        mode=payload.get("mode", "buyer"),
        provider_mode=mode,
        status=payload.get("status", "completed"),
        transcript=payload.get("transcript"),
        summary=payload.get("summary"),
        consent_checked=bool(payload.get("consent_checked", False)),
        external_id=payload.get("external_id"),
    )
    session.add(call)
    session.flush()
    audit(session, None, "call.logged", "call", call.id, {"provider_mode": mode, "source": "voice_gateway"})
    return call


def invoke_tool(session: Session, actor: User, agent: str, tool: str, payload: dict) -> dict:
    try:
        assert_tool(agent, tool)
    except DomainError:
        audit_committed(actor, "tool.denied", "agent", None, {"agent": agent, "tool": tool})
        raise
    try:
        output = _dispatch_tool(session, actor, agent, tool, payload)
    except DomainError as exc:
        _failed_run(agent, tool, payload, exc.message)
        raise
    run = AgentRun(
        agent_name=agent,
        status="succeeded",
        input={"tool": tool, "payload": payload},
        output=output,
        finished_at=now(),
    )
    session.add(run)
    session.flush()
    audit(session, actor, "agent.invoked", "agent_run", run.id, {"agent": agent, "tool": tool})
    return {"agent_run_id": str(run.id), "output": output, "allowed_tools": sorted(AGENT_TOOLS[agent])}


def _failed_run(agent: str, tool: str, payload: dict, error: str) -> None:
    from app.db import admin_sessionmaker

    with admin_sessionmaker()() as session:
        session.add(
            AgentRun(
                agent_name=agent,
                status="failed",
                input={"tool": tool, "payload": payload},
                error=error,
                finished_at=now(),
            )
        )
        session.commit()


def _dispatch_tool(session: Session, actor: User, agent: str, tool: str, payload: dict) -> dict:
    if tool == "read_kpis":
        return dashboard(session)
    if tool == "enqueue_task":
        row, replayed = enqueue(
            session,
            actor,
            str(payload["task_type"]),
            str(payload["idempotency_key"]),
            payload.get("task_payload") or {},
        )
        return {"task": public_task(row), "idempotent_replay": replayed}
    if tool == "record_source":
        from app.schemas import SourceIn
        from app.services.research import public_source, record_source

        source = record_source(session, actor, SourceIn(**payload))
        return public_source(source)
    if tool == "extract_source":
        from app.services.research import extract_source, public_source

        source = extract_source(session, actor, uuid.UUID(str(payload["source_id"])))
        return public_source(source)
    if tool == "validate_extraction":
        from app.services.research import guard_fields

        guard_fields(str(payload.get("excerpt", "")), payload.get("fields") or {})
        return {"valid": True}
    if tool == "audit":
        audit(session, actor, str(payload.get("action", "agent.audit")), "agent", None, {"agent": agent})
        return {"logged": True}
    if tool == "classify_message":
        from app.services.alex import classify_message

        return classify_message(str(payload.get("body", "")))
    if tool in {"send_message", "draft_reply"}:
        from app.services.alex import draft_reply

        return draft_reply(
            session,
            actor,
            uuid.UUID(str(payload["contact_id"])),
            str(payload.get("body", "")),
            payload.get("subject"),
        )
    if tool == "schedule_followup":
        from app.services.alex import schedule_followup

        return schedule_followup(
            session,
            actor,
            uuid.UUID(str(payload["contact_id"])),
            str(payload.get("body", "Following up on your sourcing request.")),
            payload.get("subject"),
            int(payload.get("delay_hours", 24)),
            str(payload["idempotency_key"]),
        )
    if tool == "request_callback":
        contact = require(session, Contact, uuid.UUID(str(payload["contact_id"])), "Contact")
        permission = session.scalar(select(ContactPermission).where(ContactPermission.contact_id == contact.id))
        if permission is None or not permission.consent_for_callback:
            raise DomainError(403, "consent_required", "Callback requests still require stored consent before any dial.")
        row, _replayed = enqueue(
            session,
            actor,
            "callback.request",
            str(payload.get("idempotency_key") or f"callback-{contact.id}"),
            {"contact_id": str(contact.id)},
        )
        return {"task_id": str(row.id), "call_placed": False}
    if tool == "record_offer":
        from app.schemas import OfferIn
        from app.services.commercial import create_offer, public_offer

        return public_offer(create_offer(session, actor, OfferIn(**payload)))
    if tool == "record_commission_draft":
        from app.schemas import CommissionDraftIn
        from app.services.commercial import create_commission_draft, public_commission

        return public_commission(create_commission_draft(session, actor, CommissionDraftIn(**payload)))
    raise DomainError(404, "unknown_tool", "Tool is not implemented.")


def list_tasks(session: Session, status: str | None) -> list[Task]:
    stmt = select(Task).order_by(Task.created_at.desc()).limit(200)
    if status:
        stmt = stmt.where(Task.status == status)
    return list(session.scalars(stmt))


def list_calls(session: Session) -> list[Call]:
    return list(session.scalars(select(Call).order_by(Call.created_at.desc()).limit(100)))
