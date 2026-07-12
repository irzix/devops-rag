from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///data/devops_rag.db"
    
    JWT_SECRET_KEY: str = "supersecretkey_change_me_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Key for encrypting target server credentials (SSH passwords/private keys)
    ENCRYPTION_KEY: str = "h-0rAgfuXQnNinQ9yZevWRvRNv9_nWdixhHG_DZGmoE="
    
    # OpenRouter API configurations for AI Agent
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str = "google/gemini-2.5-flash"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()