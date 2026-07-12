# DevOps-RAG 🚀

An open-source, AI-driven DevOps Agent and CLI Client designed to manage raw root/bare-metal servers securely. It features persistent credential encryption, real-time terminal streaming, and semantic security guardrails using a local vector database.

---

## Key Features
- **Semantic Guardrails:** Uses local **ChromaDB** to intercept and block dangerous terminal commands before execution.
- **Human-in-the-Loop (HITL):** Enforces admin approval (`[y/N]`) inside the terminal for any state-modifying actions (e.g. system service restarts).
- **Real-Time Streaming:** Streams LLM thoughts and active SSH `stdout`/`stderr` line-by-line using WebSockets.
- **Encrypted Credentials:** Securely encrypts passwords and SSH private keys using Fernet (AES-256).
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
devops-rag login
```

### 3. Interactive Chat
Start the real-time DevOps chat session:
```bash
devops-rag chat
```
*Ask the agent to check stats or run actions. Approve state-modifying commands directly in the prompt.*
