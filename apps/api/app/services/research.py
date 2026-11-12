import json
from datetime import UTC

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import get_settings
from app.errors import DomainError
from app.models import Company, ResearchSource, User
from app.serialize import stamp
from app.services.common import normalize_name, now, record_usage, require

EVIDENCE_KEYS = ("company", "website", "email", "phone", "category", "country")


class MockResearchProvider:
    """Returns no companies. It does not invent suppliers or buyers."""

    name = "mock"
    mode = "mock"

    def search(self, query: str, country: str | None) -> list[dict]:
        del query, country
        return []


def parse_evidence(excerpt: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in excerpt.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized = key.strip().lower()
        cleaned = value.strip()
        if normalized in EVIDENCE_KEYS and cleaned:
            found[normalized] = cleaned
    return found


def guard_fields(excerpt: str, fields: dict) -> None:
    haystack = excerpt.lower()
    rejected = []
    for key, value in fields.items():
        if value is None or str(value).strip() == "":
            continue
        if str(value).lower() not in haystack:
            rejected.append(key)
    if rejected:
        raise DomainError(
            422,
            "unsupported_fields",
            "Extraction contained values that are not present in the source text.",
            {"fields": rejected},
        )


def call_xai(excerpt: str, client: httpx.Client) -> dict:
    settings = get_settings()
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {key: {"type": ["string", "null"]} for key in EVIDENCE_KEYS},
        "required": list(EVIDENCE_KEYS),
    }
    response = client.post(
        f"{settings.xai_base_url}/responses",
        headers={"Authorization": f"Bearer {settings.xai_api_key}"},
        json={
            "model": settings.xai_model,
            "store": False,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Extract company facts that appear verbatim in the source. "
                        "Use null for anything not present. Do not infer or complete missing facts."
                    ),
                },
                {"role": "user", "content": excerpt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "company_evidence",
                    "strict": True,
                    "schema": schema,
                }
            },
        },
    )
    response.raise_for_status()
    body = response.json()
    text_out = ""
    for item in body.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text_out = content.get("text") or ""
    if not text_out:
        raise DomainError(502, "xai_empty", "xAI returned no structured text.")
    parsed = json.loads(text_out)
    return {key: value for key, value in parsed.items() if value}


def public_source(row: ResearchSource) -> dict:
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "source_url": row.source_url,
        "source_title": row.source_title,
        "retrieved_at": stamp(row.retrieved_at),
        "excerpt": row.excerpt,
        "provider": row.provider,
        "provider_mode": row.provider_mode,
        "evidence_fields": row.evidence_fields,
        "created_at": stamp(row.created_at),
    }


def _assert_source_identity(company: Company, excerpt: str) -> None:
    named = parse_evidence(excerpt).get("company")
    if company.legal_name.lower() not in excerpt.lower():
        raise DomainError(
            422,
            "identifier_mismatch",
            "The source text does not name this company.",
            {"record_company": company.legal_name},
        )
    if named is None:
        raise DomainError(
            422,
            "identifier_mismatch",
            "The source text needs a Company line that matches this record.",
            {"record_company": company.legal_name},
        )
    if normalize_name(named) != company.normalized_name:
        raise DomainError(
            422,
            "identifier_mismatch",
            "The source names a different company than the record it was attached to.",
            {"source_company": named, "record_company": company.legal_name},
        )
    country = parse_evidence(excerpt).get("country")
    if country and len(country.strip()) == 2 and country.strip().isalpha() and country.strip().upper() != company.country:
        raise DomainError(
            422,
            "identifier_mismatch",
            "The source country does not match the company record.",
            {"source_country": country.strip().upper(), "record_country": company.country},
        )


def record_source(session: Session, actor: User, data) -> ResearchSource:
    company = require(session, Company, data.company_id, "Company")
    if data.provider not in {"manual", "mock", "http", "xai", "bot"}:
        raise DomainError(422, "invalid_provider", "Research provider is not recognized.")
    if not data.excerpt.strip():
        raise DomainError(422, "evidence_required", "A research source requires excerpt evidence.")
    retrieved = data.retrieved_at or now()
    if retrieved.tzinfo is None:
        retrieved = retrieved.replace(tzinfo=UTC)
    _assert_source_identity(company, data.excerpt)
    url = data.source_url.strip()
    other_company_id = session.scalar(
        select(ResearchSource.company_id).where(ResearchSource.source_url == url, ResearchSource.company_id != company.id).limit(1)
    )
    if other_company_id is not None:
        raise DomainError(
            409,
            "duplicate_source",
            "This source URL is already recorded for another company.",
            {"existing_company_id": str(other_company_id)},
        )
    latest = session.scalar(
        select(func.max(ResearchSource.retrieved_at)).where(
            ResearchSource.company_id == company.id,
            ResearchSource.source_url == url,
        )
    )
    if latest is not None:
        latest_utc = latest if latest.tzinfo is not None else latest.replace(tzinfo=UTC)
        if retrieved < latest_utc:
            raise DomainError(
                409,
                "superseded_source",
                "This retrieval is older than a source already stored for the same URL.",
                {"latest_retrieved_at": latest_utc.isoformat()},
            )
    existing_rows = session.scalars(
        select(ResearchSource).where(ResearchSource.company_id == company.id, ResearchSource.source_url == url)
    ).all()
    for existing in existing_rows:
        if existing.retrieved_at.astimezone(UTC).date() == retrieved.astimezone(UTC).date():
            raise DomainError(
                409,
                "duplicate_source",
                "This source URL was already recorded for the company on this UTC date.",
                {"existing_id": str(existing.id)},
            )
    if data.provider == "mock":
        mode = "mock"
    elif data.provider == "bot":
        mode = "not_configured"
    elif data.provider in {"manual", "http"}:
        mode = "live"
    else:
        mode = get_settings().llm_mode
    source = ResearchSource(
        company_id=company.id,
        source_url=url,
        source_title=data.source_title,
        retrieved_at=retrieved,
        excerpt=data.excerpt.strip(),
        provider=data.provider,
        provider_mode=mode,
        evidence_fields={},
    )
    session.add(source)
    session.flush()
    if data.provider in {"manual", "http"} and company.verification_status == "unverified":
        company.verification_status = "evidence_recorded"
    audit(session, actor, "research.recorded", "research_source", source.id, {"url": url, "provider_mode": mode, "company_id": str(company.id)})
    return source


def extract_source(session: Session, actor: User, source_id, client: httpx.Client | None = None) -> ResearchSource:
    source = require(session, ResearchSource, source_id, "Research source")
    if not source.excerpt.strip():
        raise DomainError(422, "evidence_required", "Extraction without evidence is rejected.")
    settings = get_settings()
    if settings.xai_api_key:
        http = client or httpx.Client(timeout=60)
        close_client = client is None
        try:
            fields = call_xai(source.excerpt, http)
            record_usage(session, "xai", "model_called", "research.extract", 0)
        finally:
            if close_client:
                http.close()
        mode = "model_called"
    else:
        fields = parse_evidence(source.excerpt)
        record_usage(session, "evidence-parser", "not_configured", "research.extract", 0)
        mode = "not_configured"
    if not fields:
        raise DomainError(422, "evidence_required", "Extraction without evidence is rejected.")
    guard_fields(source.excerpt, fields)
    source.evidence_fields = fields
    source.provider_mode = mode if settings.xai_api_key else source.provider_mode
    company = require(session, Company, source.company_id, "Company")
    if source.provider in {"manual", "http"} and company.verification_status == "unverified":
        company.verification_status = "evidence_recorded"
    audit(session, actor, "research.extracted", "research_source", source.id, {"fields": sorted(fields), "mode": mode, "company_id": str(company.id)})
    return source
