from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str

    # LLM
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Scraping
    apify_api_token: Optional[str] = None
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    reddit_user_agent: str = "BettingCreatorTracker/1.0"
    youtube_api_key: Optional[str] = None

    # Odds/Sports
    the_odds_api_key: Optional[str] = None

    # App
    environment: str = "development"
    log_level: str = "INFO"
    failed_extraction_notify: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
