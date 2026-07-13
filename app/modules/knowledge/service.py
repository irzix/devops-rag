import uuid
import chromadb
from typing import List, Optional

# Shared ChromaDB persistent client (same data volume as guardrails)
client = chromadb.PersistentClient(path="data/chroma_db")

# --- 3 Separate Collections ---
command_history = client.get_or_create_collection(name="command_history")
server_logs = client.get_or_create_collection(name="server_logs")
server_configs = client.get_or_create_collection(name="server_configs")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

def _chunk_text(text: str) -> List[str]:
    """Split text into overlapping chunks for better retrieval."""
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start = end - CHUNK_OVERLAP
    return chunks


def index_command_output(
    server_name: str, command: str, stdout: str, stderr: str, exit_code: int
):
    """Auto-index SSH command execution results into command_history collection."""
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
    }
    chunks = _chunk_text(doc)
    for i, chunk in enumerate(chunks):
        command_history.add(
            ids=[f"cmd_{uuid.uuid4().hex[:12]}"],
            documents=[chunk],
            metadatas=[{**metadata, "chunk_index": i}],
        )


def index_log(server_name: str, log_source: str, content: str):
    """Index server log output into server_logs collection."""
    metadata = {
        "server_name": server_name,
        "log_source": log_source,
        "source": "server_logs",
    }
    chunks = _chunk_text(content)
    for i, chunk in enumerate(chunks):
        server_logs.add(
            ids=[f"log_{uuid.uuid4().hex[:12]}"],
            documents=[chunk],
            metadatas=[{**metadata, "chunk_index": i}],
        )


def index_config(server_name: str, file_path: str, content: str):
    """Index a server config file into server_configs collection."""
    metadata = {
        "server_name": server_name,
        "file_path": file_path,
        "source": "server_configs",
    }
    chunks = _chunk_text(content)
    for i, chunk in enumerate(chunks):
        server_configs.add(
            ids=[f"cfg_{uuid.uuid4().hex[:12]}"],
            documents=[chunk],
            metadatas=[{**metadata, "chunk_index": i}],
        )


# Map collection name -> collection object
_COLLECTIONS = {
    "command_history": command_history,
    "server_logs": server_logs,
    "server_configs": server_configs,
}


def search(
    query: str,
    collection_names: Optional[List[str]] = None,
    n_results: int = 3,
) -> str:
    """
    Semantic search across one or more knowledge collections.
    Returns formatted string of top results for LLM consumption.
    """
    targets = collection_names or list(_COLLECTIONS.keys())
    all_results = []

    for name in targets:
        col = _COLLECTIONS.get(name)
        if not col or col.count() == 0:
            continue
        results = col.query(query_texts=[query], n_results=min(n_results, col.count()))
        if results and results["documents"]:
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                all_results.append(
                    f"[{meta.get('source', name)}] "
                    f"Server: {meta.get('server_name', '?')} | "
                    f"{doc[:300]}"
                )

    if not all_results:
        return "No relevant knowledge found in the database."

    return "\n---\n".join(all_results)
