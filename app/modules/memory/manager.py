import asyncio
import logging
from app.modules.memory.types import MemoryContext
from app.modules.memory.stores import SemanticStore, LessonStore, EpisodicStore, UserFactStore
from app.modules.memory.extraction import ExtractionPipeline
from app.modules.memory.consolidation import ConsolidationPipeline
from app.modules.memory.summarizer import EpisodicSummarizer

class MemoryManager:
    def __init__(self):
        self.extraction_pipeline = ExtractionPipeline()
        self.consolidation_pipeline = ConsolidationPipeline()
        self.summarizer = EpisodicSummarizer()

    def read_context(self, query: str, owner_id: int) -> MemoryContext:
        try:
            # Semantic search across lessons learned, general command/config history, and facts/preferences
            lessons = LessonStore.search(query, owner_id, n_results=2)
            knowledge_raw = SemanticStore.search(query, owner_id, n_results=3)
            episodic = EpisodicStore.search(query, owner_id, n_results=2)
            facts_raw = UserFactStore.search(query, owner_id, n_results=3)
            
            combined_knowledge = (
                f"=== System Knowledge & Command Outputs ===\n{knowledge_raw}\n\n"
                f"=== User Specifications & Dynamic Facts ===\n{facts_raw}"
            )
            
            return MemoryContext(
                lessons=lessons,
                knowledge=combined_knowledge,
                episodic=episodic
            )
        except Exception as e:
            logging.error(f"Error reading memory context: {str(e)}")
            return MemoryContext(
                lessons="No relevant past postmortems found.",
                knowledge="No matching system outputs found.",
                episodic="No relevant prior session summaries found."
            )

    async def write_after_turn(self, messages: list, owner_id: int, session_id: int):
        try:
            # 1. LLM Fact Extraction from conversation
            facts = await self.extraction_pipeline.run(messages, owner_id)
            if facts:
                # 2. Consolidation & Deduplication before persisting
                await self.consolidation_pipeline.consolidate(facts, owner_id)
            
            # 3. Check for episodic summarization
            await self.summarizer.maybe_summarize(session_id, messages, owner_id)
        except Exception as e:
            logging.error(f"Error writing memory after turn: {str(e)}")

# Single global instance
memory_manager = MemoryManager()
