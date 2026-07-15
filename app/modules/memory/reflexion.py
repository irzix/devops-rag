import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from app.modules.memory.stores import LessonStore
from app.core.database import async_session_maker
from app.core.llm import get_llm_non_streaming
from app.modules.chat.models import ChatMessage
from sqlmodel import select

_REFLEXION_PROMPT = """\
You are an Expert DevOps Post-Incident Analyst.
A DevOps administrator has given NEGATIVE feedback on one of the AI agent's responses.
Analyze the transcript of the conversation, the specific message they disliked, and their feedback comment.

Your task is to perform a root-cause analysis and output a JSON object representing a lesson learned to prevent this error in the future.

The user's feedback comment: "{feedback_comment}"
The AI response they disliked: "{target_ai_message}"

Output ONLY a JSON object with the following fields (no markdown formatting, no codeblocks):
{{
  "problem": "Brief description of the problem/request",
  "real_cause": "Why did the agent fail? (e.g., ran a dangerous command without explaining, ignored directory context, etc.)",
  "what_didnt_work": "The action or response the agent did that resulted in negative feedback",
  "what_worked": "What the agent SHOULD have done instead to satisfy the user",
  "time_to_resolve": "N/A"
}}
"""


def _parse_llm_json(text: str) -> dict:
    """Strip optional markdown fences and parse JSON from an LLM response."""
    if isinstance(text, list):
        text = " ".join(str(t) for t in text)
    clean = text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    if clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    return json.loads(clean.strip())


async def _fetch_session_transcript(session_id: int) -> list[ChatMessage]:
    """Return all ChatMessage rows for a session ordered chronologically."""
    async with async_session_maker() as db_session:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        result = await db_session.exec(stmt)
        return result.all()


async def reflect_on_negative_feedback(
    session_id: int,
    message_id: int,
    user_comment: str,
    owner_id: int,
) -> None:
    """
    Analyze a conversation that received negative feedback, extract a lesson
    from the failure, and store it in LessonStore so the agent avoids repeating
    the mistake for this user in the future.
    """
    # Import here to avoid circular import (agent imports memory, memory mustn't import agent at module level)
    from app.modules.chat.agent import get_llm

    try:
        db_messages = await _fetch_session_transcript(session_id)
        if not db_messages:
            return

        transcript_lines = []
        target_ai_message = ""
        for msg in db_messages:
            role = "User" if msg.sender == "user" else "AI"
            transcript_lines.append(f"[{role}]: {msg.content}")
            if msg.id == message_id:
                target_ai_message = msg.content

        formatted_prompt = _REFLEXION_PROMPT.format(
            feedback_comment=user_comment or "No comment provided.",
            target_ai_message=target_ai_message,
        )

        llm = get_llm_non_streaming()
        response = await llm.ainvoke([
            SystemMessage(content=formatted_prompt),
            HumanMessage(content="CONVERSATION TRANSCRIPT:\n" + "\n".join(transcript_lines)),
        ])

        data = _parse_llm_json(response.content)

        LessonStore.add_lesson(
            server_name="General/Reflexion",
            problem=data.get("problem", "User dissatisfaction with agent behavior"),
            real_cause=data.get("real_cause", ""),
            what_didnt_work=data.get("what_didnt_work", ""),
            what_worked=data.get("what_worked", ""),
            time_to_resolve="N/A",
            owner_id=owner_id,
        )
        logging.info("Reflexion lesson recorded for session %s", session_id)

    except Exception:
        logging.exception("Error in negative feedback reflexion pipeline for session %s", session_id)
