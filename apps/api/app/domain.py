from app.errors import DomainError

SUPPLIER_STAGES = [
    "discover",
    "research",
    "verify",
    "contact_eligible",
    "introduction",
    "response",
    "qualification",
    "catalog",
    "quotation",
    "agreement_review",
    "active_supplier",
]

BUYER_STAGES = [
    "discover",
    "research",
    "verify",
    "contact_eligible",
    "introduction",
    "response",
    "requirements",
    "qualification",
    "match",
    "rfq",
    "deal",
]

BINDING_ACTIONS = {
    "sign_agreement",
    "bind_price",
    "bind_commission",
    "payment",
    "banking_change",
    "legal_declaration",
    "share_restricted",
    "send_outreach",
}

AGENT_TOOLS = {
    "atlas": {"enqueue_task", "read_kpis"},
    "orion": {"record_source", "extract_source"},
    "bengal": {"record_source", "extract_source"},
    "meridian": {"record_source", "extract_source"},
    "hunter": {"record_source", "extract_source"},
    "alex": {"send_message", "classify_message", "request_callback", "draft_reply", "schedule_followup"},
    "ledger": {"record_offer", "record_commission_draft"},
    "guard": {"validate_extraction", "audit"},
}

AGENT_COUNTRY = {
    "bengal": "BD",
    "meridian": "MY",
}


def assert_transition(stages: list[str], current: str | None, target: str) -> None:
    if current not in stages or target not in stages:
        raise DomainError(409, "illegal_transition", "Unknown pipeline stage.")
    expected = stages[stages.index(current) + 1] if stages.index(current) + 1 < len(stages) else None
    if target != expected:
        raise DomainError(
            409,
            "illegal_transition",
            f"Cannot move from {current} to {target}. The next stage is {expected or 'none'}.",
        )


def assert_tool(agent: str, tool: str) -> None:
    allowed = AGENT_TOOLS.get(agent)
    if allowed is None:
        raise DomainError(404, "unknown_agent", f"Unknown agent {agent}.")
    if tool not in allowed:
        raise DomainError(
            403,
            "tool_forbidden",
            f"{agent} cannot call {tool}.",
            {"allowed": sorted(allowed)},
        )
