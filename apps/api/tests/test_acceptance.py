import json
import re
import uuid
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import admin_sessionmaker
from app.domain import BUYER_STAGES, SUPPLIER_STAGES
from app.errors import DomainError
from app.security import sign_webhook
from app.services.research import call_xai, guard_fields
from tests.conftest import auth_header

def walk(client: TestClient, headers: dict, company_id: str, side: str, target: str) -> None:
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
        assert response.status_code == 200, response.text
        stage = nxt


def test_supplier_and_buyer_can_be_qualified(client: TestClient) -> None:
    headers = auth_header(client)
    supplier = client.post(
        "/companies",
        headers=headers,
        json={"legal_name": "TEST Bengal Mill", "country": "BD", "role": "supplier", "category": "Knitwear", "is_test": True},
    )
    assert supplier.status_code == 201, supplier.text
    supplier_id = supplier.json()["id"]
    buyer = client.post(
        "/companies",
        headers=headers,
        json={"legal_name": "TEST North Buyer", "country": "DE", "role": "buyer", "category": "Knitwear", "is_test": True},
    )
    buyer_id = buyer.json()["id"]
    excerpts = {
        supplier_id: "Company: TEST Bengal Mill\nCategory: Knitwear\nCountry: BD",
        buyer_id: "Company: TEST North Buyer\nCategory: Knitwear\nCountry: DE",
    }
    for company_id, url in ((supplier_id, "https://test-mill.example/about"), (buyer_id, "https://test-buyer.example/about")):
        source = client.post(
            "/research/sources",
            headers=headers,
            json={
                "company_id": company_id,
                "source_url": url,
                "excerpt": excerpts[company_id],
                "provider": "manual",
            },
        )
        assert source.status_code == 201, source.text
        client.post(
            f"/companies/{company_id}/contacts",
            headers=headers,
            json={
                "full_name": "Public Desk",
                "channel": "email",
                "value": f"desk-{company_id[:8]}@example.com",
                "allowed": True,
                "authorization_basis": "public_business",
                "source_url": url,
            },
        )
    walk(client, headers, supplier_id, "supplier", "qualification")
    walk(client, headers, buyer_id, "buyer", "qualification")
    verified = client.post(f"/companies/{supplier_id}/verification", headers=headers, json={"status": "verified"})
    assert verified.status_code == 200
    assert verified.json()["verification_status"] == "verified"
    assert client.get(f"/companies/{buyer_id}", headers=headers).json()["company"]["buyer_stage"] == "qualification"
    jumped = client.post(
        f"/companies/{supplier_id}/transitions",
        headers=headers,
        json={"side": "supplier", "to_stage": "active_supplier"},
    )
    assert jumped.status_code == 409
    assert jumped.json()["error"]["code"] == "illegal_transition"


def test_duplicates_and_research_evidence(client: TestClient) -> None:
    headers = auth_header(client)
    first = client.post("/companies", headers=headers, json={"legal_name": "TEST Duplicate Co", "country": "MY", "role": "supplier", "website": "https://www.duplicate.test"})
    assert first.status_code == 201
    second = client.post("/companies", headers=headers, json={"legal_name": "test duplicate co", "country": "MY", "role": "buyer"})
    assert second.status_code == 409
    assert second.json()["error"]["details"]["existing_id"] == first.json()["id"]
    domain = client.post("/companies", headers=headers, json={"legal_name": "Other Name", "country": "SG", "role": "buyer", "website": "https://duplicate.test/contact"})
    assert domain.status_code == 409
    contact = client.post(
        f"/companies/{first.json()['id']}/contacts",
        headers=headers,
        json={"full_name": "A", "channel": "email", "value": "Same@Duplicate.test", "allowed": False},
    )
    again = client.post(
        f"/companies/{first.json()['id']}/contacts",
        headers=headers,
        json={"full_name": "B", "channel": "email", "value": "same@duplicate.test", "allowed": True},
    )
    assert again.status_code == 409
    source = client.post(
        "/research/sources",
        headers=headers,
        json={"company_id": first.json()["id"], "source_url": "https://duplicate.test/about", "excerpt": "Company: TEST Duplicate Co\nCategory: Apparel", "provider": "manual"},
    )
    assert source.status_code == 201
    assert source.json()["source_url"] == "https://duplicate.test/about"
    assert source.json()["retrieved_at"]
    duplicate_source = client.post(
        "/research/sources",
        headers=headers,
        json={"company_id": first.json()["id"], "source_url": "https://duplicate.test/about", "excerpt": "Company: TEST Duplicate Co", "provider": "manual"},
    )
    assert duplicate_source.status_code == 409
    extracted = client.post("/research/extract", headers=headers, json={"source_id": source.json()["id"]})
    assert extracted.status_code == 200
    assert extracted.json()["evidence_fields"]["company"] == "TEST Duplicate Co"
    weak = client.post(
        "/research/sources",
        headers=headers,
        json={"company_id": first.json()["id"], "source_url": "https://duplicate.test/empty", "excerpt": "hello", "provider": "manual"},
    )
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "identifier_mismatch"
    other = client.post("/companies", headers=headers, json={"legal_name": "TEST Other Duplicate", "country": "MY", "role": "supplier"}).json()
    shared = client.post(
        "/research/sources",
        headers=headers,
        json={"company_id": other["id"], "source_url": "https://duplicate.test/about", "excerpt": "Company: TEST Other Duplicate", "provider": "manual"},
    )
    assert shared.status_code == 409
    assert shared.json()["error"]["code"] == "duplicate_source"
    job = client.post(
        "/research/jobs",
        headers=headers,
        json={"agent": "meridian", "query": "apparel", "country": "MY", "idempotency_key": "research-test-1"},
    )
    assert job.status_code == 201
    processed = client.post("/tasks/process", headers=headers)
    assert processed.status_code == 200
    result = processed.json()["results"][0]["result"]
    assert result["companies"] == []
    assert result["provider_mode"] == "mock"
    assert contact.status_code == 201


def test_outreach_permission_opt_out_and_pause(client: TestClient) -> None:
    headers = auth_header(client)
    company = client.post("/companies", headers=headers, json={"legal_name": "TEST Mail Co", "country": "BD", "role": "buyer", "is_test": True}).json()
    blocked_contact = client.post(
        f"/companies/{company['id']}/contacts",
        headers=headers,
        json={"full_name": "No", "channel": "email", "value": "no@mail.test", "allowed": False},
    ).json()
    denied = client.post("/messages/send", headers=headers, json={"contact_id": blocked_contact["id"], "body": "Hello"})
    assert denied.status_code == 403
    contact = client.post(
        f"/companies/{company['id']}/contacts",
        headers=headers,
        json={"full_name": "Yes", "channel": "email", "value": "yes@mail.test", "allowed": True, "daily_limit": 1, "authorization_basis": "explicit_consent"},
    ).json()
    sent = client.post("/messages/send", headers=headers, json={"contact_id": contact["id"], "body": "TEST introduction", "subject": "Hello"})
    assert sent.status_code == 201, sent.text
    assert sent.json()["provider_mode"] == "mock"
    assert sent.json()["status"] == "sent"
    payload = json.dumps({"from_email": "yes@mail.test", "body": "Please STOP", "subject": "Re: Hello", "provider_mode": "mock"}).encode()
    inbound = client.post("/webhooks/email/inbound", content=payload, headers={"X-Yes-Signature": sign_webhook(payload), "Content-Type": "application/json"})
    assert inbound.status_code == 200, inbound.text
    assert inbound.json()["classification"] == "opt_out"
    assert inbound.json()["message"]["conversation_id"] == sent.json()["conversation_id"]
    follow = client.post(
        "/tasks",
        headers=headers,
        json={"task_type": "email.followup", "idempotency_key": "follow-1", "payload": {"contact_id": contact["id"], "body": "Second note"}},
    )
    assert follow.status_code == 201
    ran = client.post("/tasks/process", headers=headers)
    assert ran.json()["results"][0]["result"]["blocked"] == "contact_not_eligible"
    bad = client.post("/webhooks/email/inbound", content=payload, headers={"X-Yes-Signature": "deadbeef", "Content-Type": "application/json"})
    assert bad.status_code == 401
    other = client.post(
        f"/companies/{company['id']}/contacts",
        headers=headers,
        json={"full_name": "Rate", "channel": "email", "value": "rate@mail.test", "allowed": True, "daily_limit": 1},
    ).json()
    assert client.post("/messages/send", headers=headers, json={"contact_id": other["id"], "body": "One"}).status_code == 201
    limited = client.post("/messages/send", headers=headers, json={"contact_id": other["id"], "body": "Two"})
    assert limited.status_code == 429
    client.post("/settings/outbound-pause", headers=headers, json={"paused": True})
    fresh = client.post(
        f"/companies/{company['id']}/contacts",
        headers=headers,
        json={"full_name": "Paused", "channel": "email", "value": "paused@mail.test", "allowed": True},
    ).json()
    paused = client.post("/messages/send", headers=headers, json={"contact_id": fresh["id"], "body": "Should not send"})
    assert paused.status_code == 409
    assert paused.json()["error"]["code"] == "outbound_paused"
    audit = client.get("/audit-events", headers=headers).json()["events"]
    assert any(event["action"] == "outbound.blocked" for event in audit)
    whatsapp = client.post("/messages/send", headers=headers, json={"contact_id": fresh["id"], "body": "nope"})
    assert whatsapp.status_code == 409


def test_matching_rfq_quote_and_voice(client: TestClient) -> None:
    headers = auth_header(client)
    supplier = client.post("/companies", headers=headers, json={"legal_name": "TEST Quote Mill", "country": "BD", "role": "supplier", "is_test": True}).json()
    buyer = client.post("/companies", headers=headers, json={"legal_name": "TEST Quote Buyer", "country": "US", "role": "buyer", "is_test": True}).json()
    product = client.post("/products", headers=headers, json={"company_id": supplier["id"], "name": "Jersey", "category": "Knitwear"}).json()
    upload = client.post(
        f"/products/{product['id']}/documents",
        headers=headers,
        files={"upload": ("spec.txt", b"TEST specification", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    requirement = client.post(
        "/buyer-requirements",
        headers=headers,
        json={
            "company_id": buyer["id"],
            "product_category": "Knitwear",
            "desired_quantity": "1000",
            "destination_country": "US",
            "required_certifications": ["GOTS"],
            "lead_time_days": 45,
            "delivery_terms": "sea",
            "currency": "USD",
            "incoterms": "FOB",
        },
    ).json()
    opportunity = client.post(
        "/opportunities",
        headers=headers,
        json={"buyer_company_id": buyer["id"], "supplier_company_id": supplier["id"], "buyer_requirement_id": requirement["id"], "title": "TEST jersey", "pipeline_value": "25000", "currency": "USD"},
    ).json()
    rfq = client.post("/rfqs", headers=headers, json={"buyer_requirement_id": requirement["id"], "opportunity_id": opportunity["id"], "requested_documents": ["spec"]}).json()
    offer = client.post(
        "/supplier-offers",
        headers=headers,
        json={
            "company_id": supplier["id"],
            "product_id": product["id"],
            "rfq_id": rfq["id"],
            "unit_price": "4.50",
            "currency": "USD",
            "incoterms": "FOB",
            "moq": "500",
            "capacity": "2000",
            "lead_time_days": 30,
            "origin_country": "BD",
            "certifications": ["GOTS"],
            "delivery_terms": "sea",
        },
    )
    assert offer.status_code == 201, offer.text
    second = client.post(
        "/supplier-offers",
        headers=headers,
        json={"company_id": supplier["id"], "product_id": product["id"], "rfq_id": rfq["id"], "unit_price": "4.25", "currency": "USD"},
    )
    assert second.json()["version"] == 2
    match = client.post(
        "/matches",
        headers=headers,
        json={"opportunity_id": opportunity["id"], "buyer_requirement_id": requirement["id"], "supplier_offer_id": offer.json()["id"]},
    )
    assert match.status_code == 201, match.text
    explanation = match.json()["explanation"]
    assert "matched" in explanation and "missing" in explanation and "conflicts" in explanation
    assert "landed_cost" not in explanation
    assert any("Landed cost is not calculated." == item for item in explanation["limitations"])
    compared = client.get(f"/rfqs/{rfq['id']}/compare", headers=headers)
    assert len(compared.json()["offers"]) == 2
    voice = client.post("/calls/mock", headers=headers, json={"company_id": buyer["id"], "mode": "buyer", "transcript": "TEST transcript", "request_callback": True})
    assert voice.status_code == 201
    assert voice.json()["provider_mode"] == "mock"
    assert "No carrier" in voice.json()["summary"]
    no_consent = client.post(
        f"/companies/{buyer['id']}/contacts",
        headers=headers,
        json={"full_name": "Phone", "channel": "phone", "value": "+8801700000000", "allowed": True, "consent_for_callback": False},
    ).json()
    outbound = client.post("/calls/outbound", headers=headers, json={"contact_id": no_consent["id"], "mode": "buyer"})
    assert outbound.status_code == 403


def test_founder_approval_blocks_unauthorized_binding(client: TestClient) -> None:
    headers = auth_header(client)
    operator = auth_header(client, "operator@yes-sales.test")
    buyer = client.post("/companies", headers=headers, json={"legal_name": "TEST Deal Buyer", "country": "GB", "role": "buyer", "is_test": True}).json()
    opportunity = client.post("/opportunities", headers=headers, json={"buyer_company_id": buyer["id"], "title": "TEST deal", "pipeline_value": "9000"}).json()
    agreement = client.post("/agreements", headers=headers, json={"opportunity_id": opportunity["id"], "terms": {"note": "draft"}, "evidence_note": "TEST unsigned draft"}).json()
    approval = client.post(
        "/approvals",
        headers=operator,
        json={"action_type": "sign_agreement", "subject_type": "agreement", "subject_id": agreement["id"], "notes": "Please sign"},
    )
    assert approval.status_code == 201, approval.text
    denied = client.post(f"/approvals/{approval.json()['id']}/decide", headers=operator, json={"decision": "approved", "note": "no"})
    assert denied.status_code == 403
    pending_execute = client.post(f"/approvals/{approval.json()['id']}/execute", headers=headers)
    assert pending_execute.status_code == 403
    decided = client.post(f"/approvals/{approval.json()['id']}/decide", headers=headers, json={"decision": "approved", "note": "Approved for test"})
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"
    operator_execute = client.post(f"/approvals/{approval.json()['id']}/execute", headers=operator)
    assert operator_execute.status_code == 403
    executed = client.post(f"/approvals/{approval.json()['id']}/execute", headers=headers)
    assert executed.status_code == 200, executed.text
    assert executed.json()["result"] == "agreement_signed"
    commission = client.post("/commission-records", headers=headers, json={"opportunity_id": opportunity["id"], "terms_text": "5 percent sourcing fee", "currency": "USD"}).json()
    commission_approval = client.post(
        "/approvals",
        headers=headers,
        json={
            "action_type": "bind_commission",
            "subject_type": "commission_record",
            "subject_id": commission["id"],
            "payload": {"rate_percent": "5", "contracted_amount": "450", "terms_text": "5 percent sourcing fee"},
        },
    ).json()
    client.post(f"/approvals/{commission_approval['id']}/decide", headers=headers, json={"decision": "approved", "note": "Fee agreed"})
    bound = client.post(f"/approvals/{commission_approval['id']}/execute", headers=headers)
    assert bound.status_code == 200, bound.text
    collected = client.post(f"/commission-records/{commission['id']}/collections", headers=headers, json={"amount": "100", "invoice_reference": "TEST-INV-1"})
    assert collected.json()["collection_status"] == "partial"
    payment = client.post(
        "/approvals",
        headers=headers,
        json={"action_type": "payment", "subject_type": "commission_record", "subject_id": commission["id"], "payload": {}},
    ).json()
    client.post(f"/approvals/{payment['id']}/decide", headers=headers, json={"decision": "approved", "note": "Do not pay automatically"})
    payment_result = client.post(f"/approvals/{payment['id']}/execute", headers=headers)
    assert payment_result.json()["executed"] is False
    assert payment_result.json()["result"] == "payment_not_executed"
    recorded = client.get("/approvals", headers=headers).json()["approvals"]
    signed = next(item for item in recorded if item["id"] == approval.json()["id"])
    paid = next(item for item in recorded if item["id"] == payment["id"])
    assert signed["outcome"]["result"] == "agreement_signed"
    assert paid["outcome"]["result"] == "payment_not_executed"
    assert paid["outcome"]["executed"] is False
    forbidden = client.post("/agents/invoke", headers=headers, json={"agent": "hunter", "tool": "sign_agreement", "payload": {}})
    assert forbidden.status_code == 403
    audit = client.get("/audit-events", headers=headers).json()["events"]
    assert any(event["action"] == "approval.denied" for event in audit)
    assert any(event["action"] == "agreement.signed" for event in audit)
    assert any(event["action"] == "payment.not_executed" for event in audit)


def test_task_retry_is_idempotent_and_budget_blocks(client: TestClient) -> None:
    headers = auth_header(client)
    created = client.post(
        "/tasks",
        headers=headers,
        json={"task_type": "test.fail_once", "idempotency_key": "fail-once-1", "payload": {"succeed_on_attempt": 2}, "max_attempts": 3},
    )
    assert created.status_code == 201
    task_id = created.json()["task"]["id"]
    first = client.post("/tasks/process", headers=headers).json()["results"][0]
    assert first["status"] == "failed"
    assert client.post("/tasks/process", headers=headers).json()["results"] == []
    restarted_once = client.post(f"/tasks/{task_id}/retry", headers=headers)
    assert restarted_once.status_code == 200
    second = client.post("/tasks/process", headers=headers).json()["results"][0]
    assert second["status"] == "succeeded"
    assert second["result"]["applied"] is True
    third = client.post("/tasks/process", headers=headers).json()["results"]
    assert third == []
    replay = client.post(
        "/tasks",
        headers=headers,
        json={"task_type": "test.fail_once", "idempotency_key": "fail-once-1", "payload": {"succeed_on_attempt": 2}},
    )
    assert replay.json()["idempotent_replay"] is True
    with admin_sessionmaker()() as session:
        count = session.scalar(text("SELECT count(*) FROM audit_events WHERE action = 'task.applied'"))
    assert count == 1
    dead = client.post(
        "/tasks",
        headers=headers,
        json={"task_type": "test.fail_once", "idempotency_key": "dead-1", "payload": {"succeed_on_attempt": 9}, "max_attempts": 1},
    ).json()["task"]
    assert client.post("/tasks/process", headers=headers).json()["results"][0]["status"] == "dead"
    restarted = client.post(f"/tasks/{dead['id']}/retry", headers=headers)
    assert restarted.status_code == 200
    assert restarted.json()["status"] == "queued"
    assert client.post("/tasks/process", headers=headers).json()["results"][0]["status"] == "dead"
    client.post("/settings/budget", headers=headers, json={"budget_ceiling_usd": "5"})
    spend = client.post("/tasks", headers=headers, json={"task_type": "test.spend", "idempotency_key": "spend-1", "payload": {"cost_usd": "4"}})
    assert client.post("/tasks/process", headers=headers).json()["results"][0]["status"] == "succeeded"
    client.post("/tasks", headers=headers, json={"task_type": "test.spend", "idempotency_key": "spend-2", "payload": {"cost_usd": "2"}})
    blocked = client.post("/tasks/process", headers=headers).json()["results"][0]
    assert blocked["status"] == "failed"
    assert "budget" in blocked["last_error"]
    assert spend.status_code == 201


def test_dashboard_matches_database(client: TestClient) -> None:
    headers = auth_header(client)
    supplier = client.post("/companies", headers=headers, json={"legal_name": "TEST KPI Mill", "country": "BD", "role": "supplier", "is_test": True}).json()
    buyer = client.post("/companies", headers=headers, json={"legal_name": "TEST KPI Buyer", "country": "NL", "role": "buyer", "is_test": True}).json()
    kpi_excerpts = {
        supplier["id"]: "Company: TEST KPI Mill\nCategory: Home\nCountry: BD",
        buyer["id"]: "Company: TEST KPI Buyer\nCategory: Home\nCountry: NL",
    }
    for company_id, url in ((supplier["id"], "https://kpi-mill.example"), (buyer["id"], "https://kpi-buyer.example")):
        client.post("/research/sources", headers=headers, json={"company_id": company_id, "source_url": url, "excerpt": kpi_excerpts[company_id], "provider": "manual"})
        client.post(f"/companies/{company_id}/contacts", headers=headers, json={"full_name": "Desk", "channel": "email", "value": f"{company_id[:8]}@kpi.test", "allowed": True, "authorization_basis": "public_business"})
    walk(client, headers, supplier["id"], "supplier", "qualification")
    walk(client, headers, buyer["id"], "buyer", "qualification")
    client.post(f"/companies/{supplier['id']}/verification", headers=headers, json={"status": "verified"})
    requirement = client.post("/buyer-requirements", headers=headers, json={"company_id": buyer["id"], "product_category": "Home", "desired_quantity": "10"}).json()
    opportunity = client.post("/opportunities", headers=headers, json={"buyer_company_id": buyer["id"], "title": "TEST kpi", "pipeline_value": "1000", "currency": "USD"}).json()
    client.post("/rfqs", headers=headers, json={"buyer_requirement_id": requirement["id"], "opportunity_id": opportunity["id"]})
    offer = client.post("/supplier-offers", headers=headers, json={"company_id": supplier["id"], "unit_price": "2", "currency": "USD"}).json()
    client.post("/matches", headers=headers, json={"opportunity_id": opportunity["id"], "buyer_requirement_id": requirement["id"], "supplier_offer_id": offer["id"]})
    client.post("/approvals", headers=headers, json={"action_type": "legal_declaration", "subject_type": "opportunity", "subject_id": opportunity["id"], "payload": {}})
    commission = client.post("/commission-records", headers=headers, json={"opportunity_id": opportunity["id"], "currency": "USD"}).json()
    approval = client.post(
        "/approvals",
        headers=headers,
        json={"action_type": "bind_commission", "subject_type": "commission_record", "subject_id": commission["id"], "payload": {"rate_percent": "3", "contracted_amount": "80"}},
    ).json()
    client.post(f"/approvals/{approval['id']}/decide", headers=headers, json={"decision": "approved", "note": "ok"})
    client.post(f"/approvals/{approval['id']}/execute", headers=headers)
    client.post(f"/commission-records/{commission['id']}/collections", headers=headers, json={"amount": "15"})
    client.post("/calls/mock", headers=headers, json={"mode": "supplier", "transcript": "TEST"})
    kpis = client.get("/dashboard/kpis", headers=headers)
    assert kpis.status_code == 200, kpis.text
    body = kpis.json()
    with admin_sessionmaker()() as session:
        expected = {
            "verified_suppliers": session.scalar(text("SELECT count(*) FROM companies WHERE role IN ('supplier','both') AND verification_status = 'verified'")),
            "qualified_buyers": session.scalar(text("SELECT count(*) FROM companies WHERE role IN ('buyer','both') AND buyer_stage IN ('qualification','match','rfq','deal')")),
            "active_conversations": session.scalar(text("SELECT count(*) FROM conversations WHERE status IN ('open','waiting','handoff')")),
            "rfqs": session.scalar(text("SELECT count(*) FROM rfqs")),
            "supplier_quotations": session.scalar(text("SELECT count(*) FROM supplier_offers")),
            "matched_opportunities": session.scalar(text("SELECT count(DISTINCT opportunity_id) FROM matches")),
            "deals_requiring_approval": session.scalar(text("SELECT count(*) FROM approvals WHERE status = 'pending'")),
            "pipeline_value": session.scalar(text("SELECT coalesce(sum(pipeline_value),0) FROM opportunities WHERE status = 'open'")),
            "contracted_commissions": session.scalar(text("SELECT coalesce(sum(contracted_amount),0) FROM commission_records")),
            "collected_commissions": session.scalar(text("SELECT coalesce(sum(collected_amount),0) FROM commission_records")),
            "agent_errors": session.scalar(text("SELECT count(*) FROM agent_runs WHERE status = 'failed'")),
            "api_costs": session.scalar(text("SELECT coalesce(sum(cost_usd),0) FROM provider_usage")),
        }
    assert body["verified_suppliers"] == expected["verified_suppliers"] == 1
    assert body["qualified_buyers"] == expected["qualified_buyers"] == 1
    assert body["rfqs"] == expected["rfqs"] == 1
    assert body["supplier_quotations"] == expected["supplier_quotations"] == 1
    assert body["matched_opportunities"] == expected["matched_opportunities"] == 1
    assert body["deals_requiring_approval"] == expected["deals_requiring_approval"] == 1
    assert Decimal(body["pipeline_value"]) == Decimal(expected["pipeline_value"])
    assert Decimal(body["contracted_commissions"]) == Decimal(expected["contracted_commissions"]) == Decimal("80.00")
    assert Decimal(body["collected_commissions"]) == Decimal(expected["collected_commissions"]) == Decimal("15.00")
    assert body["agent_errors"] == expected["agent_errors"]
    assert Decimal(body["api_costs"]) == Decimal(expected["api_costs"])
    assert body["integrations"]["whatsapp"] == "not_configured"
    assert body["integrations"]["grok_bot"] == "not_configured"
    assert body["integrations"]["email"] == "mock"
    assert body["active_conversations"] == expected["active_conversations"]


def test_company_creation_is_audited_and_vertical_slice(client: TestClient) -> None:
    headers = auth_header(client)
    company = client.post("/companies", headers=headers, json={"legal_name": "TEST Slice Buyer", "country": "FR", "role": "buyer", "is_test": True})
    contact = client.post(
        f"/companies/{company.json()['id']}/contacts",
        headers=headers,
        json={"full_name": "Buyer Desk", "channel": "email", "value": "slice@buyer.test", "allowed": True, "authorization_basis": "public_business"},
    )
    requirement = client.post("/buyer-requirements", headers=headers, json={"company_id": company.json()["id"], "product_category": "Ceramics"})
    opportunity = client.post("/opportunities", headers=headers, json={"buyer_company_id": company.json()["id"], "buyer_requirement_id": requirement.json()["id"], "title": "TEST slice"})
    approval = client.post(
        "/approvals",
        headers=headers,
        json={"action_type": "share_restricted", "subject_type": "contact", "subject_id": contact.json()["id"], "notes": "Share spec"},
    )
    rejected = client.post(f"/approvals/{approval.json()['id']}/decide", headers=headers, json={"decision": "rejected", "note": "Not yet"})
    events = client.get("/audit-events", headers=headers).json()["events"]
    actions = {event["action"] for event in events}
    assert {"company.created", "contact.created", "requirement.created", "opportunity.created", "approval.requested", "approval.decided"} <= actions
    assert rejected.json()["status"] == "rejected"
    assert opportunity.status_code == 201


def test_guard_rejects_values_missing_from_source() -> None:
    with pytest.raises(DomainError) as caught:
        guard_fields("Company: Real Mill", {"company": "Invented Mill"})
    assert caught.value.code == "unsupported_fields"


def test_xai_adapter_posts_responses_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/responses"
        body = json.loads(request.content)
        assert body["text"]["format"]["type"] == "json_schema"
        payload = {"company": "Real Mill", "website": None, "email": None, "phone": None, "category": None, "country": None}
        return httpx.Response(200, json={"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(payload)}]}]})

    fields = call_xai("Company: Real Mill", httpx.Client(transport=httpx.MockTransport(handler)))
    guard_fields("Company: Real Mill", fields)
    assert fields["company"] == "Real Mill"
    get_settings.cache_clear()


def test_scheduler_token_and_login(client: TestClient) -> None:
    denied = client.post("/tasks/external", json={"task_type": "research.search", "idempotency_key": "ext-1", "payload": {}})
    assert denied.status_code == 401
    allowed = client.post(
        "/tasks/external",
        json={"task_type": "research.search", "idempotency_key": "ext-1", "payload": {"agent": "orion", "query": "cotton"}},
        headers={"X-Scheduler-Token": "test-scheduler"},
    )
    assert allowed.status_code == 201, allowed.text
    bad_login = client.post("/auth/login", json={"email": "founder@yes-sales.test", "password": "wrong-password"})
    assert bad_login.status_code == 401
    open_classify = client.post("/alex/classify", json={"body": "Please call me back tomorrow"})
    assert open_classify.status_code == 401
    assert "password_hash" not in json.dumps(client.get("/me", headers=auth_header(client)).json())
    assert uuid.UUID(client.get("/me", headers=auth_header(client)).json()["id"])


def test_alex_draft_approval_context_and_unverified_voice(client: TestClient) -> None:
    headers = auth_header(client)
    company = client.post(
        "/companies",
        headers=headers,
        json={"legal_name": "TEST Alex Buyer", "country": "DE", "role": "buyer", "is_test": True},
    ).json()
    contact = client.post(
        f"/companies/{company['id']}/contacts",
        headers=headers,
        json={"full_name": "Ada", "channel": "email", "value": "ada@alex.test", "allowed": True, "authorization_basis": "explicit_consent"},
    ).json()
    context = client.get(f"/contacts/{contact['id']}/context", headers=headers)
    assert context.status_code == 200, context.text
    encoded = json.dumps(context.json())
    assert "TEST Alex Buyer" in encoded
    assert "unit_price" not in encoded
    assert "landed_cost" not in encoded
    classified = client.post("/alex/classify", headers=headers, json={"body": "Please call me back tomorrow"})
    assert classified.json()["classification"] == "callback_request"
    assert classified.json()["provider_mode"] == "not_configured"
    assert classified.json()["live_model_called"] is False
    commercial = client.post("/messages/send", headers=headers, json={"contact_id": contact["id"], "body": "Our price is 4.50"})
    assert commercial.status_code == 403
    assert commercial.json()["error"]["code"] == "approval_required"
    draft = client.post(
        "/alex/drafts",
        headers=headers,
        json={"contact_id": contact["id"], "subject": "TEST knitwear", "body": "We need knitwear next season"},
    )
    assert draft.status_code == 201, draft.text
    body = draft.json()
    assert body["sent"] is False
    assert body["message"]["status"] == "draft"
    assert body["message"]["provider_mode"] == "mock"
    assert "not stating a price" in body["message"]["body"]
    assert body["approval"]["status"] == "pending"
    approval_id = body["approval"]["id"]
    pending = client.post(f"/approvals/{approval_id}/execute", headers=headers)
    assert pending.status_code == 403
    decided = client.post(f"/approvals/{approval_id}/decide", headers=headers, json={"decision": "approved", "note": "TEST draft"})
    assert decided.status_code == 200
    client.post("/settings/outbound-pause", headers=headers, json={"paused": True})
    paused = client.post(f"/approvals/{approval_id}/execute", headers=headers)
    assert paused.status_code == 409
    assert paused.json()["error"]["code"] == "outbound_paused"
    client.post("/settings/outbound-pause", headers=headers, json={"paused": False})
    released = client.post(f"/approvals/{approval_id}/execute", headers=headers)
    assert released.status_code == 200, released.text
    assert released.json()["result"] == "message_sent"
    assert released.json()["provider_mode"] == "mock"
    assert released.json()["live_email"] is False
    assert released.json()["live_call"] is False
    handoff = client.post(f"/conversations/{body['message']['conversation_id']}/handoff", headers=headers, json={"note": "TEST person"})
    assert handoff.status_code == 200
    assert handoff.json()["status"] == "handoff"
    follow = client.post(
        "/alex/follow-ups",
        headers=headers,
        json={"contact_id": contact["id"], "body": "Checking in", "delay_hours": 24, "idempotency_key": "alex-follow-1"},
    )
    assert follow.status_code == 201, follow.text
    assert follow.json()["sent"] is False
    ran = client.post("/tasks/process", headers=headers)
    assert ran.json()["results"] == []
    stopped = client.post(
        f"/companies/{company['id']}/contacts",
        headers=headers,
        json={"full_name": "Stop", "channel": "email", "value": "stop@alex.test", "allowed": True},
    ).json()
    opt_out = client.post("/alex/drafts", headers=headers, json={"contact_id": stopped["id"], "body": "Please STOP"})
    assert opt_out.status_code == 403
    saved = client.get(f"/companies/{company['id']}", headers=headers).json()
    stopped_contact = next(item for item in saved["contacts"] if item["id"] == stopped["id"])
    assert stopped_contact["permission"]["opted_out"] is True
    assert stopped_contact["permission"]["allowed"] is False
    assert any(item["action"] == "contact.opt_out" for item in saved["activity"])
    repeat = client.post("/alex/drafts", headers=headers, json={"contact_id": stopped["id"], "body": "Hello again"})
    assert repeat.status_code == 403
    blocked_send = client.post(
        "/messages/send",
        headers=headers,
        json={"contact_id": stopped["id"], "body": "Hello after the earlier request"},
    )
    assert blocked_send.status_code == 403
    assert blocked_send.json()["error"]["code"] == "contact_not_eligible"
    reread = client.get(f"/companies/{company['id']}", headers=headers).json()
    after_block = next(item for item in reread["contacts"] if item["id"] == stopped["id"])
    assert after_block["permission"]["opted_out"] is True
    assert after_block["permission"]["allowed"] is False
    phone = client.post(
        f"/companies/{company['id']}/contacts",
        headers=headers,
        json={"full_name": "Phone", "channel": "phone", "value": "+8801711111111", "allowed": True, "consent_for_callback": True},
    ).json()
    outbound = client.post("/calls/outbound", headers=headers, json={"contact_id": phone["id"], "mode": "buyer"})
    assert outbound.status_code == 201, outbound.text
    assert outbound.json()["placed"] is False
    assert outbound.json()["provider_mode"] == "not_configured"
    assert "No call was placed" in outbound.json()["summary"]
    assert client.get("/integrations", headers=headers).json()["live_call_verified"] is False


def test_commercial_audit_does_not_pass_mocked_or_skipped(client: TestClient) -> None:
    from app.services.commercial_audit import execute_commercial_audit

    report = execute_commercial_audit(client)
    statuses = {item["code"]: item["status"] for item in report["cases"]}
    assert len(report["cases"]) == 15
    assert statuses["inbound_email"] == "mocked"
    assert statuses["phone_call"] == "skipped"
    assert "inbound_email" not in report["summary"]["passed_tests"]
    assert "phone_call" not in report["summary"]["passed_tests"]
    assert report["status"] == "completed_with_gaps"
    assert report["summary"]["research_accuracy"]["incorrectly_accepted"] == 0
    assert report["summary"]["qualified_sales_opportunities"] >= 1
    assert report["summary"]["rfqs"] >= 1
    assert report["summary"]["pending_approvals"] >= 1
    assert report["summary"]["alex_outcomes"]["comparable_pairs"] == 0
    assert report["summary"]["human_intervention"]["seconds"] is None
    for item in report["cases"]:
        if item["status"] == "passed":
            assert item["failure_reason"] is None
        else:
            assert item["failure_reason"]


def test_bot_import_rejects_untrusted_labels_and_reaches_approval(client: TestClient) -> None:
    headers = auth_header(client)
    supplier = {
        "agent_name": "bengal",
        "task_id": "YS-TEST-BOT-001",
        "company_identity": "TEST Bot Knit Mill",
        "company_type": "supplier",
        "country": "BD",
        "product_category": "knitwear",
        "source_urls": ["https://example.com/test-bot-knit-mill"],
        "verification_date": "2026-11-02",
        "verification_status": "VERIFIED",
        "contact_eligibility": "eligible",
        "source_document_reference": "samples/grok-bot-import.example.json",
        "source_excerpt": "Company: TEST Bot Knit Mill\nCountry: BD\nCategory: knitwear",
        "import_status": "ready",
    }
    buyer = {
        **supplier,
        "agent_name": "hunter",
        "task_id": "YS-TEST-BOT-004",
        "company_identity": "TEST Bot Rhine Buyer",
        "company_type": "buyer",
        "country": "DE",
        "source_urls": ["https://example.com/test-bot-rhine-buyer"],
        "verification_status": "pending",
        "contact_eligibility": "unknown",
        "source_excerpt": "Company: TEST Bot Rhine Buyer\nCountry: DE\nCategory: knitwear",
    }
    quarantined = {
        **supplier,
        "task_id": "YS-TEST-BOT-002",
        "company_identity": "TEST Bot Quarantine Mill",
        "source_excerpt": "Company: TEST Bot Quarantine Mill\nCountry: BD",
        "import_status": "quarantined",
    }
    superseded = {
        **supplier,
        "task_id": "YS-TEST-BOT-003",
        "company_identity": "TEST Bot Old Mill",
        "source_excerpt": "Company: TEST Bot Old Mill\nCountry: BD",
        "import_status": "superseded",
    }
    mismatched = {
        **supplier,
        "task_id": "YS-TEST-BOT-005",
        "company_identity": "TEST Bot Knit Mill",
        "source_urls": ["https://example.com/test-bot-mismatch"],
        "source_excerpt": "Company: TEST Some Other Mill\nCountry: BD",
    }
    first = client.post("/research/bot-imports", headers=headers, json={"records": [supplier, buyer, quarantined, superseded, mismatched]})
    assert first.status_code == 200, first.text
    by_task = {item["task_id"]: item for item in first.json()["results"]}
    assert by_task["YS-TEST-BOT-001"]["import_status"] == "accepted"
    assert by_task["YS-TEST-BOT-001"]["verification_trusted"] is False
    assert by_task["YS-TEST-BOT-001"]["outreach_authorized"] is False
    assert by_task["YS-TEST-BOT-001"]["stored_verification_status"] == "unverified"
    assert by_task["YS-TEST-BOT-005"]["import_status"] == "rejected"
    assert by_task["YS-TEST-BOT-005"]["company_id"] is None
    assert by_task["YS-TEST-BOT-002"]["import_status"] == "quarantined"
    assert by_task["YS-TEST-BOT-002"]["company_id"] is None
    assert by_task["YS-TEST-BOT-003"]["import_status"] == "superseded"
    replay = client.post(
        "/research/bot-imports",
        headers=headers,
        json={"csv": "agent_name,task_id,company_identity,company_type,country,product_category,source_urls,verification_date,verification_status,contact_eligibility,source_document_reference,import_status\nbengal,YS-TEST-BOT-001,TEST Bot Knit Mill,supplier,BD,knitwear,https://example.com/test-bot-knit-mill,2026-11-02,VERIFIED,eligible,samples/grok-bot-import.example.json,ready\n"},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["results"][0]["idempotent_replay"] is True
    listed = client.get("/companies", headers=headers, params={"q": "TEST Bot"}).json()["companies"]
    names = {item["legal_name"] for item in listed}
    assert names == {"TEST Bot Knit Mill", "TEST Bot Rhine Buyer"}
    supplier_id = by_task["YS-TEST-BOT-001"]["company_id"]
    buyer_id = by_task["YS-TEST-BOT-004"]["company_id"]
    profile = client.get(f"/companies/{supplier_id}", headers=headers).json()
    assert profile["contacts"] == []
    assert profile["company"]["verification_status"] == "unverified"
    assert profile["sources"] == []
    assert by_task["YS-TEST-BOT-001"]["evidence_status"] == "held"
    assert by_task["YS-TEST-BOT-001"]["claim_downgraded"] is True
    assert by_task["YS-TEST-BOT-001"]["stored_as_research_source"] is False
    assert by_task["YS-TEST-BOT-001"]["claim_evidence"]["evidence_excerpt"] is None
    assert "Company: TEST Bot Knit Mill" in by_task["YS-TEST-BOT-001"]["claim_evidence"]["claim_text"]
    assert any(item["action"] == "company.created" for item in profile["activity"])
    refused = client.post(f"/companies/{supplier_id}/verification", headers=headers, json={"status": "verified"})
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "evidence_required"
    advanced = client.post(f"/companies/{supplier_id}/transitions", headers=headers, json={"side": "supplier", "to_stage": "research"})
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["supplier_stage"] == "research"
    requirement = client.post(
        "/buyer-requirements",
        headers=headers,
        json={"company_id": buyer_id, "product_category": "knitwear", "desired_quantity": "1000", "destination_country": "DE"},
    ).json()
    product = client.post("/products", headers=headers, json={"company_id": supplier_id, "name": "TEST knit jersey", "category": "knitwear"}).json()
    offer = client.post(
        "/supplier-offers",
        headers=headers,
        json={"company_id": supplier_id, "product_id": product["id"], "unit_price": "4.50", "currency": "USD", "origin_country": "BD", "notes": "TEST quotation"},
    ).json()
    opportunity = client.post(
        "/opportunities",
        headers=headers,
        json={"buyer_company_id": buyer_id, "supplier_company_id": supplier_id, "buyer_requirement_id": requirement["id"], "title": "TEST bot knit deal", "pipeline_value": "4500"},
    ).json()
    rfq = client.post("/rfqs", headers=headers, json={"buyer_requirement_id": requirement["id"], "opportunity_id": opportunity["id"], "notes": "TEST RFQ"}).json()
    supplier_contact = client.post(
        f"/companies/{supplier_id}/contacts",
        headers=headers,
        json={"full_name": "TEST Mill Desk", "channel": "email", "value": "mill-desk@example.com", "allowed": True, "authorization_basis": "explicit_consent"},
    ).json()
    requested = client.post("/rfqs/" + rfq["id"] + "/request-quotes", headers=headers, json={"supplier_company_ids": [supplier_id]})
    assert requested.status_code == 200, requested.text
    assert requested.json()["sent"] is False
    assert requested.json()["live_email"] is False
    assert requested.json()["status"] == "draft"
    assert requested.json()["requests"][0]["message_status"] == "draft"
    assert requested.json()["requests"][0]["approval_id"]
    mill_profile = client.get(f"/companies/{supplier_id}", headers=headers).json()
    assert any(item["id"] == supplier_contact["id"] for item in mill_profile["contacts"])
    assert any(item["action"] == "contact.created" for item in mill_profile["activity"])
    quoted = client.post(
        "/supplier-offers",
        headers=headers,
        json={"company_id": supplier_id, "product_id": product["id"], "rfq_id": rfq["id"], "unit_price": "4.50", "currency": "USD", "origin_country": "BD"},
    ).json()
    match = client.post(
        "/matches",
        headers=headers,
        json={"opportunity_id": opportunity["id"], "buyer_requirement_id": requirement["id"], "supplier_offer_id": offer["id"]},
    )
    assert match.status_code == 201, match.text
    deals = client.get("/opportunities", headers=headers).json()["opportunities"]
    deal = next(item for item in deals if item["id"] == opportunity["id"])
    assert deal["stage"] == "quoting"
    assert deal["rfqs"][0]["id"] == rfq["id"]
    assert deal["rfqs"][0]["status"] == "quoted"
    contact = client.post(
        f"/companies/{buyer_id}/contacts",
        headers=headers,
        json={"full_name": "TEST Buyer Desk", "channel": "email", "value": "buyer-desk@example.com", "allowed": True, "authorization_basis": "explicit_consent"},
    ).json()
    draft = client.post("/alex/drafts", headers=headers, json={"contact_id": contact["id"], "body": "Please introduce your knitwear range.", "subject": "TEST introduction"})
    assert draft.status_code == 201, draft.text
    assert draft.json()["sent"] is False
    assert draft.json()["approval"]["status"] == "pending"
    assert draft.json()["approval"]["action_type"] == "send_outreach"
    actions = {event["action"] for event in client.get("/audit-events", headers=headers).json()["events"]}
    assert "bot_import.accepted" in actions
    assert "bot_import.rejected" in actions
    assert "match.created" in actions
    assert "alex.draft_created" in actions
    assert quoted["version"] == 1


def test_one_hunter_task_imports_many_companies_and_replays_duplicates(client: TestClient) -> None:
    headers = auth_header(client)
    task_id = "YS-TEST-HUNTER-COHORT"
    records = []
    for index in range(1, 26):
        name = f"TEST Hunter Cohort {index:02d}"
        records.append(
            {
                "agent_name": "hunter",
                "task_id": task_id,
                "company_identity": name,
                "company_type": "buyer",
                "country": "DE",
                "product_category": "knitwear",
                "source_urls": [f"https://example.com/test-hunter-cohort-{index:02d}"],
                "verification_date": "2026-11-03",
                "verification_status": "VERIFIED",
                "contact_eligibility": "unknown",
                "source_document_reference": "samples/grok-bot-import.example.json",
                "source_excerpt": f"Company: {name}\nCountry: DE\nCategory: knitwear",
                "import_status": "ready",
            }
        )
    first = client.post("/research/bot-imports", headers=headers, json={"records": [*records, records[0]]})
    assert first.status_code == 200, first.text
    results = first.json()["results"]
    assert len(results) == 26
    assert sum(item["idempotent_replay"] for item in results) == 1
    accepted = [item for item in results if item["import_status"] == "accepted" and not item["idempotent_replay"]]
    assert len(accepted) == 25
    assert len({item["company_id"] for item in accepted}) == 25
    assert {item["task_id"] for item in results} == {task_id}
    assert all(item["claim_downgraded"] is True and item["evidence_status"] == "held" for item in accepted)
    assert all(item["claim_evidence"]["evidence_excerpt"] is None for item in accepted)
    assert all(item["stored_verification_status"] == "unverified" for item in accepted)
    listed = client.get("/companies", headers=headers, params={"q": "TEST Hunter Cohort"}).json()["companies"]
    assert len(listed) == 25
    profile = client.get(f"/companies/{accepted[0]['company_id']}", headers=headers).json()
    assert profile["sources"] == []
    assert profile["company"]["verification_status"] == "unverified"
    retry = client.post("/research/bot-imports", headers=headers, json={"records": records})
    assert retry.status_code == 200, retry.text
    assert len(retry.json()["results"]) == 25
    assert all(item["idempotent_replay"] is True for item in retry.json()["results"])
    assert len(client.get("/companies", headers=headers, params={"q": "TEST Hunter Cohort"}).json()["companies"]) == 25
    duplicate = client.post("/research/bot-imports", headers=headers, json={"records": [records[0], records[0]]})
    assert duplicate.status_code == 200, duplicate.text
    assert all(item["idempotent_replay"] is True for item in duplicate.json()["results"])
    assert len(client.get("/companies", headers=headers, params={"q": "TEST Hunter Cohort"}).json()["companies"]) == 25


def test_app_job_pause_is_separate_from_outbound_and_grok(client: TestClient) -> None:
    headers = auth_header(client)
    created = client.post(
        "/tasks",
        headers=headers,
        json={"task_type": "research.search", "idempotency_key": "jobs-pause-1", "payload": {"agent": "hunter", "query": "TEST knitwear"}},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task"]["id"]
    paused = client.post("/settings/jobs-pause", headers=headers, json={"paused": True})
    assert paused.status_code == 200, paused.text
    assert paused.json()["jobs_paused"] is True
    assert paused.json()["outbound_paused"] is False
    operator = auth_header(client, "operator@yes-sales.test")
    denied = client.post("/settings/jobs-pause", headers=operator, json={"paused": False})
    assert denied.status_code == 403
    held = client.post("/tasks/process", headers=headers)
    assert held.json()["results"] == []
    queued = next(item for item in client.get("/tasks", headers=headers).json()["tasks"] if item["id"] == task_id)
    assert queued["status"] == "queued"
    assert queued["attempt"] == 0
    resumed = client.post("/settings/jobs-pause", headers=headers, json={"paused": False})
    assert resumed.json()["jobs_paused"] is False
    assert resumed.json()["outbound_paused"] is False
    ran = client.post("/tasks/process", headers=headers)
    assert ran.json()["results"][0]["id"] == task_id
    assert ran.json()["results"][0]["status"] == "succeeded"
    integrations = client.get("/integrations", headers=headers).json()
    assert integrations["grok_bot"] == "not_configured"
    assert integrations["grok_connected"] is False
    assert integrations["grok_credit_control"] == "none"
    picture = client.get("/dashboard/kpis", headers=headers).json()
    assert picture["jobs_paused"] is False
    assert picture["outbound_paused"] is False
    assert picture["integrations"]["grok_connected"] is False
    assert picture["integrations"]["grok_bot_ingest"] == "not_configured"


def test_grok_bot_post_stays_closed_without_a_token_and_a_key_marks_the_model(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings
    from app.services.orchestration import integration_status

    closed = client.post("/integrations/grok-bot/imports", json={"records": []})
    assert closed.status_code == 503
    assert closed.json()["error"]["code"] == "grok_bot_not_configured"
    monkeypatch.setenv("GROK_BOT_TOKEN", "test-bot-token")
    get_settings.cache_clear()
    denied = client.post(
        "/integrations/grok-bot/imports",
        headers={"X-Grok-Bot-Token": "other-token"},
        json={"records": []},
    )
    assert denied.status_code == 401
    accepted = client.post(
        "/integrations/grok-bot/imports",
        headers={"X-Grok-Bot-Token": "test-bot-token"},
        json={
            "records": [
                {
                    "agent_name": "bengal",
                    "task_id": "YS-TEST-GROK-DOOR",
                    "company_identity": "TEST Grok Door Mill",
                    "company_type": "supplier",
                    "country": "BD",
                    "product_category": "knitwear",
                    "source_urls": ["https://example.com/test-grok-door-mill"],
                    "verification_date": "2026-11-04",
                    "verification_status": "VERIFIED",
                    "contact_eligibility": "unknown",
                    "source_document_reference": "grok-bot-post",
                    "source_excerpt": "Company: TEST Grok Door Mill\nCountry: BD\nCategory: knitwear",
                    "import_status": "ready",
                }
            ]
        },
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["verification_trusted"] is False
    assert body["outreach_authorized"] is False
    assert body["grok_credit_control"] == "none"
    assert body["results"][0]["stored_verification_status"] == "unverified"
    assert body["results"][0]["stored_as_research_source"] is False
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    get_settings.cache_clear()
    connected = integration_status()
    assert connected["grok_connected"] is True
    assert connected["grok_bot"] == "configured_unverified"
    assert connected["llm"] == "configured_unverified"
    assert connected["grok_credit_control"] == "none"
    get_settings.cache_clear()


def _shop(client: TestClient, headers: dict, name: str) -> str:
    created = client.post(
        "/companies",
        headers=headers,
        json={"legal_name": name, "country": "MY", "role": "supplier", "category": "Detailing", "is_test": True},
    )
    assert created.status_code == 201, created.text
    company = client.get(f"/companies/{created.json()['id']}", headers=headers).json()["company"]
    assert company["role"] == "supplier"
    assert company["supplier_stage"] == "discover"
    return created.json()["id"]


def _approve_sheet(client: TestClient, headers: dict, company_id: str, name: str, price: str, sentence: str) -> str:
    sheet = client.post(
        "/service-sheets",
        headers=headers,
        json={
            "company_id": company_id,
            "service_name": name,
            "duration_notes": "TEST half day",
            "currency": "MYR",
            "price": price,
            "allowed_sentence": sentence,
        },
    )
    assert sheet.status_code == 201, sheet.text
    assert sheet.json()["status"] == "draft"
    approval = client.post(f"/service-sheets/{sheet.json()['id']}/request-approval", headers=headers)
    assert approval.status_code == 201, approval.text
    decided = client.post(
        f"/approvals/{approval.json()['id']}/decide",
        headers=headers,
        json={"decision": "approved", "note": "TEST sheet"},
    )
    assert decided.status_code == 200, decided.text
    executed = client.post(f"/approvals/{approval.json()['id']}/execute", headers=headers)
    assert executed.status_code == 200, executed.text
    assert executed.json()["result"] == "service_sheet_approved"
    return sheet.json()["id"]


def _file(client: TestClient, headers: dict, company_id: str, service: str, message: str, when: str | None = None) -> dict:
    filed = client.post(
        "/job-cards",
        headers=headers,
        json={
            "company_id": company_id,
            "vehicle": "TEST Myvi",
            "requested_service": service,
            "preferred_time": when,
            "photo_note": "TEST photo note",
            "customer_message": message,
        },
    )
    assert filed.status_code == 201, filed.text
    return filed.json()


def test_approved_job_card_refuses_unapproved_price_booking_and_handoff(client: TestClient) -> None:
    headers = auth_header(client)
    shop = _shop(client, headers, "TEST Detailing Studio")
    interior = _approve_sheet(client, headers, shop, "interior detail", "450.00", "Interior detail is RM450.")
    coating = client.post(
        "/service-sheets",
        headers=headers,
        json={
            "company_id": shop,
            "service_name": "ceramic coating",
            "currency": "MYR",
            "price": "880.00",
            "allowed_sentence": "Ceramic coating is RM880.",
        },
    )
    assert coating.status_code == 201, coating.text
    assert coating.json()["status"] == "draft"

    quoted = _file(client, headers, shop, "interior detail", "How much is interior detail?")
    assert quoted["status"] == "requested"
    assert quoted["reply"]["sent"] is False
    assert quoted["reply"]["price_allowed"] is True
    assert quoted["reply"]["allowed_sheet_ids"] == [interior]
    assert "Interior detail is RM450." in quoted["reply"]["body"]

    unknown = _file(client, headers, shop, "ceramic coating", "How much is ceramic coating?")
    assert unknown["status"] == "handed_off"
    assert unknown["reply"]["price_allowed"] is False
    assert unknown["reply"]["allowed_sheet_ids"] == []
    assert "880" not in unknown["reply"]["body"]
    assert "450" not in unknown["reply"]["body"]
    assert "confirm the price" in unknown["reply"]["body"]
    assert re.search(r"\d|RM|MYR|\$", unknown["reply"]["body"]) is None

    booking = _file(client, headers, shop, "interior detail", "Book me tomorrow at 10", "tomorrow at 10")
    assert booking["status"] == "requested"
    assert booking["bay_confirmed"] is False
    assert "bay is not confirmed" in booking["reply"]["body"]
    bay = client.post(f"/job-cards/{booking['id']}/request-bay", headers=headers)
    assert bay.status_code == 201, bay.text
    still = client.get(f"/job-cards/{booking['id']}", headers=headers)
    assert still.json()["status"] == "requested"

    with admin_sessionmaker()() as session:
        with pytest.raises(Exception):
            session.execute(text("UPDATE job_cards SET status = 'bay_confirmed' WHERE id = :id"), {"id": booking["id"]})
            session.commit()
        session.rollback()
    after = client.get(f"/job-cards/{booking['id']}", headers=headers)
    assert after.json()["status"] == "requested"

    person = _file(client, headers, shop, "interior detail", "I want a person")
    assert person["status"] == "handed_off"
    assert person["reply"]["sent"] is False
    assert person["reply"]["price_allowed"] is False
    assert "450" not in person["reply"]["body"]
    with admin_sessionmaker()() as session:
        sent = session.execute(text("SELECT count(*) FROM messages WHERE status = 'sent'")).scalar_one()
        replies = session.execute(text("SELECT count(*) FROM job_card_replies WHERE sent = true")).scalar_one()
    assert sent == 0
    assert replies == 0


def test_job_card_company_scope_is_not_tenant_isolation(client: TestClient) -> None:
    headers = auth_header(client)
    first = _shop(client, headers, "TEST Detailing Studio")
    second = _shop(client, headers, "TEST Other Detailing Studio")
    own = _approve_sheet(client, headers, first, "interior detail", "450.00", "Interior detail is RM450.")
    other = _approve_sheet(client, headers, second, "interior detail", "999.00", "Interior detail is RM999.")
    visible = {row["id"] for row in client.get("/companies", headers=headers).json()["companies"]}
    assert first in visible and second in visible
    filed = _file(client, headers, first, "interior detail", "How much is interior detail?")
    assert filed["reply"]["allowed_sheet_ids"] == [own]
    assert other not in filed["reply"]["allowed_sheet_ids"]
    assert "RM450" in filed["reply"]["body"]
    assert "999" not in filed["reply"]["body"]
    assert "tenant" not in filed


TOKEN_ROUTES = {
    "/health",
    "/auth/login",
    "/webhooks/email/inbound",
    "/internal/calls",
    "/tasks/external",
    "/integrations/grok-bot/imports",
}


def _dependency_names(dependant) -> set[str]:
    names: set[str] = set()
    for sub in getattr(dependant, "dependencies", []):
        call = getattr(sub, "call", None)
        if call is not None:
            names.add(getattr(call, "__name__", ""))
        names.update(_dependency_names(sub))
    return names


def test_routes_require_a_session_or_a_named_token() -> None:
    from app.routes import router

    open_routes = []
    for route in router.routes:
        path = getattr(route, "path", "")
        dependant = getattr(route, "dependant", None)
        if dependant is None or path in TOKEN_ROUTES:
            continue
        if "get_current_user" not in _dependency_names(dependant):
            open_routes.append(f"{','.join(getattr(route, 'methods', []) or [])} {path}")
    assert open_routes == []


def test_public_deployment_refuses_local_secrets_and_limits_login(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import enforce_production_secrets, get_settings
    from app.security import clear_login_failures

    get_settings.cache_clear()
    assert get_settings().is_local_runtime is True
    enforce_production_secrets()
    closed = client.post("/messages/send", json={"contact_id": str(uuid.uuid4()), "body": "hello"})
    assert closed.status_code == 401
    monkeypatch.setenv("YES_SALES_ENV", "production")
    monkeypatch.setenv("PRODUCTION_SECRET_GUARD", "false")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="insecure_deployment"):
        enforce_production_secrets()
    try:
        for _ in range(8):
            failed = client.post("/auth/login", json={"email": "founder@yes-sales.test", "password": "wrong-password"})
            assert failed.status_code == 401, failed.text
        limited = client.post("/auth/login", json={"email": "founder@yes-sales.test", "password": "wrong-password"})
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "login_limited"
    finally:
        clear_login_failures()
        monkeypatch.setenv("YES_SALES_ENV", "test")
        get_settings.cache_clear()


def test_sales_floor_files_a_source_and_does_not_send_or_invent(client: TestClient) -> None:
    headers = auth_header(client)
    before = len(client.get("/companies", headers=headers).json()["companies"])
    closed = client.post("/sales-team/run", json={"brief": "Send the quote now"})
    assert closed.status_code == 401
    roster = client.get("/sales-team", headers=headers)
    assert roster.status_code == 200
    agents = {seat["agent"] for seat in roster.json()["seats"]}
    assert agents == {"atlas", "orion", "bengal", "meridian", "hunter", "guard", "alex", "ledger"}
    waiting = client.post(
        "/sales-team/run",
        headers=headers,
        json={"brief": "Look at this mill", "country": "MY", "excerpt": "Company: TEST Floor Mill\nCountry: MY"},
    )
    assert waiting.status_code == 200, waiting.text
    held = waiting.json()
    assert held["research_agent"] == "meridian"
    assert held["sent"] is False
    assert held["verification_trusted"] is False
    assert held["outreach_authorized"] is False
    assert held["price_bound"] is False
    assert held["payment_executed"] is False
    assert held["companies_created"] is False
    assert len(client.get("/companies", headers=headers).json()["companies"]) == before
    company = client.post(
        "/companies",
        headers=headers,
        json={"legal_name": "TEST Floor Mill", "country": "MY", "role": "supplier", "category": "Knitwear", "is_test": True},
    )
    assert company.status_code == 201, company.text
    company_id = company.json()["id"]
    mismatch = client.post(
        "/sales-team/run",
        headers=headers,
        json={
            "brief": "Send the quote now",
            "country": "MY",
            "company_id": company_id,
            "source_url": "https://test-floor.example/about",
            "excerpt": "Company: TEST Someone Else\nCountry: MY",
        },
    )
    assert mismatch.status_code == 200, mismatch.text
    assert mismatch.json()["seats"][0]["status"] == "refused"
    assert mismatch.json()["sent"] is False
    filed = client.post(
        "/sales-team/run",
        headers=headers,
        json={
            "brief": "File the public page. Do not contact them.",
            "country": "MY",
            "company_id": company_id,
            "source_url": "https://test-floor.example/about",
            "excerpt": "Company: TEST Floor Mill\nCountry: MY\nCategory: Knitwear",
        },
    )
    assert filed.status_code == 200, filed.text
    body = filed.json()
    assert body["seats"][0]["status"] == "filed"
    assert body["seats"][0]["verification_status"] == "evidence_recorded"
    assert body["sent"] is False
    assert body["verification_trusted"] is False
    stored = client.get(f"/companies/{company_id}", headers=headers).json()["company"]
    assert stored["verification_status"] == "evidence_recorded"
