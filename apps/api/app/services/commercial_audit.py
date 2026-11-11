import json
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings, repo_root
from app.db import system_session
from app.domain import BUYER_STAGES, SUPPLIER_STAGES
from app.models import CommercialAuditCase, CommercialAuditRun
from app.security import sign_webhook

CASE_ORDER = [
    "supplier_import",
    "identifier_mismatch",
    "superseded_research",
    "buyer_import",
    "buyer_requirement",
    "compatible_supplier",
    "potential_match",
    "rfq",
    "quotation",
    "founder_approval",
    "inbound_email",
    "phone_call",
    "handoff",
    "opt_out_pause",
    "budget_limit",
]


def _now() -> datetime:
    return datetime.now(UTC)


def _stamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _record(cases: list[dict], code: str, title: str, status: str, evidence: dict, failure_reason: str | None) -> None:
    if status == "passed":
        failure_reason = None
    elif not failure_reason:
        failure_reason = "This case was not passed."
    cases.append(
        {
            "code": code,
            "title": title,
            "status": status,
            "executed_at": _now().isoformat(),
            "evidence": evidence,
            "failure_reason": failure_reason,
        }
    )


def _walk(client, headers: dict, company_id: str, side: str, target: str) -> None:
    stages = SUPPLIER_STAGES if side == "supplier" else BUYER_STAGES
    field = "supplier_stage" if side == "supplier" else "buyer_stage"
    stage = client.get(f"/companies/{company_id}", headers=headers).json()["company"][field]
    while stage != target:
        nxt = stages[stages.index(stage) + 1]
        response = client.post(
            f"/companies/{company_id}/transitions",
            headers=headers,
            json={"side": side, "to_stage": nxt},
        )
        if response.status_code != 200:
            raise RuntimeError(response.text)
        stage = nxt


def _auth(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    if response.status_code != 200:
        raise RuntimeError(response.text)
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _source(client, headers, company_id: str, url: str, excerpt: str, retrieved_at: str | None = None):
    payload = {"company_id": company_id, "source_url": url, "excerpt": excerpt, "provider": "manual"}
    if retrieved_at:
        payload["retrieved_at"] = retrieved_at
    return client.post("/research/sources", headers=headers, json=payload)


def execute_commercial_audit(client, password: str = "test-password", write_report: bool = False) -> dict:
    started = _now()
    headers = _auth(client, "founder@yes-sales.test", password)
    operator = _auth(client, "operator@yes-sales.test", password)
    cases: list[dict] = []
    try:
        _run_cases(client, headers, operator, cases)
    finally:
        client.post("/settings/outbound-pause", headers=headers, json={"paused": False})
        client.post("/settings/budget", headers=headers, json={"budget_ceiling_usd": "25"})
    finished = _now()
    report = _assemble(cases, started, finished)
    _persist(report)
    if write_report:
        path = repo_root() / "audit" / "commercial-audit.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["evidence_file"] = str(path)
    return report


def _run_cases(client, headers: dict, operator: dict, cases: list[dict]) -> None:
    supplier = client.post(
        "/companies",
        headers=headers,
        json={"legal_name": "TEST Audit Mill", "country": "BD", "role": "supplier", "category": "Knitwear", "is_test": True},
    )
    if supplier.status_code != 201:
        _record(cases, "supplier_import", "Import a valid supplier record", "failed", {"body": supplier.text}, supplier.text)
        return
    supplier_id = supplier.json()["id"]
    source = _source(
        client,
        headers,
        supplier_id,
        "https://test-audit-mill.example/about",
        "Company: TEST Audit Mill\nCountry: BD\nCategory: Knitwear",
        "2026-11-01T00:00:00+00:00",
    )
    imported = source.status_code == 201
    if imported:
        extracted = client.post("/research/extract", headers=headers, json={"source_id": source.json()["id"]})
        imported = extracted.status_code == 200 and extracted.json().get("evidence_fields", {}).get("company") == "TEST Audit Mill"
    contact = client.post(
        f"/companies/{supplier_id}/contacts",
        headers=headers,
        json={"full_name": "Mill Desk", "channel": "email", "value": "mill@audit.test", "allowed": True, "authorization_basis": "explicit_consent"},
    )
    if imported and contact.status_code == 201:
        _walk(client, headers, supplier_id, "supplier", "qualification")
        verified = client.post(f"/companies/{supplier_id}/verification", headers=headers, json={"status": "verified"})
        imported = verified.status_code == 200 and verified.json()["verification_status"] == "verified"
    _record(
        cases,
        "supplier_import",
        "Import a valid supplier record",
        "passed" if imported else "failed",
        {"company_id": supplier_id, "method": "manual_source", "provider_mode": "live", "external_registry_contacted": False},
        None if imported else "Supplier record was not stored with a matching source and verification.",
    )

    mismatch = _source(
        client,
        headers,
        supplier_id,
        "https://test-audit-mill.example/wrong",
        "Company: TEST Other Mill\nCountry: BD",
    )
    rejected = mismatch.status_code == 422 and mismatch.json()["error"]["code"] == "identifier_mismatch"
    _record(
        cases,
        "identifier_mismatch",
        "Reject an incorrectly matched company identifier",
        "passed" if rejected else "failed",
        {"status_code": mismatch.status_code, "accepted": mismatch.status_code == 201},
        None if rejected else "A source naming a different company was not rejected.",
    )

    older = _source(
        client,
        headers,
        supplier_id,
        "https://test-audit-mill.example/about",
        "Company: TEST Audit Mill\nCountry: BD",
        "2026-10-01T00:00:00+00:00",
    )
    superseded = older.status_code == 409 and older.json()["error"]["code"] == "superseded_source"
    _record(
        cases,
        "superseded_research",
        "Reject superseded research data",
        "passed" if superseded else "failed",
        {"status_code": older.status_code, "accepted": older.status_code == 201},
        None if superseded else "An older retrieval for the same URL was not rejected.",
    )

    buyer = client.post(
        "/companies",
        headers=headers,
        json={"legal_name": "TEST Audit Buyer", "country": "DE", "role": "buyer", "category": "Knitwear", "is_test": True},
    )
    buyer_id = buyer.json()["id"] if buyer.status_code == 201 else None
    buyer_source = None if buyer_id is None else _source(
        client,
        headers,
        buyer_id,
        "https://test-audit-buyer.example/about",
        "Company: TEST Audit Buyer\nCountry: DE\nCategory: Knitwear",
    )
    buyer_ok = False
    if buyer_id and buyer_source is not None and buyer_source.status_code == 201:
        contact_response = client.post(
            f"/companies/{buyer_id}/contacts",
            headers=headers,
            json={"full_name": "Buyer Desk", "channel": "email", "value": "buyer@audit.test", "allowed": True, "authorization_basis": "explicit_consent"},
        )
        if contact_response.status_code == 201:
            _walk(client, headers, buyer_id, "buyer", "qualification")
            verified_buyer = client.post(f"/companies/{buyer_id}/verification", headers=headers, json={"status": "verified"})
            buyer_ok = verified_buyer.status_code == 200 and verified_buyer.json()["verification_status"] == "verified"
    _record(
        cases,
        "buyer_import",
        "Import a verified buyer prospect",
        "passed" if buyer_ok else "failed",
        {"company_id": buyer_id, "verification_status": "verified" if buyer_ok else "not_verified"},
        None if buyer_ok else "Buyer was not stored and verified from a matching source.",
    )

    requirement = client.post(
        "/buyer-requirements",
        headers=headers,
        json={"company_id": buyer_id, "product_category": "Knitwear", "desired_quantity": "1000", "destination_country": "DE", "currency": "USD"},
    ) if buyer_id else None
    requirement_id = None
    requirement_ok = requirement is not None and requirement.status_code == 201
    if requirement is not None and requirement_ok:
        requirement_id = requirement.json()["id"]
    _record(
        cases,
        "buyer_requirement",
        "Create a buyer requirement",
        "passed" if requirement_ok else "failed",
        {"requirement_id": requirement_id},
        None if requirement_ok else "Buyer requirement was not stored.",
    )

    product = client.post(
        "/products",
        headers=headers,
        json={"company_id": supplier_id, "name": "TEST Jersey", "category": "Knitwear"},
    )
    found = client.get(f"/buyer-requirements/{requirement_id}/compatible-suppliers", headers=headers) if requirement_id else None
    found_ids = [] if found is None or found.status_code != 200 else [item["company_id"] for item in found.json()["suppliers"]]
    compatible = product.status_code == 201 and supplier_id in found_ids
    _record(
        cases,
        "compatible_supplier",
        "Find a product-compatible supplier",
        "passed" if compatible else "failed",
        {"supplier_ids": found_ids, "product_status": product.status_code},
        None if compatible else "No stored product category matched the requirement.",
    )

    opportunity = client.post(
        "/opportunities",
        headers=headers,
        json={
            "buyer_company_id": buyer_id,
            "supplier_company_id": supplier_id,
            "buyer_requirement_id": requirement_id,
            "title": "TEST Audit knit",
            "pipeline_value": "1000",
            "currency": "USD",
        },
    ) if buyer_id and requirement_id else None
    opportunity_id = opportunity.json()["id"] if opportunity is not None and opportunity.status_code == 201 else None
    rfq = client.post(
        "/rfqs",
        headers=headers,
        json={"buyer_requirement_id": requirement_id, "opportunity_id": opportunity_id, "requested_documents": ["spec"]},
    ) if requirement_id and opportunity_id else None
    rfq_id = None
    rfq_ok = rfq is not None and rfq.status_code == 201
    if rfq is not None and rfq_ok:
        rfq_id = rfq.json()["id"]
    _record(
        cases,
        "rfq",
        "Create an RFQ",
        "passed" if rfq_ok else "failed",
        {"rfq_id": rfq_id},
        None if rfq_ok else "RFQ was not stored.",
    )

    offer = client.post(
        "/supplier-offers",
        headers=headers,
        json={
            "company_id": supplier_id,
            "product_id": product.json()["id"] if product.status_code == 201 else None,
            "rfq_id": rfq_id,
            "unit_price": "4.50",
            "currency": "USD",
            "origin_country": "BD",
            "incoterms": "FOB",
        },
    )
    quote_ok = offer.status_code == 201 and offer.json()["version"] == 1
    _record(
        cases,
        "quotation",
        "Record a supplier quotation",
        "passed" if quote_ok else "failed",
        {"offer_id": None if not quote_ok else offer.json()["id"], "version": None if not quote_ok else offer.json()["version"]},
        None if quote_ok else "Quotation was not stored.",
    )

    match = client.post(
        "/matches",
        headers=headers,
        json={
            "opportunity_id": opportunity_id,
            "buyer_requirement_id": requirement_id,
            "supplier_offer_id": offer.json()["id"] if quote_ok else None,
        },
    ) if opportunity_id and requirement_id and quote_ok else None
    explanation = {} if match is None or match.status_code != 201 else match.json()["explanation"]
    matched = explanation.get("matched", []) if isinstance(explanation, dict) else []
    match_id = None
    match_ok = match is not None and match.status_code == 201 and "landed_cost" not in explanation and "category" in matched
    if match is not None and match_ok:
        match_id = match.json()["id"]
    _record(
        cases,
        "potential_match",
        "Generate a potential match",
        "passed" if match_ok else "failed",
        {
            "match_id": match_id,
            "matched": explanation.get("matched"),
            "missing": explanation.get("missing"),
            "landed_cost_present": "landed_cost" in explanation,
            "sequence_note": "The quotation is stored before the match because a match requires a stored offer.",
        },
        None if match_ok else "Match was not stored from the requirement and quotation.",
    )

    agreement = client.post(
        "/agreements",
        headers=headers,
        json={"opportunity_id": opportunity_id, "terms": {"note": "TEST unsigned"}, "evidence_note": "TEST draft only"},
    ) if opportunity_id else None
    agreement_id = agreement.json()["id"] if agreement is not None and agreement.status_code == 201 else None
    approval = client.post(
        "/approvals",
        headers=operator,
        json={"action_type": "sign_agreement", "subject_type": "agreement", "subject_id": agreement_id, "notes": "TEST route only"},
    ) if agreement_id else None
    denied = client.post(
        f"/approvals/{approval.json()['id']}/decide",
        headers=operator,
        json={"decision": "approved", "note": "no"},
    ) if approval is not None and approval.status_code == 201 else None
    routed = (
        approval is not None
        and approval.status_code == 201
        and approval.json()["status"] == "pending"
        and denied is not None
        and denied.status_code == 403
    )
    _record(
        cases,
        "founder_approval",
        "Route a binding decision for founder approval",
        "passed" if routed else "failed",
        {
            "approval_id": None if approval is None or approval.status_code != 201 else approval.json()["id"],
            "status": None if approval is None or approval.status_code != 201 else approval.json()["status"],
            "executed": False,
            "operator_decide_status": None if denied is None else denied.status_code,
        },
        None if routed else "Binding decision was not left pending for the founder.",
    )

    payload = json.dumps(
        {"from_email": "buyer@audit.test", "body": "TEST controlled inbound note", "subject": "TEST", "provider_mode": "mock"}
    ).encode()
    inbound = client.post(
        "/webhooks/email/inbound",
        content=payload,
        headers={"X-Yes-Signature": sign_webhook(payload), "Content-Type": "application/json"},
    )
    stored = inbound.status_code == 200 and inbound.json()["message"]["provider_mode"] == "mock"
    _record(
        cases,
        "inbound_email",
        "Process a controlled inbound email",
        "mocked" if stored else "failed",
        {
            "message_id": None if inbound.status_code != 200 else inbound.json()["message"]["id"],
            "conversation_id": None if inbound.status_code != 200 else inbound.json()["conversation"]["id"],
            "provider_mode": "mock",
            "mailbox_contacted": False,
        },
        None if stored else "Inbound webhook did not store the message.",
    )
    if stored:
        cases[-1]["failure_reason"] = "The webhook stored the message, but provider_mode is mock. No mailbox was contacted, so this is not a pass."

    conversation_id = inbound.json()["conversation"]["id"] if stored else None
    handoff = client.post(
        f"/conversations/{conversation_id}/handoff",
        headers=headers,
        json={"note": "TEST human handoff"},
    ) if conversation_id else None
    handed = handoff is not None and handoff.status_code == 200 and handoff.json()["status"] == "handoff"
    _record(
        cases,
        "handoff",
        "Record communications and handoffs",
        "passed" if handed and stored else "failed",
        {"conversation_id": conversation_id, "status": None if not handed else "handoff", "call_placed": False},
        None if handed and stored else "Conversation was not marked for human handoff.",
    )

    opt_contact = client.post(
        f"/companies/{buyer_id}/contacts",
        headers=headers,
        json={"full_name": "Opt Out", "channel": "email", "value": "optout@audit.test", "allowed": True, "authorization_basis": "explicit_consent"},
    ) if buyer_id else None
    opt_payload = json.dumps({"from_email": "optout@audit.test", "body": "Please STOP", "provider_mode": "mock"}).encode()
    opt_in = client.post(
        "/webhooks/email/inbound",
        content=opt_payload,
        headers={"X-Yes-Signature": sign_webhook(opt_payload), "Content-Type": "application/json"},
    ) if opt_contact is not None and opt_contact.status_code == 201 else None
    blocked_send = client.post(
        "/messages/send",
        headers=headers,
        json={"contact_id": opt_contact.json()["id"], "body": "TEST follow-up"},
    ) if opt_contact is not None and opt_contact.status_code == 201 else None
    pause_contact = client.post(
        f"/companies/{buyer_id}/contacts",
        headers=headers,
        json={"full_name": "Paused", "channel": "email", "value": "paused@audit.test", "allowed": True, "authorization_basis": "explicit_consent"},
    ) if buyer_id else None
    client.post("/settings/outbound-pause", headers=headers, json={"paused": True})
    paused = client.post(
        "/messages/send",
        headers=headers,
        json={"contact_id": pause_contact.json()["id"], "body": "TEST during pause"},
    ) if pause_contact is not None and pause_contact.status_code == 201 else None
    client.post("/settings/outbound-pause", headers=headers, json={"paused": False})
    controls = (
        opt_in is not None
        and opt_in.status_code == 200
        and opt_in.json()["classification"] == "opt_out"
        and blocked_send is not None
        and blocked_send.status_code == 403
        and paused is not None
        and paused.status_code == 409
    )
    _record(
        cases,
        "opt_out_pause",
        "Enforce opt-outs and the global pause",
        "passed" if controls else "failed",
        {
            "opt_out_status": None if opt_in is None else opt_in.status_code,
            "follow_up_status": None if blocked_send is None else blocked_send.status_code,
            "paused_status": None if paused is None else paused.status_code,
        },
        None if controls else "Opt-out or global pause did not block the send.",
    )

    settings = get_settings()
    if settings.voice_mode == "live":
        _record(
            cases,
            "phone_call",
            "Process a controlled test phone call",
            "skipped",
            {"credentials_present": True, "placed": False, "live_call_verified": False},
            "Credentials are present, but this run does not place a carrier call. Live calling is not verified.",
        )
    else:
        _record(
            cases,
            "phone_call",
            "Process a controlled test phone call",
            "skipped",
            {"credentials_present": False, "placed": False, "live_call_verified": False},
            "Twilio or xAI credentials are absent. No call was placed, and the mock session was not counted as a pass.",
        )

    client.post("/settings/budget", headers=headers, json={"budget_ceiling_usd": "1"})
    client.post(
        "/tasks",
        headers=headers,
        json={"task_type": "test.spend", "idempotency_key": "audit-budget", "payload": {"cost_usd": "2"}, "max_attempts": 1},
    )
    processed = client.post("/tasks/process", headers=headers)
    result = processed.json()["results"][0] if processed.status_code == 200 and processed.json()["results"] else {}
    budget_rejected = result.get("status") in {"failed", "dead"} and "budget" in str(result.get("last_error", ""))
    _record(
        cases,
        "budget_limit",
        "Reject jobs that exceed approved budget limits",
        "passed" if budget_rejected else "failed",
        {"task_status": result.get("status"), "last_error": result.get("last_error"), "ceiling_usd": "1", "attempted_cost_usd": "2"},
        None if budget_rejected else "The over-budget job was not rejected.",
    )
    client.post("/settings/budget", headers=headers, json={"budget_ceiling_usd": "25"})


def _assemble(cases: list[dict], started: datetime, finished: datetime) -> dict:
    order = {code: index for index, code in enumerate(CASE_ORDER)}
    cases.sort(key=lambda item: order.get(item["code"], 99))
    by_status = {name: [item["code"] for item in cases if item["status"] == name] for name in ("passed", "failed", "mocked", "skipped")}
    if by_status["failed"]:
        run_status = "failed"
    elif by_status["mocked"] or by_status["skipped"]:
        run_status = "completed_with_gaps"
    else:
        run_status = "passed"
    summary = _summary(cases)
    return {
        "source": "database",
        "environment": summary["environment"],
        "database_name": summary["database_name"],
        "status": run_status,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "reproduction": {
            "command": "python scripts/run_commercial_audit.py",
            "working_directory": str(repo_root()),
            "database": "yes_sales_staging",
        },
        "cases": cases,
        "summary": summary,
    }


def _summary(cases: list[dict]) -> dict:
    with system_session() as session:
        database_name = session.scalar(text("SELECT current_database()"))
        qualified = session.scalar(
            text(
                """
                SELECT count(*) FROM opportunities o
                JOIN companies c ON c.id = o.buyer_company_id
                WHERE o.status = 'open'
                  AND c.buyer_stage IN ('qualification', 'match', 'rfq', 'deal')
                """
            )
        )
        rfqs = session.scalar(text("SELECT count(*) FROM rfqs"))
        pending = session.scalar(text("SELECT count(*) FROM approvals WHERE status = 'pending'"))
        commissions = list(session.execute(text("SELECT collection_status, count(*) FROM commission_records GROUP BY 1")))
        decided = list(
            session.execute(text("SELECT EXTRACT(EPOCH FROM (decided_at - created_at)) FROM approvals WHERE decided_at IS NOT NULL"))
        )
        agent_costs = list(
            session.execute(
                text(
                    """
                    SELECT coalesce(ar.agent_name, 'unattributed') AS agent_name, coalesce(sum(pu.cost_usd), 0) AS cost_usd
                    FROM provider_usage pu
                    LEFT JOIN agent_runs ar ON ar.id = pu.agent_run_id
                    GROUP BY 1
                    ORDER BY 1
                    """
                )
            )
        )
        alex_rows = session.scalar(text("SELECT count(*) FROM alex_outcome_metrics"))
        comparable = session.scalar(text("SELECT count(*) FROM alex_outcome_metrics WHERE comparable"))
    controls = [item for item in cases if item["code"] in {"supplier_import", "identifier_mismatch", "superseded_research"}]
    controls_passed = sum(1 for item in controls if item["status"] == "passed")
    mismatch = next(item for item in cases if item["code"] == "identifier_mismatch")
    incorrectly_accepted = 1 if mismatch["evidence"].get("accepted") else 0
    passed_titles = [item["title"] for item in cases if item["status"] == "passed"]
    not_passed = [item["title"] for item in cases if item["status"] != "passed"]
    gaps = ["Live SMTP delivery", "xAI classification against a live model", "WhatsApp", "Grok Bot"]
    if "Process a controlled test phone call" not in not_passed:
        gaps.append("Live phone call")
    intervention = [Decimal(str(row[0])) for row in decided if row[0] is not None]
    return {
        "environment": "staging" if str(database_name).endswith("staging") else "test",
        "database_name": database_name,
        "tested_capabilities": passed_titles,
        "untested_capabilities": not_passed + gaps,
        "passed_tests": [item["code"] for item in cases if item["status"] == "passed"],
        "failed_tests": [item["code"] for item in cases if item["status"] == "failed"],
        "mocked_tests": [item["code"] for item in cases if item["status"] == "mocked"],
        "skipped_tests": [item["code"] for item in cases if item["status"] == "skipped"],
        "research_accuracy": {
            "claims_checked": len(controls),
            "controls_passed": controls_passed,
            "incorrectly_accepted": incorrectly_accepted,
            "ratio": f"{(Decimal(controls_passed) / Decimal(len(controls) or 1)):.4f}",
            "note": "The ratio counts these audit controls. It is not an accuracy score for external factory records.",
        },
        "qualified_sales_opportunities": int(qualified or 0),
        "rfqs": int(rfqs or 0),
        "human_intervention": {
            "seconds": None if not intervention else str(min(intervention)),
            "decisions_measured": len(intervention),
            "reason": None
            if intervention
            else "No founder decision was recorded. Pending approvals have no interval, so human intervention time was not measured.",
        },
        "per_agent_cost_usd": {str(row[0]): f"{Decimal(row[1]):.6f}" for row in agent_costs},
        "commission_status": [{"collection_status": row[0], "count": int(row[1])} for row in commissions] or [{"collection_status": "none_recorded", "count": 0}],
        "pending_approvals": int(pending or 0),
        "alex_outcomes": {
            "rows": int(alex_rows or 0),
            "comparable_pairs": int(comparable or 0),
            "note": "Comparable is true only for a live model send that a person also decided. Mock and skipped work is stored and is not comparable.",
        },
    }


def _persist(report: dict) -> None:
    started = datetime.fromisoformat(report["started_at"])
    finished = datetime.fromisoformat(report["finished_at"])
    with system_session() as session:
        run = CommercialAuditRun(
            environment=report["summary"]["environment"],
            database_name=report["summary"]["database_name"],
            status=report["status"],
            started_at=started,
            finished_at=finished,
            summary=report["summary"],
        )
        session.add(run)
        session.flush()
        for item in report["cases"]:
            session.add(
                CommercialAuditCase(
                    run_id=run.id,
                    code=item["code"],
                    title=item["title"],
                    status=item["status"],
                    executed_at=datetime.fromisoformat(item["executed_at"]),
                    evidence=item["evidence"],
                    failure_reason=item["failure_reason"],
                )
            )
        session.commit()
        report["run_id"] = str(run.id)


def latest_report(session: Session) -> dict | None:
    stored = session.scalar(select(CommercialAuditRun).order_by(CommercialAuditRun.finished_at.desc()).limit(1))
    if stored is None:
        return None
    cases = list(
        session.scalars(select(CommercialAuditCase).where(CommercialAuditCase.run_id == stored.id).order_by(CommercialAuditCase.executed_at))
    )
    return {
        "source": "database",
        "run_id": str(stored.id),
        "environment": stored.environment,
        "database_name": stored.database_name,
        "status": stored.status,
        "started_at": _stamp(stored.started_at),
        "finished_at": _stamp(stored.finished_at),
        "connected_database": session.scalar(text("SELECT current_database()")),
        "cases": [
            {
                "code": item.code,
                "title": item.title,
                "status": item.status,
                "executed_at": _stamp(item.executed_at),
                "evidence": item.evidence,
                "failure_reason": item.failure_reason,
            }
            for item in cases
        ],
        "summary": stored.summary,
    }


def public_report(session: Session) -> dict:
    report = latest_report(session)
    if report is None:
        report = read_evidence_file()
    if report is None:
        return {"source": "none", "status": "not_run", "cases": [], "summary": None}
    connected = session.scalar(text("SELECT current_database()"))
    report["connected_database"] = connected
    report["isolated_from_connected_database"] = report.get("database_name") not in {None, connected}
    return report


def read_evidence_file() -> dict | None:
    path = repo_root() / "audit" / "commercial-audit.json"
    if not path.exists():
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    report["source"] = "evidence_file"
    report["evidence_file"] = "audit/commercial-audit.json"
    return report
