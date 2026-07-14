from langchain_core.messages import SystemMessage, HumanMessage
from app.modules.memory.stores import EpisodicStore

class EpisodicSummarizer:
    async def maybe_summarize(self, session_id: int, messages: list, owner_id: int):
        from app.modules.chat.agent import get_llm
        # Summarize if the conversation has reached a significant length
        if len(messages) < 6:
            return
        
        transcript_parts = []
        for msg in messages:
            role = "User" if msg.type == "human" else "AI"
            content = msg.content
            if isinstance(content, list):
                content = " ".join([str(c) for c in content])
            transcript_parts.append(f"[{role}]: {content}")
        transcript = "\n".join(transcript_parts)
        
        prompt = """You are an Expert DevOps Session Summarizer. Your goal is to write a concise, high-density summary of this DevOps chat session.
Summarize:
- The main objective/request of the admin.
- Key servers targeted, diagnostics run, or changes made (e.g. commands executed, config modifications).
- The outcome of the session (e.g., success, paused for approval, errors).

Keep it under 150 words. Output ONLY the summary text. No intro/outro.
"""
        try:
            llm = get_llm()
            response = await llm.ainvoke([
                SystemMessage(content=prompt),
                HumanMessage(content=f"SESSION TRANSCRIPT:\n{transcript}")
            ])
            summary = response.content
            if isinstance(summary, list):
                summary = " ".join([str(s) for s in summary])
            
            EpisodicStore.add_summary(
                session_id=session_id,
                summary=summary.strip(),
                owner_id=owner_id
            )
        except Exception as e:
            import logging
            logging.error(f"Error in episodic summarization: {str(e)}")
            # Fail silently to avoid interrupting the agent
