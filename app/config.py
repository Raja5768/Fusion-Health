from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fusion Health"
    app_env: str = "local"
    database_url: str = "sqlite:///./fusion_health.db"
    secret_key: str = "change-me"
    fusion_encryption_key: str | None = None

    whoop_client_id: str | None = None
    whoop_client_secret: str | None = None
    whoop_redirect_uri: str = "http://localhost:8000/api/v1/auth/whoop/callback"
    whoop_scopes: str = "offline read:profile read:recovery read:cycles read:sleep read:workout"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    enable_ollama: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
