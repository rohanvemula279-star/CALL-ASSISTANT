"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "ai-phone-assistant"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    environment: Literal["development", "production", "testing"] = "development"
    log_level: str = "info"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "minimax-m3"
    ollama_timeout: int = 60

    # Whisper
    whisper_model: str = "base"
    whisper_device: Literal["cpu", "cuda"] = "cpu"
    whisper_preload: bool = False

    # Piper
    piper_voice: str = "en_US-amy-medium"
    piper_preload: bool = False
    piper_output_dir: str = "./storage/tts"

    # Storage
    storage_dir: str = "./storage"
    sqlite_path: str = "./storage/conversations.db"

    # Asterisk (informational)
    asterisk_host: str = "asterisk"
    asterisk_http_port: int = 8088

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_timeout: int = 10

    # LiveKit (voice agent)
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # Webhooks
    # Public base URL of *this* service. Used in Telegram messages so
    # the "Open dashboard" link works.
    base_url: str = "http://localhost:8000"

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @property
    def logs_dir(self) -> Path:
        path = self.project_root / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def storage_path(self) -> Path:
        path = Path(self.storage_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def piper_output_path(self) -> Path:
        path = Path(self.piper_output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
