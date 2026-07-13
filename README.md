# DevOps-Copilot 🚀

An open-source, AI-driven DevOps Copilot and CLI Client designed to manage raw root/bare-metal servers securely. It features persistent credential encryption, real-time terminal streaming, and semantic security guardrails using a local vector database.

---

## Key Features
- **Experiential Learning (ExpeL / Reflexion Postmortems):** Automatically distills complex debugging sessions into structured `Lessons Learned` cards (`Problem`, `Real Cause`, `What didn't work`, `What worked`) indexed into ChromaDB. The agent performs semantic retrieval on past postmortems before troubleshooting new errors to avoid dead ends.
- **Lean RAG Knowledge Base:** Automatically chunks and indexes executed SSH command outputs, logs, and server configs into separate **ChromaDB** collections, enabling the agent to search past server history before executing new commands.
- **Semantic Guardrails:** Uses local vector search to intercept and block dangerous terminal commands.
- **Human-in-the-Loop (HITL):** Enforces admin approval (`[y/N]`) inside the terminal for any state-modifying actions with clean prompt synchronization.
- **CLI Connection Resilience:** Automatically reconnects to the WebSocket server using exponential backoff if the network drops or the server restarts.
- **Real-Time Streaming:** Streams LLM thoughts and active SSH `stdout`/`stderr` line-by-line using WebSockets with 30s execution timeouts.
- **Encrypted Credentials:** Securely encrypts passwords and SSH private keys using Fernet (AES-256).
- **Server & Session CRUD:** Full REST API support for updating/deleting server connections and deleting chat sessions (with cascade cleanup).
- **Flexible AI Models:** Powered by **OpenRouter** (supports Llama 3, Gemini, GPT, etc.).

---

## 📦 Quick Start (Backend Server)

### 1. Configure Settings
Copy the env file and populate keys:
```bash
cp .env.example .env
```
Make sure to add your `OPENROUTER_API_KEY` and a custom base64 `ENCRYPTION_KEY` in `.env`.

### 2. Run with Docker Compose
```bash
docker compose up -d --build
```
The server will boot on port `8000`. Database tables and security blacklist vectors are automatically seeded on startup.

---

## 💻 Quick Start (CLI Client)

### 1. Install Globally
Install the package in editable mode from your local repository root:
```bash
uv pip install -e .
```

### 2. Authenticate
Configure the server URL and log in to get your JWT access token:
```bash
devops-copilot login
```

### 3. Interactive Chat & Auto-Postmortems
Start the real-time DevOps chat session:
```bash
devops-copilot chat
```
*Ask the agent to check stats or run actions. Approve state-modifying commands directly in the prompt.*

Extract and index a structured Experiential Lesson Learned from any completed troubleshooting session:
```bash
devops-copilot lesson <session_id>
```
