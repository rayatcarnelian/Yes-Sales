from collections.abc import Generator

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.db import admin_sessionmaker, app_sessionmaker
from app.errors import DomainError
from app.models import User
from app.security import decode_token, load_user, load_user_by_email


def get_current_user(authorization: str | None = Header(default=None)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise DomainError(401, "invalid_token", "Authentication token is required.")
    payload = decode_token(authorization.split(" ", 1)[1].strip())
    with admin_sessionmaker()() as session:
        if payload.get("iss") == "yes-sales-local":
            user = load_user(session, str(payload.get("sub", "")))
        else:
            email = payload.get("email")
            user = load_user_by_email(session, email) if email else None
            if user is None or not user.is_active:
                raise DomainError(403, "user_not_provisioned", "No YES SALES user matches this Supabase account.")
        session.expunge(user)
        return user


def get_db(user: User = Depends(get_current_user)) -> Generator[Session, None, None]:
    session = app_sessionmaker()()
    session.info["actor"] = user
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
