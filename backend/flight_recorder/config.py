"""Central configuration, loaded from environment / .env file.

Keeping every tunable in one place means no module hard-codes a key or a path.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ directory (two levels up from this file)
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings sourced from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM (free provider: Groq) ---
    groq_api_key: str = ""
    # 8b-instant has a much larger free-tier daily token budget than 70b and is plenty
    # for this triage task. Override with GROQ_MODEL in .env if you want the 70b model.
    groq_model: str = "llama-3.1-8b-instant"
    # The free tier has a low per-minute token limit (TPM). Let the Groq client retry
    # transient 429s with exponential backoff (it honours the Retry-After header) so a
    # short burst over the limit self-heals instead of failing the whole run.
    groq_max_retries: int = 6
    # A stronger model used for AI analysis (auto-fix RCA, pattern insights) on Groq.
    groq_judge_model: str = "llama-3.3-70b-versatile"
    # Optional INDEPENDENT judge from a different provider (Mistral). When the key is set, the
    # LLM-as-Judge uses Mistral instead of Groq — a genuinely independent reviewer of the agent.
    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"

    # --- Storage ---
    database_path: str = "flight_recorder.db"

    # --- Real Jira integration (optional) ---
    # When all three are set, the agent reads real past tickets from Jira (query_db) and
    # posts a real comment on the ticket (send_notification). Leave blank to use the local
    # mock — the system works fully offline either way.
    jira_base_url: str = ""   # e.g. https://your-domain.atlassian.net
    jira_email: str = ""      # your Atlassian account email
    jira_api_token: str = ""  # from https://id.atlassian.com/manage-profile/security/api-tokens
    jira_project_key: str = ""  # optional: scope searches to one project, e.g. "JSM"

    # --- Audit: secret used to HMAC-sign traces (Bonus 8) ---
    signing_secret: str = "dev-flight-recorder-secret-change-me"

    @property
    def database_file(self) -> Path:
        """Absolute path to the SQLite file."""
        path = Path(self.database_path)
        return path if path.is_absolute() else BACKEND_DIR / path

    @property
    def jira_enabled(self) -> bool:
        """True only when enough is configured to talk to a real Jira."""
        return bool(self.jira_base_url and self.jira_email and self.jira_api_token)


settings = Settings()
