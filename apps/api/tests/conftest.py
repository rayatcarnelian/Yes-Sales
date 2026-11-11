import os
from collections.abc import Generator

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ["DATABASE_URL"] = "postgresql+psycopg://yes_app:yes_app@127.0.0.1:5432/yes_sales_test"
os.environ["ADMIN_DATABASE_URL"] = "postgresql+psycopg://yes:yes@127.0.0.1:5432/yes_sales_test"
os.environ["APP_DB_PASSWORD"] = "yes_app"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["WEBHOOK_SECRET"] = "test-webhook"
os.environ["SCHEDULER_TOKEN"] = "test-scheduler"
os.environ["VOICE_GATEWAY_TOKEN"] = "test-voice"
os.environ["OUTBOUND_ENABLED"] = "false"
os.environ["XAI_API_KEY"] = ""
os.environ["SMTP_HOST"] = ""
os.environ["SMTP_FROM"] = ""
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["AUTO_MIGRATE"] = "true"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"

from app.config import get_settings
from app.db import admin_sessionmaker, apply_migrations, reset_engines
from app.main import app
from app.models import User, UserCredential
from app.security import hash_password

get_settings.cache_clear()
reset_engines()

TABLES = """
job_card_replies, job_cards, service_sheets, operating_settings, notification_events, webhook_events, audit_events, provider_usage,
agent_runs, tasks, approvals, agreements, commission_records, matches, calls, messages,
conversations, supplier_offers, rfqs, opportunities, buyer_requirements, product_documents,
products, research_sources, contact_permissions, contacts, companies, user_credentials, users
"""


def _ensure_database() -> None:
    conn = psycopg.connect("postgresql://yes:yes@127.0.0.1:5432/postgres", autocommit=True)
    exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = 'yes_sales_test'").fetchone()
    if exists is None:
        conn.execute("CREATE DATABASE yes_sales_test")
    sales = conn.execute("SELECT 1 FROM pg_database WHERE datname = 'yes_sales'").fetchone()
    if sales is None:
        conn.execute("CREATE DATABASE yes_sales")
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    _ensure_database()
    get_settings.cache_clear()
    reset_engines()
    apply_migrations()


@pytest.fixture()
def client(migrated_database: None) -> Generator[TestClient, None, None]:
    del migrated_database
    with admin_sessionmaker()() as session:
        session.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        session.execute(
            text(
                "INSERT INTO operating_settings (id, outbound_paused, budget_ceiling_usd, budget_spent_usd) "
                "VALUES (1, false, 25, 0)"
            )
        )
        founder = User(email="founder@yes-sales.test", full_name="Founder", role="founder", is_active=True)
        operator = User(email="operator@yes-sales.test", full_name="Operator", role="operator", is_active=True)
        session.add(founder)
        session.add(operator)
        session.flush()
        session.add(UserCredential(user_id=founder.id, password_hash=hash_password("test-password")))
        session.add(UserCredential(user_id=operator.id, password_hash=hash_password("test-password")))
        session.commit()
    with TestClient(app) as test_client:
        yield test_client


def auth_header(client: TestClient, email: str = "founder@yes-sales.test") -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": "test-password"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
