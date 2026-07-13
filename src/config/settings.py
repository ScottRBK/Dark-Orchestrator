from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings): 
    model_config = SettingsConfigDict(env_prefix="DARK_ORCH_", env_file=".env", extra="ignore")

    ## Server Configuration 
    SERVICE_NAME: str = "Dark-Orchestrator"
    HOST: str = "0.0.0.0"
    PORT: int = 8099
    CORS_ORIGINS: list[str] = []
    CORS_ALLOW_HEADERS: list[str] = []
    CORS_ALLOW_METHDS: list[str] = []

    ## Orchestration Copnfiguration 
    HEART_BEAT_INTERVAL: int = 30 # seconds 

settings = Settings() 
