from app.modules.memory.types import ExtractedFact
from app.modules.memory.stores import UserFactStore, user_facts

class ConsolidationPipeline:
    async def consolidate(self, facts: list[ExtractedFact], owner_id: int):
        for fact in facts:
            if fact.confidence < 0.6:
                # Discard low confidence extractions
                continue
            
            query_str = f"Subject: {fact.subject}\nType: {fact.fact_type}\nContent: {fact.content}"
            
            is_duplicate = False
            if user_facts.count() > 0:
                # Query user_facts collection for similar content under the same owner
                res = user_facts.query(
                    query_texts=[query_str],
                    where={"owner_id": owner_id},
                    n_results=1
                )
                if res and res["documents"] and res["documents"][0]:
                    distance = res["distances"][0][0]
                    similarity = 1.0 - (distance / 2.0)
                    
                    # If semantically almost identical, treat as duplicate and skip to avoid bloat
                    if similarity > 0.88:
                        is_duplicate = True
            
            if not is_duplicate:
                UserFactStore.add_fact(
                    subject=fact.subject,
                    content=fact.content,
                    fact_type=fact.fact_type,
                    confidence=fact.confidence,
                    owner_id=owner_id
                )
