"""Application settings, loaded from environment / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # General
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Vayu-X Cyclone Intelligence API"
    VERSION: str = "0.1.0"

    # Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # Security
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: str = "http://localhost:5173"

    # Serve synthetic cyclone data instead of 501 stubs. Lets the dashboard and
    # alert console be demonstrated without a database, trained models, or live
    # satellite feeds. Every demo payload is tagged synthetic.
    DEMO_MODE: bool = True

    # Where cyclone events come from:
    #   "ibtracs"   real historical storms replayed from best-track data
    #   "synthetic" generated demo events (no data files needed)
    DATA_SOURCE: str = "ibtracs"
    IBTRACS_PATH: str = "../ai-model/data/raw/ibtracs/ibtracs_NI_v04r01.csv"
    REPLAY_STORM_COUNT: int = 4
    REPLAY_MIN_SEASON: int = 2021  # held out from model training

    # Database
    DATABASE_URL: str = "postgresql+psycopg://vayux:change-me@localhost:5432/vayux"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Downstream services
    MODEL_SERVICE_URL: str = "http://localhost:8001"
    ALERT_SERVICE_URL: str = "http://localhost:8002"

    # Windy Point Forecast API — optional independent cross-check on conditions
    # at the forecast landfall point. Point service only: no map tiles.
    WINDY_POINT_API_KEY: str = ""

    # Object storage
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "change-me"
    S3_BUCKET_PROCESSED: str = "vayux-processed"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
