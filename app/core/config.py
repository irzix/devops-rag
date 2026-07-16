from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///data/devops_rag.db"
    
    JWT_SECRET_KEY: str = "supersecretkey_change_me_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Key for encrypting target server credentials (SSH passwords/private keys)
    ENCRYPTION_KEY: str = "h-0rAgfuXQnNinQ9yZevWRvRNv9_nWdixhHG_DZGmoE="
    
    # Ollama (local, free — preferred for development and contributors)
    # Set OLLAMA_BASE_URL to enable local LLM inference without any API key.
    # Example: OLLAMA_BASE_URL=http://localhost:11434/v1
    OLLAMA_BASE_URL: str | None = None
    OLLAMA_MODEL: str = "qwen2.5:7b"

    # OpenRouter API configurations for AI Agent (cloud — requires API key)
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str = "google/gemini-2.5-flash"

    # LangSmith observability (optional — set LANGSMITH_TRACING=true to enable)
    LANGSMITH_TRACING: bool = False
    LANGSMITH_API_KEY: str | None = None
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_PROJECT: str = "devops-copilot"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()