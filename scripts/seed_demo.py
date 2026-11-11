"""Create local dev users and one labeled TEST company pair.

Passwords come from DEV_FOUNDER_PASSWORD and DEV_OPERATOR_PASSWORD.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://yes_app:yes_app@127.0.0.1:5432/yes_sales")
os.environ.setdefault("ADMIN_DATABASE_URL", "postgresql+psycopg://yes:yes@127.0.0.1:5432/yes_sales")
os.environ.setdefault("AUTO_MIGRATE", "true")


def upsert_user(session, email: str, full_name: str, role: str, password: str) -> None:
    from sqlalchemy import select

    from app.models import User, UserCredential
    from app.security import hash_password

    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, full_name=full_name, role=role, is_active=True)
        session.add(user)
        session.flush()
        session.add(UserCredential(user_id=user.id, password_hash=hash_password(password)))
        return
    credential = session.get(UserCredential, user.id)
    if credential is None:
        session.add(UserCredential(user_id=user.id, password_hash=hash_password(password)))
    else:
        credential.password_hash = hash_password(password)


def main() -> None:
    from app.config import get_settings
    from app.db import admin_sessionmaker, apply_migrations

    get_settings.cache_clear()
    apply_migrations()
    settings = get_settings()
    with admin_sessionmaker()() as session:
        upsert_user(session, settings.dev_founder_email, "YES SALES Founder", "founder", settings.dev_founder_password)
        upsert_user(session, settings.dev_operator_email, "YES SALES Operator", "operator", settings.dev_operator_password)
        session.commit()
    print("Seeded local users. Company records are created by scripts/simulate_transaction.py and are labeled TEST.")


if __name__ == "__main__":
    main()
