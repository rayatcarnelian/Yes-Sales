"""Run the fictional TEST commercial audit in the isolated staging database.

From the repository root:

    python scripts/run_commercial_audit.py

The run writes audit/commercial-audit.json and stores the same cases in
yes_sales_staging. It does not use the operating database and it does not
place a phone call or send live email.
"""

import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

os.environ["DATABASE_URL"] = "postgresql+psycopg://yes_app:yes_app@127.0.0.1:5432/yes_sales_staging"
os.environ["ADMIN_DATABASE_URL"] = "postgresql+psycopg://yes:yes@127.0.0.1:5432/yes_sales_staging"
os.environ["APP_DB_PASSWORD"] = "yes_app"
os.environ["JWT_SECRET"] = "staging-audit-secret"
os.environ["WEBHOOK_SECRET"] = "staging-webhook"
os.environ["SCHEDULER_TOKEN"] = "staging-scheduler"
os.environ["VOICE_GATEWAY_TOKEN"] = "staging-voice"
os.environ["OUTBOUND_ENABLED"] = "false"
os.environ["XAI_API_KEY"] = ""
os.environ["SMTP_HOST"] = ""
os.environ["SMTP_FROM"] = ""
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["TWILIO_PHONE_NUMBER"] = ""
os.environ["AUTO_MIGRATE"] = "true"


def ensure_database() -> None:
    connection = psycopg.connect("postgresql://yes:yes@127.0.0.1:5432/postgres", autocommit=True)
    exists = connection.execute("SELECT 1 FROM pg_database WHERE datname = 'yes_sales_staging'").fetchone()
    if exists is None:
        connection.execute("CREATE DATABASE yes_sales_staging")
    connection.close()


def seed_users() -> None:
    from sqlalchemy import select

    from app.db import admin_sessionmaker
    from app.models import User, UserCredential
    from app.security import hash_password

    with admin_sessionmaker()() as session:
        for email, name, role in (
            ("founder@yes-sales.test", "Staging Founder", "founder"),
            ("operator@yes-sales.test", "Staging Operator", "operator"),
        ):
            user = session.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(email=email, full_name=name, role=role, is_active=True)
                session.add(user)
                session.flush()
                session.add(UserCredential(user_id=user.id, password_hash=hash_password("test-password")))
        session.commit()


def main() -> None:
    ensure_database()
    from app.config import get_settings
    from app.db import apply_migrations, reset_engines
    from app.main import app
    from app.services.commercial_audit import execute_commercial_audit
    from fastapi.testclient import TestClient

    get_settings.cache_clear()
    reset_engines()
    apply_migrations()
    seed_users()
    with TestClient(app) as client:
        report = execute_commercial_audit(client, write_report=True)
    print(f"status={report['status']} database={report['database_name']} run_id={report['run_id']}")
    for case in report["cases"]:
        print(f"{case['status']:8} {case['code']}")
    print(f"evidence={report['evidence_file']}")


if __name__ == "__main__":
    main()
