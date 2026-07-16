from langchain_openai import ChatOpenAI
from app.core.config import settings


def _get_provider_config() -> dict:
    """Resolve LLM provider configuration.

    Supports two backends:
      1. **Ollama** (local, free) — set ``OLLAMA_BASE_URL`` in ``.env``
         (e.g. ``http://localhost:11434/v1``).
      2. **OpenRouter** (cloud) — set ``OPENROUTER_API_KEY`` in ``.env``.

    Ollama is tried first so contributors can run the project without any
    paid API key.
    """
    if settings.OLLAMA_BASE_URL:
        return {
            "openai_api_key": "ollama",  # Ollama doesn't need a real key
            "openai_api_base": settings.OLLAMA_BASE_URL,
            "model": settings.OLLAMA_MODEL,
            "default_headers": {},
        }

    if settings.OPENROUTER_API_KEY:
        return {
            "openai_api_key": settings.OPENROUTER_API_KEY,
            "openai_api_base": "https://openrouter.ai/api/v1",
            "model": settings.OPENROUTER_MODEL,
            "default_headers": {
                "HTTP-Referer": "https://github.com/irzix/devops-copilot",
                "X-Title": "DevOps Copilot Agent",
            },
        }

    raise ValueError(
        "No LLM provider configured. "
        "Set OLLAMA_BASE_URL (free, local) or OPENROUTER_API_KEY in your .env file. "
        "See README for setup instructions."
    )


def get_llm(callbacks=None) -> ChatOpenAI:
    """Streaming LLM for interactive agent turns.

    Use this ONLY inside agent_node where tokens need to be streamed
    to the active WebSocket. Do NOT use in background tasks.
    """
    config = _get_provider_config()
    return ChatOpenAI(
        openai_api_key=config["openai_api_key"],
        openai_api_base=config["openai_api_base"],
        model=config["model"],
        temperature=0.0,
        streaming=True,
        callbacks=callbacks or [],
        default_headers=config["default_headers"],
    )


def get_llm_non_streaming() -> ChatOpenAI:
    """Non-streaming LLM for background tasks (memory extraction, summarization, reflexion).

    Background tasks run via asyncio.create_task which inherits the parent's context,
    including active_websocket. Using a streaming LLM here would cause internal
    JSON (facts, summaries) to leak as tokens into the user's chat stream.
    Always use this factory for any LLM call that runs outside of agent_node.
    """
    config = _get_provider_config()
    return ChatOpenAI(
        openai_api_key=config["openai_api_key"],
        openai_api_base=config["openai_api_base"],
        model=config["model"],
        temperature=0.0,
        streaming=False,
        callbacks=[],
        default_headers=config["default_headers"],
    )
