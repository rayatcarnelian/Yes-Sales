# Implementation checklist

1. Docs, Docker Compose, SQL migration, API, web, and voice skeletons.
2. Vertical slice: company, contact, buyer requirement, opportunity, founder approval, audit, and unauthorized binding denial.
3. Supplier and buyer pipeline guards.
4. Research evidence, provenance, duplicate rules, and scheduled research tasks.
5. Email adapter, inbound webhook, opt-out, and rate limits.
6. Voice mock session and a Twilio / xAI bridge that stays dark without credentials.
7. Matching, RFQs, quotation versions, and commission records.
8. Command center, CRM, inbox, pipelines, deals, approvals, and agent control.
9. Retry, dead-letter restart, budget ceiling, and global pause.
10. TEST demo transaction.
11. Pytest, ruff, mypy, voice tests, TypeScript check, and web build.
12. Deployment files. Cloud deploy only with credentials and an explicit target.

Status is recorded in `COMPLETION_REPORT.md` after the commands in that file have been run.
