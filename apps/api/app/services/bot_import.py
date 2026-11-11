import csv
import io
import json
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import audit
from app.errors import DomainError
from app.models import BotImport, User
from app.schemas import CompanyIn
from app.serialize import stamp
from app.services.common import record_usage
from app.services.crm import create_company

RESEARCH_AGENTS = {"bengal", "meridian", "hunter", "orion"}
BLOCKED_STATUS = {"quarantined", "quarantine", "superseded", "rejected", "duplicate"}
READY_STATUS = {"ready", "accepted", "imported", "new", "pending", "verified"}
CLAIMED_STATUS = {"verified", "unverified", "pending", "evidence_recorded"}
ELIGIBILITY = {"eligible", "ineligible", "unknown", "opted_out"}
REQUIRED = (
    "agent_name",
    "task_id",
    "company_identity",
    "company_type",
    "country",
    "product_category",
    "source_urls",
    "verification_date",
    "verification_status",
    "contact_eligibility",
    "source_document_reference",
    "source_excerpt",
    "import_status",
)
ALIASES = {
    "agent": "agent_name",
    "agent_name": "agent_name",
    "task": "task_id",
    "task_id": "task_id",
    "company": "company_identity",
    "company_identity": "company_identity",
    "legal_name": "company_identity",
    "company_type": "company_type",
    "role": "company_type",
    "type": "company_type",
    "country": "country",
    "product_category": "product_category",
    "category": "product_category",
    "source_url": "source_urls",
    "source_urls": "source_urls",
    "verification_date": "verification_date",
    "verification_status": "verification_status",
    "contact_eligibility": "contact_eligibility",
    "source_document": "source_document_reference",
    "source_document_reference": "source_document_reference",
    "source_excerpt": "source_excerpt",
    "excerpt": "source_excerpt",
    "source_text": "source_excerpt",
    "import_status": "import_status",
}


def _public_claim(row: BotImport) -> dict:
    stored = dict(row.claim_evidence or {})
    return {
        "claim_text": stored.get("claim_text") or "",
        "claimed_verification_status": stored.get("claimed_verification_status") or row.claimed_verification_status,
        "evidence_excerpt": None,
        "evidence_status": stored.get("evidence_status") or "held",
        "claim_downgraded": bool(stored.get("claim_downgraded")),
        "stored_as_research_source": False,
        "reason": stored.get("reason") or "Bot claim text is not a source excerpt. The claim stays held.",
    }


def public_import(row: BotImport, replay: bool = False) -> dict:
    claim = _public_claim(row)
    return {
        "id": str(row.id),
        "task_id": row.task_id,
        "agent_name": row.agent_name,
        "company_id": None if row.company_id is None else str(row.company_id),
        "company_identity": row.company_identity,
        "company_type": row.company_type,
        "country": row.country,
        "product_category": row.product_category,
        "source_urls": list(row.source_urls or []),
        "verification_date": None if row.verification_date is None else row.verification_date.isoformat(),
        "claimed_verification_status": row.claimed_verification_status,
        "stored_verification_status": row.stored_verification_status,
        "verification_trusted": False,
        "contact_eligibility": row.contact_eligibility,
        "source_document_reference": row.source_document_reference,
        "import_status": row.import_status,
        "rejection_reason": row.rejection_reason,
        "claim_evidence": claim,
        "evidence_status": claim["evidence_status"],
        "claim_downgraded": claim["claim_downgraded"],
        "stored_as_research_source": False,
        "outreach_authorized": False,
        "idempotent_replay": replay,
        "created_at": stamp(row.created_at),
    }


def rows_from_payload(payload: dict) -> list[dict]:
    if "csv" in payload:
        if not isinstance(payload["csv"], str) or not payload["csv"].strip():
            raise DomainError(422, "import_required", "CSV text is empty.")
        return list(csv.DictReader(io.StringIO(payload["csv"])))
    records = payload.get("records")
    if not isinstance(records, list):
        raise DomainError(422, "import_required", "Provide a records array or csv text.")
    return records


def rows_from_upload(filename: str, content: bytes) -> list[dict]:
    if len(content) > 1_000_000:
        raise DomainError(413, "import_too_large", "Bot import file exceeds 1 MB.")
    text = content.decode("utf-8-sig")
    name = filename.lower()
    if name.endswith(".csv"):
        return rows_from_payload({"csv": text})
    try:
        parsed = json.loads(text or "{}")
    except json.JSONDecodeError as exc:
        raise DomainError(422, "invalid_payload", "Bot import file is not valid JSON.") from exc
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return rows_from_payload(parsed)
    raise DomainError(422, "invalid_payload", "Bot import JSON must be an object or an array.")


def list_imports(session: Session) -> list[BotImport]:
    return list(session.scalars(select(BotImport).order_by(BotImport.created_at.desc()).limit(100)))


def import_records(session: Session, actor: User, rows: list[dict]) -> list[dict]:
    if len(rows) > 200:
        raise DomainError(422, "import_too_large", "A bot import accepts at most 200 records.")
    results = []
    for raw in rows:
        if not isinstance(raw, dict):
            results.append(_rejected_payload("A bot import row must be an object."))
            continue
        results.append(_import_one(session, actor, raw))
    return results


def _rejected_payload(reason: str) -> dict:
    return {
        "import_status": "rejected",
        "rejection_reason": reason,
        "verification_trusted": False,
        "outreach_authorized": False,
        "idempotent_replay": False,
        "company_id": None,
    }


def _import_one(session: Session, actor: User, raw: dict) -> dict:
    fields = _normalize(raw)
    fields["verification_date_parsed"] = _parse_date(fields["verification_date"]) if fields["verification_date"] else None
    existing = _find_existing(session, fields)
    if existing is not None:
        return public_import(existing, replay=True)
    reason = _invalid_reason(fields)
    if reason is not None:
        if not fields["task_id"]:
            return _rejected_payload(reason)
        return public_import(_store_rejection(session, actor, fields, "rejected", reason))
    blocked = _blocked_status(fields)
    if blocked is not None:
        status, why = blocked
        return public_import(_store_rejection(session, actor, fields, status, why))
    try:
        with session.begin_nested():
            row = _accept(session, actor, fields)
            session.flush()
    except DomainError as exc:
        status = "duplicate" if exc.code in {"duplicate_company", "duplicate_source"} else "superseded" if exc.code == "superseded_source" else "rejected"
        return public_import(_store_rejection(session, actor, fields, status, exc.message))
    except IntegrityError:
        replay = _find_existing(session, fields)
        if replay is not None:
            return public_import(replay, replay=True)
        raise
    record_usage(session, "bot-import", "not_configured", "research.bot_import", 0)
    return public_import(row)


def _accept(session: Session, actor: User, fields: dict) -> BotImport:
    identity = fields["company_identity"]
    company = create_company(
        session,
        actor,
        CompanyIn(
            legal_name=identity,
            country=fields["country"],
            role=fields["company_type"],
            category=fields["product_category"],
            summary=(
                f"Imported from {fields['agent_name']} task {fields['task_id']}. "
                f"Bot verification claim: {fields['verification_status']}. "
                "The claim text was not stored as a source excerpt. "
                "Stored verification stays unverified until a person records a source. "
                f"Contact eligibility claim: {fields['contact_eligibility']}. "
                "This import did not authorize outreach."
            ),
            is_test=identity.upper().startswith("TEST"),
        ),
    )
    if company.verification_status != "unverified":
        company.verification_status = "unverified"
    row = BotImport(
        task_id=fields["task_id"],
        agent_name=fields["agent_name"],
        company_id=company.id,
        research_source_id=None,
        company_identity=identity,
        company_type=fields["company_type"],
        country=fields["country"],
        product_category=fields["product_category"],
        source_urls=fields["source_urls"],
        verification_date=fields["verification_date_parsed"],
        claimed_verification_status=fields["verification_status"],
        stored_verification_status=company.verification_status,
        contact_eligibility=fields["contact_eligibility"],
        source_document_reference=fields["source_document_reference"],
        import_status="accepted",
        claim_evidence=_claim_evidence(fields),
    )
    session.add(row)
    session.flush()
    audit(
        session,
        actor,
        "bot_import.accepted",
        "bot_import",
        row.id,
        {
            "task_id": row.task_id,
            "company_identity": row.company_identity,
            "claimed_verification_status": row.claimed_verification_status,
            "verification_trusted": False,
            "stored_as_research_source": False,
            "evidence_status": "held",
        },
    )
    return row


def _store_rejection(session: Session, actor: User, fields: dict, status: str, reason: str) -> BotImport:
    row = BotImport(
        task_id=fields["task_id"],
        agent_name=fields["agent_name"] or "unknown",
        company_identity=fields["company_identity"] or fields["task_id"],
        company_type=fields["company_type"] or "unknown",
        country=fields["country"] or None,
        product_category=fields["product_category"] or None,
        source_urls=fields["source_urls"],
        verification_date=fields["verification_date_parsed"],
        claimed_verification_status=fields["verification_status"] or None,
        stored_verification_status=None,
        contact_eligibility=fields["contact_eligibility"] or None,
        source_document_reference=fields["source_document_reference"] or None,
        import_status=status,
        rejection_reason=reason,
        claim_evidence=_claim_evidence(fields),
    )
    session.add(row)
    session.flush()
    audit(session, actor, "bot_import.rejected", "bot_import", row.id, {"task_id": row.task_id, "import_status": status})
    return row


def _normalize(raw: dict) -> dict:
    mapped: dict = {name: "" for name in REQUIRED}
    for key, value in raw.items():
        name = ALIASES.get(str(key).strip().lower().replace(" ", "_"))
        if name is None or name == "source_urls":
            continue
        mapped[name] = "" if value is None else str(value).strip()
    urls = raw.get("source_urls", raw.get("source_url", raw.get("Source URLs", "")))
    mapped["source_urls"] = _urls(urls)
    mapped["agent_name"] = mapped["agent_name"].lower()
    mapped["company_type"] = mapped["company_type"].lower()
    mapped["country"] = mapped["country"].upper()
    mapped["verification_status"] = mapped["verification_status"].lower()
    mapped["contact_eligibility"] = mapped["contact_eligibility"].lower().replace(" ", "_")
    mapped["import_status"] = mapped["import_status"].lower()
    return mapped


def _urls(value) -> list[str]:
    if isinstance(value, list):
        parts = [str(item).strip() for item in value]
    else:
        parts = [item.strip() for item in str(value or "").replace("|", "\n").splitlines()]
    return [item for item in parts if item]


def _invalid_reason(fields: dict) -> str | None:
    if not fields["task_id"]:
        return "Task ID is required."
    if fields["agent_name"] not in RESEARCH_AGENTS:
        return "Agent must be bengal, meridian, hunter, or orion."
    if len(fields["company_identity"]) < 2:
        return "Company identity is required."
    if fields["company_type"] not in {"supplier", "buyer", "both"}:
        return "Company type must be supplier, buyer, or both."
    if len(fields["country"]) != 2 or not fields["country"].isalpha():
        return "Country must be a 2-letter code."
    if not fields["product_category"]:
        return "Product category is required."
    if not fields["source_urls"] or any(not url.startswith(("http://", "https://")) for url in fields["source_urls"]):
        return "At least one http or https source URL is required."
    if fields["verification_date_parsed"] is None:
        return "Verification date must be YYYY-MM-DD."
    if fields["verification_status"] not in CLAIMED_STATUS | BLOCKED_STATUS:
        return "Verification status is not recognized."
    if fields["contact_eligibility"] not in ELIGIBILITY:
        return "Contact eligibility must be eligible, ineligible, unknown, or opted_out."
    if not fields["source_document_reference"]:
        return "Source document reference is required."
    if not fields["source_excerpt"] or "company:" not in fields["source_excerpt"].lower():
        return "Claim text must include a Company line. It is stored as a claim, not as a source excerpt."
    if fields["company_identity"].lower() not in fields["source_excerpt"].lower():
        return "The claim text does not name this company."
    if not fields["import_status"]:
        return "Import status is required."
    if fields["import_status"] not in READY_STATUS | BLOCKED_STATUS:
        return "Import status is not recognized."
    return None


def _blocked_status(fields: dict) -> tuple[str, str] | None:
    claimed = fields["verification_status"]
    incoming = fields["import_status"]
    if claimed in {"quarantined", "quarantine"} or incoming in {"quarantined", "quarantine"}:
        return "quarantined", "Quarantined bot output was not added to the CRM."
    if claimed == "superseded" or incoming == "superseded":
        return "superseded", "Superseded bot output was not added to the CRM."
    if claimed == "rejected" or incoming in {"rejected", "duplicate"}:
        status = "duplicate" if incoming == "duplicate" else "rejected"
        return status, "The bot file marked this record as not importable."
    return None


def _find_existing(session: Session, fields: dict) -> BotImport | None:
    task_id = fields["task_id"]
    identity = fields["company_identity"]
    if not task_id or not identity:
        return None
    return session.scalar(
        select(BotImport).where(
            BotImport.task_id == task_id,
            func.lower(BotImport.company_identity) == identity.lower(),
            func.coalesce(BotImport.country, "") == fields["country"],
        )
    )


def _claim_evidence(fields: dict) -> dict:
    claimed = fields["verification_status"]
    return {
        "claim_text": fields["source_excerpt"],
        "claimed_verification_status": claimed or None,
        "evidence_excerpt": None,
        "evidence_status": "held",
        "claim_downgraded": claimed in {"verified", "evidence_recorded"},
        "stored_as_research_source": False,
        "reason": "Bot claim text is not a source excerpt. The claim is held and the company stays unverified.",
    }


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
