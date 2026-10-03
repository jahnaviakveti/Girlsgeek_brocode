from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Vettora AI Vetting Platform"
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()
