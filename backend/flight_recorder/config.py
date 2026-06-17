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

    # --- Storage ---
    database_path: str = "flight_recorder.db"

    # --- Audit: secret used to HMAC-sign traces (Bonus 8) ---
    signing_secret: str = "dev-flight-recorder-secret-change-me"

    @property
    def database_file(self) -> Path:
        """Absolute path to the SQLite file."""
        path = Path(self.database_path)
        return path if path.is_absolute() else BACKEND_DIR / path


settings = Settings()
