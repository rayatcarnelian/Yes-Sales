import hashlib
import hmac
import os
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import DomainError

PBKDF2_ROUNDS = 200_000
# Not an account password. Used so a missing user takes the same verify path.
DUMMY_PASSWORD_HASH = "pbkdf2_sha256$200000$a0222d55d1faa9354d9a9939cbe21b3c$18509254602ec2f763e1315a5652654485237caaecf9b52d47764252b6a8708c"
_LOGIN_FAILURES: dict[str, list[float]] = {}
LOGIN_WINDOW_SECONDS = 900
LOGIN_FAILURE_LIMIT = 8
LOGIN_BUCKET_LIMIT = 256


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds_text, salt_hex, digest_hex = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds_text))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_token(user_id: uuid.UUID, email: str, role: str) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iss": "yes-sales-local",
        "exp": datetime.now(UTC) + timedelta(minutes=settings.jwt_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        local = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], options={"verify_aud": False})
        if local.get("iss") == "yes-sales-local":
            return local
    except jwt.PyJWTError:
        local = None
    if settings.supabase_jwt_secret:
        try:
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        except jwt.PyJWTError as exc:
            raise DomainError(401, "invalid_token", "Authentication token is invalid.") from exc
    if local is None:
        raise DomainError(401, "invalid_token", "Authentication token is invalid.")
    return local


def sign_webhook(body: bytes) -> str:
    secret = get_settings().webhook_secret.encode()
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def secret_matches(supplied: str | None, expected: str | None) -> bool:
    if not supplied or not expected:
        return False
    left = supplied.strip()
    right = expected.strip()
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def webhook_signature_valid(body: bytes, signature: str | None) -> bool:
    return secret_matches(signature, sign_webhook(body))


def twilio_signature_valid(url: str, params: dict[str, str], signature: str | None) -> bool:
    token = get_settings().twilio_auth_token
    if not token or not signature:
        return False
    material = url + "".join(key + params[key] for key in sorted(params))
    digest = hmac.new(token.encode(), material.encode(), hashlib.sha1).digest()
    import base64

    expected = base64.b64encode(digest).decode()
    return secret_matches(signature, expected)


def _prune_login_failures(moment: float) -> None:
    stale = []
    for bucket, stamps in _LOGIN_FAILURES.items():
        recent = [stamp for stamp in stamps if moment - stamp < LOGIN_WINDOW_SECONDS]
        if recent:
            _LOGIN_FAILURES[bucket] = recent[-LOGIN_FAILURE_LIMIT:]
        else:
            stale.append(bucket)
    for bucket in stale:
        _LOGIN_FAILURES.pop(bucket, None)


def login_is_limited(bucket: str, *, now: float | None = None) -> bool:
    moment = time.time() if now is None else now
    _prune_login_failures(moment)
    return len(_LOGIN_FAILURES.get(bucket, [])) >= LOGIN_FAILURE_LIMIT


def record_login_failure(bucket: str, *, now: float | None = None) -> None:
    moment = time.time() if now is None else now
    _prune_login_failures(moment)
    if bucket not in _LOGIN_FAILURES and len(_LOGIN_FAILURES) >= LOGIN_BUCKET_LIMIT:
        oldest = next(iter(_LOGIN_FAILURES))
        _LOGIN_FAILURES.pop(oldest, None)
    _LOGIN_FAILURES.setdefault(bucket, []).append(moment)


def clear_login_failures(bucket: str | None = None) -> None:
    if bucket is None:
        _LOGIN_FAILURES.clear()
        return
    _LOGIN_FAILURES.pop(bucket, None)


def login_bucket_count() -> int:
    return len(_LOGIN_FAILURES)


def load_user(session: Session, user_id: str):
    from app.models import User

    try:
        parsed = uuid.UUID(user_id)
    except ValueError as exc:
        raise DomainError(401, "invalid_token", "Authentication token is invalid.") from exc
    user = session.get(User, parsed)
    if user is None or not user.is_active:
        raise DomainError(401, "invalid_token", "Authentication token is invalid.")
    return user


def load_user_by_email(session: Session, email: str):
    from app.models import User

    return session.scalar(select(User).where(User.email == email.lower()))
