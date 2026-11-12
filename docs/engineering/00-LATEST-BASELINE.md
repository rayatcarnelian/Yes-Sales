# 00 — Latest baseline

**Date:** 12 November 2026  
**Branch:** `s0-security-preflight`  
**Starting point:** `main` at `91a261f`, clean working tree. No migrations in this slice.  
**Paid providers:** not called.

## Commands

Run from the paths below. Results are for this branch after the S0 changes.

| Command | Where | Result |
| --- | --- | --- |
| `..\..\.venv\Scripts\python.exe -m pytest -q` | `apps/api` | 22 passed, 1 Starlette deprecation warning, 31.84s |
| `..\..\.venv\Scripts\python.exe -m ruff check app tests` | `apps/api` | All checks passed |
| `..\..\.venv\Scripts\python.exe -m mypy app` | `apps/api` | Success, 28 source files. The first run failed at `sales_team.py:195` (a research seat dict typed itself as strings, then stored a source object). That annotation was fixed and mypy was run again. |
| `npm run typecheck` | `apps/web` | Exit 0 |
| `npm run build` | `apps/web` | Exit 0. Next.js 15.5.28. 13 pages generated. |
| `npm test` | `apps/voice` | 3 passed. Mock session only. No carrier call. |
| `npm audit --omit=dev` | `apps/web` | 2 advisories (1 moderate, 1 high) in PostCSS through Next.js. The suggested fix installs Next.js 16, a breaking upgrade. Not applied in this slice. |
| `python -m pip_audit` | — | Not run. `pip-audit` is not installed. |

PostgreSQL had to be started from `E:\M sales\.tools\pgsql` before pytest. The first pytest attempt failed because nothing was accepting connections on port 5432.

## What was wrong

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
- Production login stops after 8 failures for the same email and client within 15 minutes.
- Dashboard words for Grok, the model, email, and voice stay `not_configured`, `mock`, or `configured_unverified` until there is provider evidence. `live_call_verified` stays false. WhatsApp stays `not_configured`.
- Security headers: `nosniff`, `no-referrer`, `DENY` framing. HSTS is added only when the environment is production.
- Existing export, job-card, and sales-floor tests still pass. No table was changed.

## Still missing

- HttpOnly session cookies and CSRF defence. The founder desk still uses `localStorage`.
- Tenant isolation. S1 has not started.
- A delivery receipt for email. A configured SMTP send can still store `provider_mode=live` after `deliver()` returns. This environment does not turn outbound on.
- Rate limits on routes other than production login.
- The Next.js 16 upgrade that would clear the PostCSS advisories.
- A Python dependency advisory scan.

## Rollback

Check out `main`. No migration to undo. To boot this machine, `.env` must contain `YES_SALES_ENV=local`. Without that line the API refuses to start, which is the intended public default.
