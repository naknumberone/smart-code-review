"""Настройки конфигурации."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Config(BaseSettings):
    """Конфигурация приложения."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    # LLM
    llm_api_url: str = Field(default="https://api.openai.com/v1")
    llm_model: str = Field(default="gpt-4o-mini")
    llm_api_key: str = Field(default="")
    llm_price_per_million_input_tokens: float = Field(
        default=0.150
    )  # цена gpt-4o-mini
    llm_price_per_million_output_tokens: float = Field(
        default=0.600
    )  # цена gpt-4o-mini

    # Репозиторий (обязательно)
    repo_path: str
    base_branch: str
    target_branch: str

    # Настройки ревью
    prompt_budget_chars: int = Field(default=50000)
    finalize_batch_size: int = Field(default=4)
    max_stages: int = Field(default=0)  # 0 = без лимита
