from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    fake_llm: bool = True
    fake_llm_delay_seconds: float = Field(default=0.2, ge=0)
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-6-luna"
    openai_timeout_seconds: float = Field(default=30, gt=0)
    openai_max_output_tokens: int = Field(default=300, gt=0)
    rag_enabled: bool = True
    embedding_model: str = "text-embedding-3-small"
    policy_path: Path = Path(__file__).resolve().parents[2] / "policies" / "store_policy.md"
    chroma_path: Path = Path(__file__).resolve().parents[2] / ".chroma"
    rag_k: int = Field(default=4, ge=1, le=8)


@lru_cache
def get_settings() -> Settings:
    return Settings()
