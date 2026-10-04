import os
from pydantic_settings import BaseSettings

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_sibling_images = os.path.abspath(os.path.join(_project_root, "..", "onfoodserver", "app", "static", "images"))
_container_images = "/app/static/images"

def _resolve_static_images_dir() -> str:
    env_dir = os.getenv("STATIC_IMAGES_DIR")
    if env_dir and os.path.isdir(env_dir):
        return env_dir
    if os.path.isdir(_container_images):
        return _container_images
    if os.path.isdir(_sibling_images):
        return _sibling_images
    local_fallback = os.path.join(_project_root, "static", "images")
    os.makedirs(local_fallback, exist_ok=True)
    return local_fallback

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/onfood"
    SQL_ECHO: bool = False
    JWT_SECRET: str = "super_secret_key_for_development_purposes"
    JWT_ISSUER: str = "onfood"
    UPLOAD_DIR: str = os.path.join(_project_root, "uploads")
    STATIC_IMAGES_DIR: str = _resolve_static_images_dir()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
