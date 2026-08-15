"""Application settings, loaded from environment / .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Korea Job Finder"

    # sqlite file lives next to the backend package; created automatically on boot
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'korea_jobs.db').as_posix()}"

    # CORS origins for the Vite dev server
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Networking
    request_timeout: float = 10.0
    collector_timeout: float = 20.0
    max_results_per_collector: int = 50
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 KoreaJobFinder/1.0"
    )

    # Official open-API keys. Collectors that need one report themselves as
    # unavailable when the key is missing - they never try to work around it.
    saramin_api_key: str = ""
    work24_api_key: str = ""

    # Sample data is OFF by default. A source that is unconfigured or failing
    # reports the real reason instead of being silently swapped for fake jobs.
    # Turn this on only to demo the UI without any API keys.
    demo_mode: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
