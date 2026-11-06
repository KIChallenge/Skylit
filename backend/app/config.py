"""Read and validate all environment configuration in this module."""

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "demo", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    secret_key: str = "change-me"

    llm_provider: Literal["eustella", "azure", "fake", "replay"] = "fake"
    llm_record: bool = False
    llm_fixtures_dir: str = "demo/fixtures"
    # Replay pacing makes recorded answers stream like live ones. 0 turns it off.
    llm_replay_first_token_ms: int = Field(default=0, ge=0)
    llm_replay_chars_per_second: float = Field(default=0, ge=0)
    llm_replay_max_seconds: float = Field(default=12, gt=0)
    # Where a replay miss goes: the scripted fake model or a live provider.
    llm_replay_fallback: Literal["fake", "eustella", "azure"] = "fake"
    eustella_api_key: str = ""
    eustella_base_url: str = "https://api.eustella.com/v1"
    eustella_model: str = "eustella-v1.5"
    llm_max_tokens: int = Field(default=4096, gt=0)
    llm_enable_thinking: bool = False
    document_extraction_thinking: bool = False
    llm_timeout_seconds: float = Field(default=120, gt=0)
    llm_max_retries: int = Field(default=2, ge=0)
    llm_max_concurrency: int = Field(default=2, gt=0)
    llm_max_tool_rounds: int = Field(default=3, gt=0)

    azure_openai_base_url: str = ""
    azure_openai_api_key: str = ""
    azure_openai_model: str = "gpt-5-4-mini"
    azure_reasoning_effort: Literal["low", "medium", "high"] = "low"
    guardrail_output_check: bool = False

    embedding_model: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    embedding_dim: int = Field(default=384, gt=0)
    embedding_cache_dir: str = "/models"
    rag_top_k: int = Field(default=5, gt=0)

    postgres_user: str = "lotse"
    postgres_password: str = "change-me"
    postgres_db: str = "lotse"
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, gt=0, le=65535)
    database_url: str = ""

    backend_port: int = Field(default=8000, gt=0, le=65535)
    port: int | None = Field(default=None, gt=0, le=65535)
    backend_cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000"
    ]
    # Local OCR for scans and photos. PyMuPDF calls Tesseract with these languages.
    ocr_enabled: bool = True
    ocr_languages: str = "deu+eng"
    # Tesseract language folder. Empty: PyMuPDF detects it.
    ocr_tessdata_dir: str = ""
    ocr_timeout_seconds: float = Field(default=60, gt=0)
    # Fuzzy quote check for OCR text, 0-100 (rapidfuzz partial_ratio).
    ocr_quote_min_similarity: float = Field(default=90, ge=0, le=100)

    upload_dir: str = "/data/uploads"
    max_upload_mb: int = Field(default=10, gt=0)
    frontend_port: int = Field(default=3000, gt=0, le=65535)
    next_public_api_url: str = "http://localhost:8000"

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            value = (
                json.loads(value)
                if value.lstrip().startswith("[")
                else value.split(",")
            )
        origins = [origin.strip().rstrip("/") for origin in value if origin.strip()]
        if "*" in origins:
            raise ValueError("BACKEND_CORS_ORIGINS requires explicit origins")
        return origins

    @model_validator(mode="after")
    def resolve_database_url(self) -> "Settings":
        # docker compose expands ${VAR} in .env; pydantic-settings does not.
        if not self.database_url or "${" in self.database_url:
            self.database_url = URL.create(
                "postgresql+asyncpg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                database=self.postgres_db,
            ).render_as_string(hide_password=False)
        return self


settings = Settings()
