from langchain_openai import ChatOpenAI
from app.core.config import settings


def get_llm(callbacks=None) -> ChatOpenAI:
    """Streaming LLM for interactive agent turns.

    Use this ONLY inside agent_node where tokens need to be streamed
    to the active WebSocket. Do NOT use in background tasks.
    """
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is not configured in environment")

    return ChatOpenAI(
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base="https://openrouter.ai/api/v1",
        model=settings.OPENROUTER_MODEL,
        temperature=0.0,
        streaming=True,
        callbacks=callbacks or [],
        default_headers={
            "HTTP-Referer": "https://github.com/irzix/devops-copilot",
            "X-Title": "DevOps Copilot Agent",
        },
    )


def get_llm_non_streaming() -> ChatOpenAI:
    """Non-streaming LLM for background tasks (memory extraction, summarization, reflexion).

    Background tasks run via asyncio.create_task which inherits the parent's context,
    including active_websocket. Using a streaming LLM here would cause internal
    JSON (facts, summaries) to leak as tokens into the user's chat stream.
    Always use this factory for any LLM call that runs outside of agent_node.
    """
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is not configured in environment")

    return ChatOpenAI(
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base="https://openrouter.ai/api/v1",
        model=settings.OPENROUTER_MODEL,
        temperature=0.0,
        streaming=False,
        callbacks=[],
        default_headers={
            "HTTP-Referer": "https://github.com/irzix/devops-copilot",
            "X-Title": "DevOps Copilot Agent",
        },
    )
