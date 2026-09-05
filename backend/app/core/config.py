import os

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")


class Settings(BaseSettings):
    """Application configuration settings (Pydantic v2 / pydantic-settings).

    Field names map to environment variables case-insensitively, so
    ``MAX_TXN_AMOUNT_PAISE`` is read from the ``MAX_TXN_AMOUNT_PAISE`` env var
    (or the project ``.env``). All financial-safety limits are expressed in the
    smallest currency unit (paise for INR) to avoid floating-point rounding.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Core / Database
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = "sqlite:///./app.db"
    SQLALCHEMY_ECHO: bool = False
    SECRET_KEY: str = "changeme"

    # ------------------------------------------------------------------ #
    # Legacy Kiosk AI (Hugging Face) — retained for the existing kiosk app
    # ------------------------------------------------------------------ #
    HUGGINGFACE_API_KEY: str = ""
    HF_LLM_MODEL: str = "Qwen/Qwen2.5-7B-Instruct"

    # ------------------------------------------------------------------ #
    # Claude (Anthropic) — powers the Agentic Commerce & Recovery Engine
    # ------------------------------------------------------------------ #
    ANTHROPIC_API_KEY: str = ""
    # Required only for identity-linked (org) API keys, which must name the
    # workspace a request acts in. Leave blank for workspace-scoped keys.
    ANTHROPIC_WORKSPACE_ID: str = ""
    CLAUDE_MODEL: str = "claude-3-5-sonnet-latest"
    CLAUDE_MAX_TOKENS: int = 1024
    # Hard upper bound on agent tool-use turns — a deterministic stopping guard.
    AGENT_MAX_TURNS: int = 8

    # ------------------------------------------------------------------ #
    # Razorpay
    # ------------------------------------------------------------------ #
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    # "live" hits api.razorpay.com; "mock" runs a deterministic in-process
    # simulator so the engine works end-to-end without credentials.
    RAZORPAY_MODE: str = "mock"
    RAZORPAY_BASE_URL: str = "https://api.razorpay.com/v1"
    RAZORPAY_TIMEOUT_SECONDS: float = 15.0

    # ------------------------------------------------------------------ #
    # Payment guardrails (financial safety) — all amounts in paise
    # ------------------------------------------------------------------ #
    MIN_TXN_AMOUNT_PAISE: int = 100          # ₹1
    MAX_TXN_AMOUNT_PAISE: int = 50_000_00     # ₹50,000
    DAILY_CAP_PAISE: int = 200_000_00         # ₹2,00,000
    ALLOWED_CURRENCIES: str = "INR"

    @property
    def allowed_currencies(self) -> set[str]:
        """Return the configured currency allowlist as an uppercase set."""
        return {c.strip().upper() for c in self.ALLOWED_CURRENCIES.split(",") if c.strip()}


# Instantiate a single Settings object for import elsewhere
settings = Settings()
