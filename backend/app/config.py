"""
Configuration and settings management using Pydantic Settings.
Reads environment variables with sensible defaults for local development.
"""
import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # Database: SQLite locally, Neon/PostgreSQL in production
    DATABASE_URL: str = "sqlite:///./applications.db"

    # LLM configuration
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DEFAULT_LLM_PROVIDER: str = "gemini"

    # Data file paths (relative to backend or absolute)
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    JOBS_DATA_PATH: str = os.path.join(os.path.dirname(BASE_DIR), "data", "jobs.json")
    SKILLS_TAXONOMY_PATH: str = os.path.join(os.path.dirname(BASE_DIR), "data", "skills_taxonomy.json")

    # CORS origins for frontend
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://*.vercel.app"
    ]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

