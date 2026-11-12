# YES SALES QuoteDesk — Cursor Execution Plan / Acceptance Gates
Date: 12 November 2026
Status: engineering task queue; not evidence that implementation has begun
References: docs/product/11-QUOTEDESK-MARKET-DECISION.md and docs/product/12-QUOTEDESK-PRD-ARCHITECTURE.md
Existing code: Next.js 15 / FastAPI / PostgreSQL / SQLAlchemy / tests / migrations / approvals and audit. Keep one deployable monolith.
Source branch for this specification: product/quotedesk-mvp-blueprint

## Operating protocol for Cursor
Read all three new documents, previous docs/product/05-TARGET-ARCHITECTURE.md, current app source, migrations and tests. Independently verify them; don't blindly trust previous audit notes. Check git status; do not overwrite worktrees, clean untracked files, reset history, expose secrets, or push secret-bearing files.
Implement ONE slice per small feature branch from current main, PR to main, with tests and screenshots or concise UI walkthrough. No automatic merge. Reuse existing patterns when safe, but do not reuse the old brokerage tenant model. On each PR report commit SHA, tests actually run, features actually live/mock/missing, scope changed, risks and next slice. Refuse attempts to start all slices simultaneously or call paid models in a loop.

## Stage S0 — Preflight and blocker audit
- Run API pytest, full ruff, mypy, frontend tsc/build, voice mock tests where environment supports. Label missing commands as not run rather than passed.
- Inventory routes/permissions; ensure all operations with spending, data changes or business records authenticated/authorized.
- Audit public repo for committed secrets; rotate any leaked real credentials out of band. Remove hardcoded production-capable passwords; production secret guard must be enforced by deployment config, not an optional toggle defaulting off. Verify CORS, CSRF, session storage, rate-limit needs, audit writes.
- Do not publicly deploy the current default-secret founder desk. Existing web uses localStorage token; migrate to secure auth for customer product before release.
- Output docs/engineering/00-LATEST-BASELINE.md with exact commands and known failures, no confidential values.
Exit: existing suite reproducible, blockers documented, rollback strategy known.

## Stage S1 — Tenant foundation (PR 1)
- Add business, memberships, business_settings and related session/business context plumbing, separate from old companies.
- Implement auth/session strategy secure-cookie + CSRF for business routes, verified membership RBAC and database transaction app.business_id.
- Add FORCE RLS + scoped composite FKs for all customer-domain tables as each table lands; explicit non-tenant tests and cross-tenant tests including SQL-level restrictions.
- Add authenticated workspace selection and small settings/profile UI. Founder can create an internal YES SALES business workspace. Existing export and job-card pages unchanged.
- Tests for owner/staff/unauthorized/anonymous, business A cannot see/modify B in routes or SQL, default production secrets forbidden.
Exit: hardened business boundary, no external customer data yet.

## Stage S2 — Enquiry intake + owner queue (PR 2)
- New customer, source, enquiry, message, answer, action and audit tables, scoped to business.
- Public intake form URL and embed snippet, with business routing key, rate limit, size checks, idempotency, anti-spam, minimal PII and privacy notice.
- Owner manual import/paste of EXISTING inbound requests with explicit source label (not invented live integration). Dedup and opt-out flags.
- Today/Enquiries/detail UI desktop and mobile: received, needs_info, qualified, quote_pending, quote_ready, won/lost. Owner creates an action/reminder and can view source timeline.
- No AI necessary in this phase. Build deterministic missing-fields questions from service template.
Exit: two synthetic enquiries enter two separate workspaces without leaking; owner finds, qualifies and adds next action.

## Stage S3 — Quote/approval/proposal loop (PR 3)
- Approved catalog and question templates, price approval rule, quotes/revisions/line items, required quote approvals and immutable version snapshots.
- User can build proposal from sourced requirements, add exclusions and payment/timeline terms, explicitly approve an exact version, print/export PDF, and log a manual share event as "shared manually, delivery unconfirmed".
- Follow-up task list with due dates and completed actions; allow won/lost with evidence notes.
- Dashboard calculates factual counts only; actual collected revenue requires explicit verified record, not pipeline value.
Exit: 1 enquiry to approved printable proposal and next action with comprehensive audit, no fabricated quote/delivery.

## Stage S4 — Bounded AI assist (PR 4)
- Structured model adapter with provider_mode mock/not_configured/live and tenant budget controls (off by default).
- AI suggests requirement extraction with evidence-linked spans, missing questions, proposal outline and short reply draft. Owner reviews before data becomes confirmed.
- No price computation from language model. Validate guardrails in code and approved price policy. If a source span is missing, mark field unverified and request human review.
- 20 synthetic+redacted consented scenarios: incomplete requirements, two languages, ambiguity, prompt injection, false deadlines, price bluff, duplicate data, opt-outs, redirection to human. Log evaluation outcomes and costs. No uncontrolled Grok bot sync.
Exit: accuracy and critical error report with explicit fails. Failure to meet guardrails blocks launch, not replaced by a model marketing claim.

## Stage S5 — Internal real-world validation (PR 5 / process gate)
- Founder uses YES SALES digital services to process real, appropriately obtained inbound project requests. Compare manual vs AI-assisted handling for at least 20 historical redacted enquiries where feasible. If insufficient actual samples, report sample size and don't claim statistically significant uplift.
- 3–5 business interviews, at least one signed voluntary external pilot agreement (including data processing/consent terms) before deploying a subscriber workspace.
- Track owner work minutes, missing-brief rate, quote turnaround, follow-up completion, errors, cost and customer conversion.
- Public multi-tenant deploy only after security/backup/restore/privacy/incident response gates and explicit founder acceptance.
Exit: local demo complete, production-safe pilot criteria met, costs recorded; external SaaS claims only after live verification.

## Stage S6 — Conditional next release (not pre-authorized)
Official WhatsApp Business inbound if pilot specifically needs it, OR authenticated inbound business email if faster and permitted. Add one channel, not three. Require authenticated webhooks, message idempotency, provider failure tests, opt-out, tenant quota, human handoff and accurate delivery state. Do not add paid phone or provider integration merely to fill a feature matrix.

## Build vs integrate
BUILD: business-scoped intake, evidence-linked requirements, missing question engine, approval rules, quote state/versioning, owner queue, minimal UI, audit, analytics.
INTEGRATE IF DEMANDED: identity auth provider, S3-like private media, email, Meta WhatsApp Business Platform, calendar, payment, e-signature.
DEFER: visual agent office, nine agents, voice, broad outbound automation, full CRM suite, inventory/ERP, marketplace, invoice tax compliance, public no-code agent builder.

## Release checklist to include on EVERY PR
[ ] New tables RLS and business-scope tests
[ ] API validation, approval and error tests
[ ] No secrets or credentials introduced
[ ] No regression in founder export/job-card workflows
[ ] No paid provider called in automated CI
[ ] Demonstration with fictional TEST data; truthful LIVE/MOCK labels
[ ] Mobile 360px, keyboard navigation, useful empty/error/loading states
[ ] Audit entries for consequential actions
[ ] Manual API + UI walkthrough actually executed, or explicitly not run
[ ] Tests command, output and commit recorded
[ ] Rollback or feature-flag plan
[ ] PR left for review, no auto-merge

## Decision / kill gates
- If a credible external pilot cannot be found with a painful quote-workflow problem, stop speculative expansion. Do not build a generic SaaS.
- If quotes cannot be made accurately with approved rules and a human, keep quotes drafted only.
- If channel costs and support time exceed expected subscription margin, charge setup fee or change product scope instead of claiming unlimited usage.
- If no secure multi-tenancy, DO NOT onboard external paying businesses.
- If existing research proves a prospect is already well served by an incumbent, do not build a clone for them.
- OpenAI selection/accreditation is never a success criterion or claim; customers, sound engineering and measured utility are.
