from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DARK_ORCH_",
        env_file=".env",
        extra="ignore",
    )

    SERVICE_NAME: str = "Dark Orchestrator"
    HOST: str = "127.0.0.1"
    PORT: int = Field(default=8099, ge=1, le=65_535)
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]
    CORS_ALLOW_METHODS: list[str] = ["*"]

    DATABASE_URL: str = (
        "postgresql://dark_orchestrator:dark_orchestrator@"
        "localhost:54329/dark_orchestrator"
    )
    HEART_BEAT_INTERVAL: float = Field(default=30, gt=0)
    MAX_CONCURRENT_JOBS: int = Field(default=4, ge=1, le=100)
    PROCESS_TIMEOUT_SECONDS: float = Field(default=900, gt=0)
    MAX_CAPTURED_OUTPUT_BYTES: int = Field(default=1_000_000, ge=64)
    SCRIPT_ROOT: Path = Path(__file__).parents[2] / "processes"
    FRONTEND_DIR: Path = Path(__file__).parents[2] / "web" / "dist"


settings = Settings()
