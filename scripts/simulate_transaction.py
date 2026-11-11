"""Run one labeled TEST sourcing transaction against a live API process."""

import os
import uuid

import httpx

API = os.environ.get("API_URL", "http://127.0.0.1:8000")
EMAIL = os.environ.get("DEV_FOUNDER_EMAIL", "founder@yes-sales.test")
PASSWORD = os.environ.get("DEV_FOUNDER_PASSWORD", "change-me-founder")
SUFFIX = uuid.uuid4().hex[:8]


def must(response: httpx.Response) -> dict:
    if response.status_code >= 400:
        raise SystemExit(f"{response.request.method} {response.request.url} -> {response.status_code} {response.text}")
    return response.json()


def main() -> None:
    with httpx.Client(base_url=API, timeout=30) as client:
        login = must(client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}))
        headers = {"Authorization": f"Bearer {login['access_token']}"}
        supplier = must(client.post("/companies", headers=headers, json={
            "legal_name": f"TEST Bengal Mill {SUFFIX}",
            "country": "BD",
            "role": "supplier",
            "category": "Knitwear",
            "website": f"https://test-mill-{SUFFIX}.example",
            "is_test": True,
        }))
        buyer = must(client.post("/companies", headers=headers, json={
            "legal_name": f"TEST Rhine Buyer {SUFFIX}",
            "country": "DE",
            "role": "buyer",
            "category": "Knitwear",
            "is_test": True,
        }))
        for company, url, email in (
            (supplier, f"https://test-mill-{SUFFIX}.example/about", f"mill-{SUFFIX}@example.com"),
            (buyer, f"https://test-buyer-{SUFFIX}.example/about", f"buyer-{SUFFIX}@example.com"),
        ):
            must(client.post("/research/sources", headers=headers, json={
                "company_id": company["id"],
                "source_url": url,
                "excerpt": f"Company: {company['legal_name']}\nCategory: Knitwear",
                "provider": "manual",
            }))
            must(client.post(f"/companies/{company['id']}/contacts", headers=headers, json={
                "full_name": "Public Desk",
                "channel": "email",
                "value": email,
                "allowed": True,
                "authorization_basis": "public_business",
                "consent_for_callback": True,
            }))
        supplier_stages = ["research", "verify", "contact_eligible", "introduction", "response", "qualification"]
        buyer_stages = ["research", "verify", "contact_eligible", "introduction", "response", "requirements", "qualification"]
        for stage in supplier_stages:
            must(client.post(f"/companies/{supplier['id']}/transitions", headers=headers, json={"side": "supplier", "to_stage": stage}))
        for stage in buyer_stages:
            must(client.post(f"/companies/{buyer['id']}/transitions", headers=headers, json={"side": "buyer", "to_stage": stage}))
        must(client.post(f"/companies/{supplier['id']}/verification", headers=headers, json={"status": "verified"}))
        requirement = must(client.post("/buyer-requirements", headers=headers, json={
            "company_id": buyer["id"],
            "product_category": "Knitwear",
            "desired_quantity": "1000",
            "destination_country": "DE",
            "required_certifications": ["OEKO-TEX"],
            "lead_time_days": 40,
            "delivery_terms": "sea",
            "currency": "USD",
            "incoterms": "FOB",
        }))
        opportunity = must(client.post("/opportunities", headers=headers, json={
            "buyer_company_id": buyer["id"],
            "supplier_company_id": supplier["id"],
            "buyer_requirement_id": requirement["id"],
            "title": f"TEST knitwear {SUFFIX}",
            "pipeline_value": "18000",
            "currency": "USD",
        }))
        product = must(client.post("/products", headers=headers, json={"company_id": supplier["id"], "name": "Jersey", "category": "Knitwear"}))
        rfq = must(client.post("/rfqs", headers=headers, json={"buyer_requirement_id": requirement["id"], "opportunity_id": opportunity["id"]}))
        offer = must(client.post("/supplier-offers", headers=headers, json={
            "company_id": supplier["id"],
            "product_id": product["id"],
            "rfq_id": rfq["id"],
            "unit_price": "3.40",
            "currency": "USD",
            "incoterms": "FOB",
            "moq": "500",
            "capacity": "4000",
            "lead_time_days": 30,
            "origin_country": "BD",
            "certifications": ["OEKO-TEX"],
            "delivery_terms": "sea",
        }))
        match = must(client.post("/matches", headers=headers, json={
            "opportunity_id": opportunity["id"],
            "buyer_requirement_id": requirement["id"],
            "supplier_offer_id": offer["id"],
        }))
        agreement = must(client.post("/agreements", headers=headers, json={"opportunity_id": opportunity["id"], "terms": {"label": "TEST"}, "evidence_note": "Unsigned test draft"}))
        approval = must(client.post("/approvals", headers=headers, json={
            "action_type": "sign_agreement",
            "subject_type": "agreement",
            "subject_id": agreement["id"],
            "notes": "TEST approval",
        }))
        must(client.post(f"/approvals/{approval['id']}/decide", headers=headers, json={"decision": "approved", "note": "TEST founder approval"}))
        executed = must(client.post(f"/approvals/{approval['id']}/execute", headers=headers))
        kpis = must(client.get("/dashboard/kpis", headers=headers))
        print("TEST transaction completed")
        print(f"supplier={supplier['id']} buyer={buyer['id']}")
        print(f"match_score={match['score']} confidence_cap={match['confidence_cap']}")
        print(f"agreement_result={executed['result']}")
        print(f"verified_suppliers={kpis['verified_suppliers']} pipeline_value={kpis['pipeline_value']}")
        assert "landed_cost" not in match["explanation"]


if __name__ == "__main__":
    main()
