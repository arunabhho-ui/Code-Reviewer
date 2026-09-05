import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Code Reviewer & Bug Fixing Agent"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api"

    # LLM Settings — Groq Cloud is the default provider, with Grok compatibility retained.
    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: Optional[str] = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROK_API_KEY: Optional[str] = ""
    GROK_MODEL: str = "grok-3"
    GROK_BASE_URL: str = "https://api.x.ai/v1"
    GITHUB_TOKEN: Optional[str] = ""
    VALID_GROQ_MODELS: List[str] = [
        "openai/gpt-oss-120b",
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
    ]

    # Sandbox Settings
    SANDBOX_TIMEOUT_SECONDS: int = 10
    SANDBOX_MEMORY_LIMIT: str = "512m"
    SANDBOX_CPU_QUOTA: int = 100000  # 1.0 CPU
    USE_DOCKER_SANDBOX: bool = True

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "*",  # Allow all for deployment preview / flexibility
    ]

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def active_provider(self) -> str:
        provider = (os.getenv("LLM_PROVIDER") or self.LLM_PROVIDER or "groq").lower()
        if provider in {"groq", "grok"}:
            return provider
        return "groq"

    @property
    def active_api_key(self) -> str:
        provider = self.active_provider
        if provider == "groq":
            return self.GROQ_API_KEY or self.GROK_API_KEY or ""
        return self.GROK_API_KEY or self.GROQ_API_KEY or ""

    @property
    def active_model(self) -> str:
        provider = self.active_provider
        if provider == "groq":
            candidate = self.GROQ_MODEL or "openai/gpt-oss-120b"
            return candidate if candidate in self.VALID_GROQ_MODELS else "openai/gpt-oss-120b"
        return self.GROK_MODEL or self.GROQ_MODEL or "grok-3"

    @property
    def active_base_url(self) -> str:
        provider = self.active_provider
        if provider == "groq":
            return self.GROQ_BASE_URL or "https://api.groq.com/openai/v1"
        return self.GROK_BASE_URL or "https://api.x.ai/v1"


settings = Settings()

