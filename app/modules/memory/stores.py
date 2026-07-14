import uuid
import time
import chromadb
from typing import List, Optional

# Shared ChromaDB client
client = chromadb.PersistentClient(path="data/chroma_db")

# Standard Collections
command_history = client.get_or_create_collection(name="command_history")
server_logs = client.get_or_create_collection(name="server_logs")
server_configs = client.get_or_create_collection(name="server_configs")
lessons_learned = client.get_or_create_collection(name="lessons_learned")
episodic_summaries = client.get_or_create_collection(name="episodic_summaries")
user_facts = client.get_or_create_collection(name="user_facts")
procedural_tools = client.get_or_create_collection(name="procedural_tools")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

def _chunk_text(text: str) -> List[str]:
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start = end - CHUNK_OVERLAP
    return chunks

class SemanticStore:
    @staticmethod
    def add_command_output(server_name: str, command: str, stdout: str, stderr: str, exit_code: int, owner_id: int):
        doc = (
            f"Server: {server_name}\n"
            f"Command: {command}\n"
            f"Exit Code: {exit_code}\n"
            f"Stdout:\n{stdout}\n"
            f"Stderr:\n{stderr}"
        )
        metadata = {
            "server_name": server_name,
            "command": command,
            "exit_code": exit_code,
            "source": "command_history",
            "owner_id": owner_id,
            "timestamp": time.time()
        }
        chunks = _chunk_text(doc)
        for i, chunk in enumerate(chunks):
            command_history.add(
                ids=[f"cmd_{uuid.uuid4().hex[:12]}"],
                documents=[chunk],
                metadatas=[{**metadata, "chunk_index": i}]
            )

    @staticmethod
    def add_log(server_name: str, log_source: str, content: str, owner_id: int):
        metadata = {
            "server_name": server_name,
            "log_source": log_source,
            "source": "server_logs",
            "owner_id": owner_id,
            "timestamp": time.time()
        }
        chunks = _chunk_text(content)
        for i, chunk in enumerate(chunks):
            server_logs.add(
                ids=[f"log_{uuid.uuid4().hex[:12]}"],
                documents=[chunk],
                metadatas=[{**metadata, "chunk_index": i}]
            )

    @staticmethod
    def add_config(server_name: str, file_path: str, content: str, owner_id: int):
        metadata = {
            "server_name": server_name,
            "file_path": file_path,
            "source": "server_configs",
            "owner_id": owner_id,
            "timestamp": time.time()
        }
        chunks = _chunk_text(content)
        for i, chunk in enumerate(chunks):
            server_configs.add(
                ids=[f"cfg_{uuid.uuid4().hex[:12]}"],
                documents=[chunk],
                metadatas=[{**metadata, "chunk_index": i}]
            )

    @staticmethod
    def search(query: str, owner_id: int, n_results: int = 3) -> str:
        collections = {
            "command_history": command_history,
            "server_logs": server_logs,
            "server_configs": server_configs
        }
        results_list = []
        for name, col in collections.items():
            if col.count() == 0:
                continue
            # Query with owner filter
            res = col.query(
                query_texts=[query],
                where={"owner_id": owner_id},
                n_results=min(n_results, col.count())
            )
            if res and res["documents"] and res["documents"][0]:
                for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
                    results_list.append(
                        f"[{meta.get('source', name)}] "
                        f"Server: {meta.get('server_name', '?')} | "
                        f"{doc[:300]}"
                    )
        if not results_list:
            return "No relevant command outputs, logs, or configurations found."
        return "\n---\n".join(results_list)

class LessonStore:
    @staticmethod
    def add_lesson(server_name: str, problem: str, real_cause: str, what_didnt_work: str, what_worked: str, time_to_resolve: str, owner_id: int):
        doc = (
            f"Problem: {problem}\n"
            f"Real Cause: {real_cause}\n"
            f"What didn't work: {what_didnt_work}\n"
            f"What worked: {what_worked}\n"
            f"Time to Resolve: {time_to_resolve}"
        )
        metadata = {
            "server_name": server_name,
            "problem": problem,
            "real_cause": real_cause,
            "what_worked": what_worked,
            "time_to_resolve": time_to_resolve,
            "source": "lessons_learned",
            "owner_id": owner_id,
            "timestamp": time.time()
        }
        lessons_learned.add(
            ids=[f"lsn_{uuid.uuid4().hex[:12]}"],
            documents=[doc],
            metadatas=[metadata]
        )

    @staticmethod
    def search(query: str, owner_id: int, n_results: int = 3) -> str:
        if lessons_learned.count() == 0:
            return "No lessons learned recorded yet."
        res = lessons_learned.query(
            query_texts=[query],
            where={"owner_id": owner_id},
            n_results=min(n_results, lessons_learned.count())
        )
        if not res or not res["documents"] or not res["documents"][0]:
            return "No matching lessons learned found."
        cards = []
        for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
            cards.append(
                f"[Lesson Learned - Server: {meta.get('server_name', '?')}]\n{doc}"
            )
        return "\n\n---\n\n".join(cards)

class EpisodicStore:
    @staticmethod
    def add_summary(session_id: int, summary: str, owner_id: int):
        metadata = {
            "session_id": session_id,
            "owner_id": owner_id,
            "timestamp": time.time(),
            "source": "episodic_summaries"
        }
        episodic_summaries.add(
            ids=[f"ep_{session_id}_{uuid.uuid4().hex[:6]}"],
            documents=[summary],
            metadatas=[metadata]
        )

    @staticmethod
    def search(query: str, owner_id: int, n_results: int = 2) -> str:
        if episodic_summaries.count() == 0:
            return "No previous episodic summaries."
        res = episodic_summaries.query(
            query_texts=[query],
            where={"owner_id": owner_id},
            n_results=min(n_results, episodic_summaries.count())
        )
        if not res or not res["documents"] or not res["documents"][0]:
            return "No matching episodic history."
        summaries = []
        for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
            summaries.append(f"[Past Session {meta.get('session_id')} Summary]: {doc}")
        return "\n\n".join(summaries)

class UserFactStore:
    @staticmethod
    def add_fact(subject: str, content: str, fact_type: str, confidence: float, owner_id: int):
        # First query if we have similar facts about the subject
        doc = f"Subject: {subject}\nType: {fact_type}\nContent: {content}"
        metadata = {
            "subject": subject,
            "fact_type": fact_type,
            "confidence": confidence,
            "owner_id": owner_id,
            "timestamp": time.time()
        }
        user_facts.add(
            ids=[f"fact_{uuid.uuid4().hex[:12]}"],
            documents=[doc],
            metadatas=[metadata]
        )

    @staticmethod
    def search(query: str, owner_id: int, n_results: int = 5) -> str:
        if user_facts.count() == 0:
            return "No user facts recorded."
        res = user_facts.query(
            query_texts=[query],
            where={"owner_id": owner_id},
            n_results=min(n_results, user_facts.count())
        )
        if not res or not res["documents"] or not res["documents"][0]:
            return "No matching user facts."
        facts = []
        for doc in res["documents"][0]:
            facts.append(doc)
        return "\n".join(facts)

class ProceduralStore:
    @staticmethod
    def register_tool(name: str, description: str, parameters: str):
        doc = f"Tool Name: {name}\nDescription: {description}\nParameters: {parameters}"
        metadata = {
            "name": name,
            "timestamp": time.time()
        }
        # Check if already registered
        existing = procedural_tools.get(where={"name": name})
        if existing and existing["ids"]:
            procedural_tools.update(
                ids=existing["ids"],
                documents=[doc],
                metadatas=[metadata]
            )
        else:
            procedural_tools.add(
                ids=[f"tool_{name}"],
                documents=[doc],
                metadatas=[metadata]
            )

    @staticmethod
    def retrieve_tools(query: str, n_results: int = 4) -> List[str]:
        if procedural_tools.count() == 0:
            return []
        res = procedural_tools.query(
            query_texts=[query],
            n_results=min(n_results, procedural_tools.count())
        )
        if not res or not res["metadatas"] or not res["metadatas"][0]:
            return []
        return [meta["name"] for meta in res["metadatas"][0]]
