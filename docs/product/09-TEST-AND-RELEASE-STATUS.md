# 09 — Test and release status

**Date:** 3 November 2026  
**Environment:** Local Windows workstation. PostgreSQL on `127.0.0.1:5432`. No `.env` overrides were required for the suite; `conftest.py` sets the test database and blank provider keys.

## Commands run in this review

| Command | Result |
| --- | --- |
| `.venv\Scripts\python -m pytest apps\api\tests -q` | **16 passed**, 1 Starlette deprecation warning, 15.35s. Re-run after the classify auth change. |
| `.venv\Scripts\python -m ruff check apps\api\app\routes.py apps\api\tests\test_acceptance.py` | Passed. |
| `npm test` in `apps\voice` | **3 passed**. Mock session only. No call placed. |

## Not run in this review

| Command | Why it matters |
| --- | --- |
| `npm run typecheck` and `npm run build` in `apps/web` | Last recorded in `AUDIT-STATUS.md` on 2 Nov 2026 as exit 0. Not repeated today. |
| `mypy`, full `ruff` on the whole API | Not run today. |
| `scripts/run_commercial_audit.py` | Not run. Older JSON under `audit/` is not today's evidence. |
| Docker Compose | Not run. |
| Browser walkthrough of the command center | Not run. Prior notes describe one. This review does not reuse that as a fresh pass. |
| Live SMTP, xAI, Twilio, WhatsApp, Supabase | No credentials used. Those integrations are not live. |

## Change included in the 16 passing tests

`POST /alex/classify` without a bearer token returns 401. `test_scheduler_token_and_login` asserts that. The authenticated classification assertion in `test_alex_draft_approval_context_and_unverified_voice` still passes and still records `live_model_called: false`.

## Release state

| Surface | State |
| --- | --- |
| Local API against `yes_sales_test` | Tests passed, as above |
| Local web production build | Not re-verified today |
| Voice | Mock tests passed. Live carrier not configured and not verified |
| Staging or production deployment | None verified |
| Customer pilot | None |

## Known gaps the suite does not close

- No test joins two tenants, because tenants do not exist.
- The WhatsApp 501 branch is not the assertion in `test_outreach_permission_opt_out_and_pause`. That test sends WhatsApp while outbound pause is on and expects 409.
- `live_call_verified` is not proven by placing a call.
- Web UI regressions are not in CI here.
- The suite's database passwords and JWT secret are intentional test values in `conftest.py`. They are not a production configuration.

## Blockers before any external user

1. Founder decision on the data split (`08-DECISION-LOG.md`).
2. Secret guard and no public deploy on default secrets.
3. MFA, privacy notice, and a real retention story before customer personal data.
4. A pilot who has agreed. None has been verified in this repository.
