from typing import TypedDict, Annotated, Literal, List
from pydantic import BaseModel
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    memory_context: str
    owner_id: int
    session_id: int

class ExtractedFact(BaseModel):
    fact_type: Literal["preference", "server_fact", "relationship", "incident"]
    subject: str
    content: str
    confidence: float

class MemoryContext(BaseModel):
    lessons: str
    knowledge: str
    episodic: str
