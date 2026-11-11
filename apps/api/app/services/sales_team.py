"""One sales floor. The seats are the agents already in this desk.

A world-class floor separates research, compliance, writing, the deal desk,
and the manager. This play does the same. It files a source only when the
founder already opened the company and pasted text that names it. It does not
create a company, verify one, bind a price, take a payment, or send.
"""

import uuid

from sqlalchemy.orm import Session

from app.audit import audit
from app.domain import AGENT_COUNTRY
from app.errors import DomainError
from app.models import Company, User
from app.schemas import SourceIn
from app.services.alex import classify_message
from app.services.orchestration import dashboard
from app.services.research import extract_source, parse_evidence, public_source, record_source

ROSTER = [
    {
        "seat": "manager",
        "agent": "atlas",
        "job": "Reads the board and names the next human step. Does not send or close.",
    },
    {
        "seat": "research_lead",
        "agent": "orion",
        "job": "Files a source when no country desk owns the account.",
    },
    {
        "seat": "bangladesh",
        "agent": "bengal",
        "job": "Files a source for a Bangladesh account.",
    },
    {
        "seat": "malaysia",
        "agent": "meridian",
        "job": "Files a source for a Malaysia account.",
    },
    {
        "seat": "new_market",
        "agent": "hunter",
        "job": "Files a source for a country outside Bangladesh and Malaysia.",
    },
    {
        "seat": "compliance",
        "agent": "guard",
        "job": "Keeps a fact only when that fact is written in the source text.",
    },
    {
        "seat": "sdr",
        "agent": "alex",
        "job": "Classifies the brief. The send stays with the founder.",
    },
    {
        "seat": "deal_desk",
        "agent": "ledger",
        "job": "Holds price, commission, and payment until the founder executes them.",
    },
]


def roster() -> dict:
    return {
        "name": "YES SALES floor",
        "seats": ROSTER,
        "sent": False,
        "verification_trusted": False,
        "outreach_authorized": False,
        "price_bound": False,
        "payment_executed": False,
        "companies_created": False,
    }


def research_agent(country: str | None) -> str:
    if country == "BD":
        return "bengal"
    if country == "MY":
        return "meridian"
    if country:
        return "hunter"
    return "orion"


def run_play(
    session: Session,
    actor: User,
    brief: str,
    country: str | None,
    excerpt: str,
    company_id: uuid.UUID | None,
    source_url: str,
) -> dict:
    clean_country = _country(country)
    agent = research_agent(clean_country)
    if clean_country and AGENT_COUNTRY.get(agent) not in {None, clean_country}:
        raise DomainError(422, "country_mismatch", "That research seat does not own this country.")
    research = _research(session, actor, agent, excerpt, company_id, source_url)
    compliance = _compliance(excerpt)
    sdr = _sdr(brief)
    deal = _deal_desk()
    manager = _manager(session, research, sdr)
    result = {
        "research_agent": agent,
        "seats": [research, compliance, sdr, deal, manager],
        "next_step": manager["next_step"],
        "sent": False,
        "verification_trusted": False,
        "outreach_authorized": False,
        "price_bound": False,
        "payment_executed": False,
        "companies_created": False,
        "live_model_called": bool(sdr.get("live_model_called")),
    }
    audit(
        session,
        actor,
        "sales_team.ran",
        "company",
        company_id,
        {
            "research_agent": agent,
            "research_status": research["status"],
            "sent": False,
            "verification_trusted": False,
            "outreach_authorized": False,
            "price_bound": False,
        },
    )
    return result


def _country(country: str | None) -> str | None:
    if country is None or not str(country).strip():
        return None
    cleaned = str(country).strip().upper()
    if len(cleaned) != 2 or not cleaned.isalpha():
        raise DomainError(422, "invalid_country", "Country must be two letters.")
    return cleaned


def _research(
    session: Session,
    actor: User,
    agent: str,
    excerpt: str,
    company_id: uuid.UUID | None,
    source_url: str,
) -> dict:
    seat = {"seat": "research", "agent": agent}
    text = excerpt.strip()
    if company_id is None:
        seat["status"] = "waiting"
        seat["message"] = "Open the company first. This floor does not create companies."
        return seat
    if not text:
        seat["status"] = "waiting"
        seat["message"] = "Paste source text that names the company. This floor does not invent suppliers."
        return seat
    if not source_url.strip():
        seat["status"] = "refused"
        seat["code"] = "source_url_required"
        seat["message"] = "Add the page address the text came from."
        return seat
    company = session.get(Company, company_id)
    if company is None:
        seat["status"] = "refused"
        seat["code"] = "not_found"
        seat["message"] = "That company is not on this desk."
        return seat
    try:
        source = record_source(
            session,
            actor,
            SourceIn(
                company_id=company.id,
                source_url=source_url.strip(),
                source_title=f"{agent} floor note",
                excerpt=text,
                provider="manual",
            ),
        )
        extracted = extract_source(session, actor, source.id)
    except DomainError as exc:
        seat["status"] = "refused"
        seat["code"] = exc.code
        seat["message"] = exc.message
        return seat
    seat["status"] = "filed"
    seat["message"] = "The source is filed. The company is not verified, and nobody was contacted."
    seat["source"] = public_source(extracted)
    seat["verification_status"] = company.verification_status
    return seat


def _compliance(excerpt: str) -> dict:
    text = excerpt.strip()
    if not text:
        return {
            "seat": "compliance",
            "agent": "guard",
            "status": "waiting",
            "message": "There is no source text to check.",
        }
    fields = parse_evidence(text)
    return {
        "seat": "compliance",
        "agent": "guard",
        "status": "passed" if fields else "waiting",
        "fields": fields,
        "message": "Only values written in the source are kept." if fields else "The source has no Company, country, or category line.",
    }


def _sdr(brief: str) -> dict:
    classified = classify_message(brief)
    return {
        "seat": "sdr",
        "agent": "alex",
        "status": "held",
        "classification": classified["classification"],
        "provider_mode": classified["provider_mode"],
        "live_model_called": classified["live_model_called"],
        "sent": False,
        "message": "The brief is classified. Nothing was sent.",
    }


def _deal_desk() -> dict:
    return {
        "seat": "deal_desk",
        "agent": "ledger",
        "status": "held",
        "price_bound": False,
        "payment_executed": False,
        "message": "Price, commission, and payment stay on Approvals until you execute them.",
    }


def _manager(session: Session, research: dict, sdr: dict) -> dict:
    board = dashboard(session)
    if sdr["classification"] in {"opt_out", "human_handoff"}:
        step = "A person takes this brief. Nothing is sent."
    elif research["status"] == "refused":
        step = "Correct the source, then run the floor again. Nobody is contacted meanwhile."
    elif research["status"] == "waiting":
        step = "Open the company and paste the page that names it, then run the floor again."
    else:
        step = "Read the filed source on the company. Approve any send yourself."
    return {
        "seat": "manager",
        "agent": "atlas",
        "status": "ready",
        "next_step": step,
        "deals_requiring_approval": board["deals_requiring_approval"],
        "message": step,
    }
