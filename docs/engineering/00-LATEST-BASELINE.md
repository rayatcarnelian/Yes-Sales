# 00 — Latest baseline

**Date:** 12 November 2026  
**Branch:** `s0-security-preflight`  
**Starting point:** `main` at `91a261f`. This note covers the PR #5 review corrections on that branch.  
**Paid providers:** not called. The model test uses a stub HTTP response and the real `yes_sales_test` database.  
**Migrations:** none in this slice. Stored `provider_mode` and usage `mode` stay `live`, `mock`, or `not_configured`.

## Commands

Run after the review corrections. `docker compose up` was not run. Docker is not part of this check; the compose test reads the file.

| Command | Where | Result |
| --- | --- | --- |
| `..\..\.venv\Scripts\python.exe -m pytest -q` | `apps/api` | 25 passed, 1 Starlette deprecation warning, 22.95s |
| `..\..\.venv\Scripts\python.exe -m ruff check app tests` | `apps/api` | All checks passed |
| `..\..\.venv\Scripts\python.exe -m mypy app` | `apps/api` | Success: no issues found in 28 source files |
| `npm run typecheck` | `apps/web` | Exit 0 |
| `npm run build` | `apps/web` | Exit 0. Next.js 15.5.28. 13 pages generated. |
| `npm test` | `apps/voice` | 3 passed. Mock session only. No carrier call. |
| `npm audit --omit=dev` | `apps/web` | Not re-run in this correction pass. The earlier run on 12 November 2026 reported 2 advisories (1 moderate, 1 high) in PostCSS through Next.js. The suggested fix installs Next.js 16. Not applied. |
| `python -m pip_audit` | — | Not run. `pip-audit` is not installed. |

PostgreSQL on port 5432 was already accepting connections for this run.

## Review corrections

- A saved xAI key does not write `configured_unverified` or `model_called` into a CHECK column. A source filed as `xai` stays `not_configured` until extract returns. A mocked successful extract stores `provider_mode=live` and one `provider_usage` row with `mode=live` and cost `0.01`. The next extract is refused with `budget_exceeded` when the ceiling is below that cost, and that second source stays `not_configured`. The integrations screen still says `configured_unverified` when a key is only saved.
- `require_model_budget` runs before the xAI HTTP call for research extract and Alex classify. Usage is recorded as `live` only after that call returns. Classify without a key, or without a database session, stays deterministic and does not call the provider.
- `.env.example` sets `YES_SALES_ENV=production`. Local boot uses `.env.local.example`. Compose publishes `127.0.0.1:5432`, `127.0.0.1:8000`, `127.0.0.1:3000`, and `127.0.0.1:3001` only. The container process still listens on `0.0.0.0` inside its own network. Local and test refuse a non-loopback CORS origin. `YES_SALES_PUBLIC_RELEASE=true` and more than one worker are refused at production startup. The login limiter is capped at 256 keys and 8 stamps per key, expires after 15 minutes, and is still per process, so public release stays blocked.
- Export desk, job-card, and sales-floor tests still pass.

## What was wrong before this branch

- `PRODUCTION_SECRET_GUARD` defaulted off, so a public process could boot with the built-in development passwords.
- A saved `XAI_API_KEY` made the desk say the Grok model was live. No model call had been proven.
- SMTP settings made the integration label say email was live before any delivery receipt.
- Voice credentials used the word live inside the process. The public voice label was already `configured_unverified`, and `live_call_verified` stayed false.
- Login compared passwords only when a user row existed, and a public host had no limit on repeated failures.
- Token comparisons did not all reject a different length before `compare_digest`.
- The login page prefilled the local founder email on every host. The password hint was already limited to `localhost` and `127.0.0.1`.
- The session token still lives in `localStorage`. That is recorded here and is not changed in this slice. Customer-product cookies belong to S1.

No real provider key was found in the files staged for git. `.env` is gitignored. The built-in development passwords remain in source for an explicit local or test process. They are not repeated in this note.

## What this slice changed

- The process defaults to production. `YES_SALES_ENV=local` or `YES_SALES_ENV=test` is required before the built-in passwords are allowed. Setting `PRODUCTION_SECRET_GUARD=false` does not turn the check off.
- Production also refuses a signing secret shorter than 32 characters and a CORS list of `*` or empty.
- Production login stops after 8 failures for the same email and client within 15 minutes, and the failure map cannot grow without bound.
- Dashboard words for Grok, the model, email, and voice stay `not_configured`, `mock`, or `configured_unverified` until there is provider evidence. A completed model call is the row that uses `live`. `live_call_verified` stays false. WhatsApp stays `not_configured`.
- Security headers: `nosniff`, `no-referrer`, `DENY` framing. HSTS is added only when the environment is production.

## Still missing

- A shared login limiter. This process refuses `YES_SALES_PUBLIC_RELEASE` until that exists.
- HttpOnly session cookies and CSRF defence. The founder desk still uses `localStorage`.
- Tenant isolation. S1 has not started.
- A delivery receipt for email. A configured SMTP send can still store `provider_mode=live` after `deliver()` returns. This environment does not turn outbound on.
- Rate limits on routes other than production login.
- The Next.js 16 upgrade that would clear the PostCSS advisories.
- A Python dependency advisory scan.
- A running Docker Compose check. Only the compose file was asserted.

## Rollback

Check out `main`. No migration to undo. To boot this machine, `.env` must contain `YES_SALES_ENV=local`. Without that line the API refuses to start, which is the intended public default.
