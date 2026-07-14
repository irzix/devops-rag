import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.modules.memory.types import ExtractedFact

class ExtractionPipeline:
    async def run(self, messages: list, owner_id: int) -> list[ExtractedFact]:
        from app.modules.chat.agent import get_llm
        if not messages:
            return []
        
        # Build transcript of the recent interaction to focus on memory extraction
        transcript_parts = []
        for msg in messages[-4:]:
            # messages are langchain messages (HumanMessage, AIMessage, etc.)
            role = "User" if msg.type == "human" else "AI"
            content = msg.content
            if isinstance(content, list):
                content = " ".join([str(c) for c in content])
            transcript_parts.append(f"[{role}]: {content}")
        transcript = "\n".join(transcript_parts)
        
        prompt = """You are an Expert DevOps Memory System. Analyze the recent conversation transcript between a DevOps admin and an AI agent.
Your task is to extract important user preferences, server facts (e.g., OS version, configuration file paths, server specs), relationships, or incidents that are critical to persist.

Output ONLY a JSON array of objects conforming to this schema:
[
  {
    "fact_type": "preference" | "server_fact" | "relationship" | "incident",
    "subject": "The main entity, tool, or server (e.g., 'prod-db', 'nginx', 'user')",
    "content": "The actual fact or preference (e.g., 'User prefers to reboot only during maintenance windows', 'nginx is installed at /etc/nginx')",
    "confidence": 0.0 to 1.0
  }
]

If no important facts, preferences, or relationships were mentioned/revealed in this turn, return an empty array [].
Output ONLY valid JSON code. Do NOT enclose in markdown formatting.
"""
        try:
            llm = get_llm()
            response = await llm.ainvoke([
                SystemMessage(content=prompt),
                HumanMessage(content=f"TRANSCRIPT:\n{transcript}")
            ])
            text = response.content
            if isinstance(text, list):
                text = " ".join([str(t) for t in text])
            
            clean_json = text.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            clean_json = clean_json.strip()
            
            if not clean_json or clean_json == "[]":
                return []
            
            data = json.loads(clean_json)
            facts = []
            for item in data:
                # Validate schema
                fact_type = item.get("fact_type")
                if fact_type not in ["preference", "server_fact", "relationship", "incident"]:
                    continue
                facts.append(ExtractedFact(
                    fact_type=fact_type,
                    subject=item.get("subject", "unknown"),
                    content=item.get("content", ""),
                    confidence=float(item.get("confidence", 1.0))
                ))
            return facts
        except Exception as e:
            # Silent fallback to avoid breaking conversation loops
            import logging
            logging.error(f"Error in memory extraction: {str(e)}")
            return []
