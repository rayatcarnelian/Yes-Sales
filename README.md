# YES SALES

The founder's export desk and a detailing job-card desk, in one application.

The sales floor is Atlas, Orion, Bengal, Meridian, Hunter, Guard, Alex, and Ledger. Run it from Sales team. The floor files a source only for a company you already opened. It does not create a company, verify one, bind a price, take a payment, or send.

## Run locally

PostgreSQL must be listening on port 5432. Copy `.env.example` to `.env` and leave the live keys blank until you have them.

```text
apps/api:  .venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
apps/web:  npm run dev -- --port 3000
```

Open http://localhost:3000 and sign in with the local founder shown on the login page.

`.env` must set `YES_SALES_ENV=local` on this machine. A process without that setting is treated as production and will not start on the built-in passwords.

## Tests

```text
cd apps/api
..\.venv\Scripts\python.exe -m pytest -q
```
