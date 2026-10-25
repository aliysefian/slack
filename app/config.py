from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    slack_bot_token: str
    slack_signing_secret: str
    my_slack_user_id: str
    telegram_bot_token: str
    telegram_chat_id: str

    log_level: str = "INFO"
    # Max accepted clock skew for Slack request timestamps (replay protection).
    slack_timestamp_tolerance: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
