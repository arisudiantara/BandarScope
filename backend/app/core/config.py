"""Application configuration."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "BandarScope"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./bandarscope.db"

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Mock data settings
    MOCK_HISTORY_DAYS: int = 120
    MOCK_SYMBOLS_COUNT: int = 50

    class Config:
        env_file = ".env"


settings = Settings()
