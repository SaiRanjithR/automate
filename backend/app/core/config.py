"""Application settings. The only module that reads environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


def _resolve(path: Path) -> Path:
    """Resolve a path from .env relative to the repo root, so it works from any cwd."""
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        str_strip_whitespace=True,
    )

    # App
    app_env: Literal["development", "production", "test"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    # Storage
    data_dir: Path = Path("./backend/data")
    database_url: str = "sqlite:///./backend/data/app.db"
    files_dir: Path = Path("./backend/data/files")
    max_upload_mb: int = Field(default=50, gt=0)
    # Policy rules as JSON / YAML files; re-read on every audit (no restart needed)
    policy_dir: Path = Path("./policies")

    # Auth
    jwt_secret: SecretStr = SecretStr("dev-only-insecure-secret-change-me")
    jwt_expire_minutes: int = Field(default=720, gt=0)
    admin_email: str = "admin@example.com"
    admin_password: SecretStr = SecretStr("change-me-strong-password")
    admin_name: str = "Admin"

    # LLM
    # auto = anthropic when an API key is set, otherwise the offline rule-based provider
    llm_provider: Literal["auto", "anthropic", "offline"] = "auto"
    llm_model: str = "claude-opus-5-5"
    llm_effort: Literal["low", "medium", "high"] = "medium"
    anthropic_api_key: SecretStr | None = None
    llm_max_concurrency: int = Field(default=8, gt=0)
    llm_max_tokens_per_project: int = Field(default=2_000_000, gt=0)
    llm_timeout_seconds: int = Field(default=120, gt=0)

    # Retrieval
    embedding_provider: Literal["fastembed", "hash"] = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    retrieval_min_score: float = Field(default=0.35, ge=0, le=1)
    retrieval_top_k: int = Field(default=6, gt=0)

    # Document tools
    ocr_enabled: bool = True
    tesseract_cmd: str = "tesseract"

    # Jobs: run inline (synchronously) instead of on the worker pool — used by tests and scripts
    jobs_inline: bool = False
    job_workers: int = Field(default=2, gt=0)

    @field_validator("data_dir", "files_dir", "policy_dir")
    @classmethod
    def _resolve_paths(cls, value: Path) -> Path:
        return _resolve(value)

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def _empty_key_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def resolved_database_url(self) -> str:
        """SQLite URLs with a relative path are resolved against the repo root."""
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            raw = Path(self.database_url.removeprefix(prefix))
            if not raw.is_absolute():
                return f"{prefix}{_resolve(raw)}"
        return self.database_url

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def effective_llm_provider(self) -> Literal["anthropic", "offline"]:
        if self.llm_provider == "auto":
            return "anthropic" if self.anthropic_api_key else "offline"
        return self.llm_provider

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
