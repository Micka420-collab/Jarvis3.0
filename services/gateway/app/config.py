from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jarvis_domain: str = "jarvis.local"

    jwt_secret: str = "change_me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    owner_username: str = "owner"

    redis_host: str = "redis"
    redis_port: int = 6379

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "jarvis"
    postgres_user: str = "jarvis"
    postgres_password: str = "change_me"

    voiceprint_threshold_accept: float = 0.75
    voiceprint_threshold_grey: float = 0.65
    admin_command_cooldown_seconds: int = 30

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
