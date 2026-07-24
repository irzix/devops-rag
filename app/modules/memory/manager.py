import os
from experia.core.learner import Learner
from experia.memory.store import SQLiteStore
from experia.experience.llm_evaluator import LLMEvaluator

os.makedirs("data", exist_ok=True)
global_store = SQLiteStore(db_path="data/agent_memory.db")
_store_initialized = False

async def get_learner(owner_id: int) -> Learner:
    global _store_initialized
    if not _store_initialized:
        await global_store.initialize()
        _store_initialized = True
        
    # Read model from environment variables and prepend 'openrouter/' for LiteLLM
    model_name = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    if not model_name.startswith("openrouter/"):
        model_name = f"openrouter/{model_name}"
        
    evaluator = LLMEvaluator(model=model_name)
    
    return Learner(
        store=global_store,
        evaluator=evaluator,
        agent_role=str(owner_id)
    )
