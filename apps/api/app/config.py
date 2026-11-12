from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "supabase" / "migrations" / "0001_init.sql").exists():
            return candidate
    raise FileNotFoundError("Could not locate supabase/migrations/0001_init.sql")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(repo_root() / ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://yes_app:yes_app@127.0.0.1:5432/yes_sales"
    admin_database_url: str = "postgresql+psycopg://yes:yes@127.0.0.1:5432/yes_sales"
    app_db_password: str = "yes_app"
    jwt_secret: str = "dev-only-change-me"
    jwt_ttl_minutes: int = 720
    webhook_secret: str = "dev-webhook-secret"
    scheduler_token: str = "dev-scheduler-token"
    voice_gateway_token: str = "dev-voice-token"
    outbound_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    xai_api_key: str = ""
    xai_model: str = "grok-4.7"
    grok_bot_token: str = ""
    xai_base_url: str = "https://api.x.ai/v1"
    xai_realtime_url: str = "wss://api.x.ai/v1/realtime"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    public_voice_host: str = ""
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    cors_origins: str = "http://localhost:3000"
    auto_migrate: bool = True
    upload_dir: str = "data/uploads"
    dev_founder_email: str = "founder@yes-sales.test"
    dev_founder_password: str = "change-me-founder"
    dev_operator_email: str = "operator@yes-sales.test"
    dev_operator_password: str = "change-me-operator"
    # Public deployment is the default. Local and test must opt in.
    yes_sales_env: str = "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def email_live(self) -> bool:
        return bool(self.outbound_enabled and self.smtp_host and self.smtp_from)

    @property
    def environment(self) -> str:
        return self.yes_sales_env.strip().lower()

    @property
    def is_local_runtime(self) -> bool:
        return self.environment in {"local", "test"}

    @property
    def llm_mode(self) -> str:
        # A saved key is not evidence that a model call succeeded.
        return "configured_unverified" if self.xai_api_key else "not_configured"

    @property
    def voice_configured(self) -> bool:
        return bool(self.xai_api_key and self.twilio_auth_token and self.twilio_phone_number)

    @property
    def voice_mode(self) -> str:
        return "configured_unverified" if self.voice_configured else "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()


_LOCAL_DEFAULTS = {
    "jwt_secret": "dev-only-change-me",
    "webhook_secret": "dev-webhook-secret",
    "scheduler_token": "dev-scheduler-token",
    "voice_gateway_token": "dev-voice-token",
    "dev_founder_password": "change-me-founder",
    "dev_operator_password": "change-me-operator",
    "app_db_password": "yes_app",
}


def enforce_production_secrets() -> None:
    """Refuse known local secrets unless this process is explicitly local or test.

    PRODUCTION_SECRET_GUARD is not a bypass. A public deployment that forgets
    YES_SALES_ENV still lands on the production default and stops.
    """
    settings = get_settings()
    if settings.is_local_runtime:
        return
    failures: list[str] = []
    for name, default in _LOCAL_DEFAULTS.items():
        if getattr(settings, name) == default:
            failures.append(name)
    for name in ("database_url", "admin_database_url"):
        value = getattr(settings, name)
        if "yes:yes@" in value or "yes_app:yes_app@" in value:
            failures.append(name)
    for name in ("jwt_secret", "webhook_secret", "scheduler_token", "voice_gateway_token"):
        if len(getattr(settings, name).strip()) < 32:
            failures.append(name)
    if "*" in settings.cors_origin_list or not settings.cors_origin_list:
        failures.append("cors_origins")
    if failures:
        names = ", ".join(sorted(set(failures)))
        raise RuntimeError(f"insecure_deployment refused local defaults: {names}")
