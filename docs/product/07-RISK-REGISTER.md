# 07 — Risk register

**Date:** 3 November 2026  
**Scale:** High / Medium / Low for both likelihood and impact if we continue from the current tree.

| ID | Risk | L | I | What we do now |
| --- | --- | --- | --- | --- |
| R1 | The product grows as a general AI OS and no shop pays | High | High | Strategy is one detailing workflow. M2+ blocked pending a founder yes. |
| R2 | Customer data is added to a single shared workspace | High | High | New product tables require `business_id`. Brokerage tables are not the tenant. |
| R3 | Subscription price sits under model, WhatsApp, and support cost | Medium | High | No unlimited plans. Measure cost before naming a price. RM199 is a hypothesis. |
| R4 | Website chat is the wrong channel for Malaysian detailing shops | High | High | Treat it as an assumption to test. Do not buy WhatsApp infrastructure until a pilot rejects the widget. |
| R5 | Mock email, voice, or WhatsApp is described as live | Medium | High | Keep provider-mode labels. Do not enable outbound without a separate approval. |
| R6 | Default secrets and the localhost password hint ship into a shared deployment | Medium | High | M1 secret guard. Do not expose this tree to the public internet with defaults. |
| R7 | `POST /alex/classify` spends a model key anonymously | Closed on 3 Nov 2026 for new calls | High | Route now requires a bearer token. Census test still required so the next route cannot repeat it. |
| R8 | Admin database role is used as a convenient bypass | Medium | High | Keep admin writes limited to migrations, credentials, and the existing opt-out path. New customer writes use `yes_app`. |
| R9 | JWT in `localStorage` is stolen by any script on the dashboard origin | Medium | High | Move to an httpOnly cookie before the public widget shares a production origin with the dashboard. |
| R10 | No MFA on the owner account | High | Medium | Required before real customer personal data. Not built. |
| R11 | Imported research is treated as verified | Medium | Medium | Current import path does not do this. Keep that rule. It is not the pilot product. |
| R12 | Prompt injection causes a tool to send, quote, or export | Medium | High | Tools stay server-allow-listed. The pilot roles cannot send marketing or set an approved price. |
| R13 | PDPA duties are assumed away | Medium | High | Read the Act and the DPO guideline. Get counsel before the first real enquiry store. Do not claim compliance. |
| R14 | WhatsApp or email is sent without marketing permission | Medium | High | No cold outbound in the pilot. The customer starts the chat. Opt-out pattern from the brokerage app is reused when a channel exists. |
| R15 | Photos of vehicles become an ungoverned file pile | Medium | Medium | Private storage, business-scoped paths, retention, and deletion before photos are a feature. Disk uploads today are not that system. |
| R16 | The task worker is forgotten because it is not a process | Medium | Medium | Acceptable for local use. A pilot needs a supervised loop or an external scheduler with the existing token. |
| R17 | HighLevel, Urable, or Fresha already solve the job well enough | Medium | High | Sell the narrow workflow and the done-for-you setup. Stop if a shop is happy on Urable or Bookedin. |
| R18 | Founder support time is the real product | High | Medium | Pilot success includes onboarding hours. If the second shop needs a rewrite, it is not a template. |
| R19 | Live voice is built because the gateway exists | Medium | Medium | Voice stays deferred. `live_call_verified` is false. |
| R20 | Competitor prices in this folder go stale and get quoted to a customer | Medium | Medium | Baseline is 3 Nov 2026. Re-check the vendor page before quoting. |

## Legal note

R13 and R14 need a qualified adviser. The public PDPA materials checked on 3 Nov 2026 are cited in `05-TARGET-ARCHITECTURE.md`. They are not a compliance certificate.
