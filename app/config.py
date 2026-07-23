from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/onfood"
    SQL_ECHO: bool = False
    JWT_SECRET: str = "super_secret_key_for_development_purposes"
    JWT_ISSUER: str = "onfood"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
