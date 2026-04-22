from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Database
    database_url: str

    # LLM
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_api_key_env: Optional[str] = None
    
    # Scraping
    apify_api_token: Optional[str] = None
    apify_api_token_env: Optional[str] = None
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    reddit_user_agent: str = "BettingCreatorTracker/1.0"
    youtube_api_key: Optional[str] = None

    # Odds/Sports
    the_odds_api_key: Optional[str] = None
    the_odds_api_key_env: Optional[str] = None

    # Security
    admin_api_key: Optional[str] = None
    admin_api_key_env: Optional[str] = None
    allowed_origins: str = "http://localhost:3000"

    # Gmail ingestion (Twitter notification adapter)
    gmail_credentials_json: Optional[str] = None
    gmail_credentials_json_env: Optional[str] = None
    gmail_token_json: Optional[str] = None
    gmail_token_json_env: Optional[str] = None
    gmail_label_id: Optional[str] = None
    gmail_ingestion_enabled: bool = False
    gmail_ingestion_interval_minutes: int = 10
    gmail_ingestion_lookback_hours: int = 2

    # Scheduler
    scrape_interval_hours: int = 4
    resolve_interval_hours: int = 2

    # App
    environment: str = "development"
    log_level: str = "INFO"
    failed_extraction_notify: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False

    def __init__(self, **data):
        super().__init__(**data)
        # Resolve env var references
        if self.anthropic_api_key_env:
            self.anthropic_api_key = os.getenv(self.anthropic_api_key_env)
        if self.apify_api_token_env:
            self.apify_api_token = os.getenv(self.apify_api_token_env)
        if self.the_odds_api_key_env:
            self.the_odds_api_key = os.getenv(self.the_odds_api_key_env)
        if self.admin_api_key_env:
            self.admin_api_key = os.getenv(self.admin_api_key_env)
        if self.gmail_credentials_json_env:
            self.gmail_credentials_json = os.getenv(self.gmail_credentials_json_env)
        if self.gmail_token_json_env:
            self.gmail_token_json = os.getenv(self.gmail_token_json_env)


settings = Settings()
