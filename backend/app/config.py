from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DataPrep Studio API"
    app_version: str = "0.1.0"

    cors_origins: list[str] = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()