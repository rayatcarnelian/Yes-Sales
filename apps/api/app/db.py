import uuid
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings, repo_root

_engines: dict[str, Engine] = {}
_sessions: dict[str, sessionmaker] = {}


def _engine(url: str):
    if url not in _engines:
        _engines[url] = create_engine(url, pool_pre_ping=True)
    return _engines[url]


def admin_sessionmaker() -> sessionmaker:
    url = get_settings().admin_database_url
    if url not in _sessions:
        _sessions[url] = sessionmaker(bind=_engine(url), autoflush=False, expire_on_commit=False)
    return _sessions[url]


def app_sessionmaker() -> sessionmaker:
    url = get_settings().database_url
    if url not in _sessions:
        factory = sessionmaker(bind=_engine(url), autoflush=False, expire_on_commit=False)
        _sessions[url] = factory
    return _sessions[url]


@event.listens_for(Session, "after_begin")
def _set_app_context(session: Session, _transaction, connection) -> None:
    actor = session.info.get("actor")
    if actor is not None:
        role = actor.role
        user_id = str(actor.id)
    else:
        role = session.info.get("actor_role", "")
        user_id = session.info.get("actor_id", "")
    connection.execute(text("SELECT set_config('app.role', :role, true)"), {"role": role})
    connection.execute(text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": user_id})


def migration_dir() -> Path:
    return repo_root() / "supabase" / "migrations"


def _admin_psycopg_url() -> str:
    return get_settings().admin_database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _execute_script(conn: psycopg.Connection, path: Path) -> None:
    script = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    for statement in script.split("\n-- ;;\n"):
        statement = statement.strip()
        if statement:
            conn.execute(statement)


def apply_migrations() -> None:
    with psycopg.connect(_admin_psycopg_url(), autocommit=True) as conn:
        for path in sorted(migration_dir().glob("*.sql")):
            version = path.name.split("_", 1)[0]
            applied = False
            try:
                row = conn.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (version,)).fetchone()
                applied = row is not None
            except psycopg.Error:
                conn.rollback()
            if applied:
                continue
            _execute_script(conn, path)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s) ON CONFLICT DO NOTHING", (version,))
        _set_app_password(conn)


def _set_app_password(conn: psycopg.Connection) -> None:
    conn.execute(sql.SQL("ALTER ROLE yes_app PASSWORD {}").format(sql.Literal(get_settings().app_db_password)))


def reset_engines() -> None:
    for engine in _engines.values():
        engine.dispose()
    _engines.clear()
    _sessions.clear()


def system_session() -> Session:
    session = app_sessionmaker()()
    session.info["actor_role"] = "agent"
    session.info["actor_id"] = ""
    return session


def new_id() -> uuid.UUID:
    return uuid.uuid4()
