# DevOps Copilot 🚀

**An autonomous, self-learning AI DevOps Assistant & CLI Client that manages bare-metal servers with Experiential Memory (`ExpeL`), Semantic Guardrails, and Real-Time SSH Tunneling.**

---

## 💡 About The Project

Managing infrastructure via traditional CLI tools or basic AI wrappers often leads to dangerous mistakes, repetitive debugging dead-ends, and fragmented server logs. **DevOps Copilot** redefines server management by bringing **Closed-Loop Experiential Learning (ExpeL)** directly to your terminal.

Unlike standard AI chat wrappers that forget previous troubleshooting sessions, `DevOps Copilot` builds a permanent, structured **ChromaDB Vector Knowledge Base** of your infrastructure:

- **🧠 Zero-Click Experiential Learning (ExpeL & Reflexion):** Every time an incident or bug is diagnosed and resolved, the agent distills the entire session into a structured Postmortem (`Problem`, `Real Cause`, `What didn't work`, `What worked`). Before tackling new errors, relevant past lessons are **automatically retrieved and injected** into the agent's context—ensuring it *never repeats a dead end*.
- **🛡️ Semantic Security Guardrails:** Local vector search intercepts and blocks catastrophic shell commands (e.g., `rm -rf /`, `mkfs`) before they ever touch your servers.
- **🧑‍💻 Human-in-the-Loop (HITL) Approvals:** State-modifying actions dynamically prompt for explicit admin confirmation (`[y/N]`) inside the terminal with clean prompt synchronization.
- **⚡ Real-Time Async Execution Tunnel:** Streams LLM reasoning, SSH `stdout`, and `stderr` line-by-line via resilient WebSockets with automatic reconnection and exponential backoff.
- **🔒 Zero-Trust Credential Encryption:** Passwords and SSH private keys are encrypted at rest using AES-256 (`Fernet`).

---

## 🏛️ System Architecture & ExpeL Loop

```
+-----------------------------------------------------------------------------------+
|                                 DevOps Copilot CLI                                |
|  (Typer Async Client + Real-Time WebSocket Tunnel + [y/N] Terminal Approval)      |
+-----------------------------------------------------------------------------------+
                                   |           ^
                   REST Auth/CRUD  |           | WebSocket Stream (stdout/stderr)
                                   v           |
+-----------------------------------------------------------------------------------+
|                              FastAPI Backend Server                               |
|                                                                                   |
|  +------------------------+   +-----------------------+   +--------------------+  |
|  |     Auth Module        |   |    Servers Module     |   | Guardrails Module  |  |
|  |  (JWT & AES Fernet)    |   |  (AsyncSSH Execution) |   | (Vector Blacklist) |  |
|  +------------------------+   +-----------------------+   +--------------------+  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                              Chat & Agent Module                            |  |
|  |   LangChain StateGraph + Zero-Click ExpeL Injection + OpenRouter LLM        |  |
|  +-----------------------------------------------------------------------------+  |
|                                       |                                           |
|                                       v                                           |
|  +-----------------------------------------------------------------------------+  |
|  |                            Knowledge Base (ChromaDB)                        |  |
|  |  [command_history]   [server_logs]   [server_configs]   [lessons_learned]   |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### The Closed-Loop Experiential Learning (`ExpeL`) Flow:
1. **Observe & Act:** Agent connects via `AsyncSSH`, runs non-destructive diagnostics or approved actions, and indexes outputs into `command_history` and `server_logs`.
2. **Judge & Extract:** When an incident is resolved, running `devops-copilot lesson <session_id>` triggers an automated LLM extraction (`Problem`, `Real Cause`, `What didn't work`, `What worked`) stored in `lessons_learned`.
3. **Zero-Click Injection (Future Decision):** On any future chat turn or command error, the `inject_experiential_memory` middleware queries `lessons_learned` and injects proven solutions directly into the prompt context.

---

## Key Features
- **Experiential Learning (ExpeL / Reflexion Postmortems):** Distills complex debugging sessions into structured `Lessons Learned` cards indexed into ChromaDB with zero-click context injection.
- **Self-Correction (Evaluator Node):** Automatic detection of tool execution failures (e.g. non-zero exit codes or system errors) in LangGraph, routing execution back to the agent with error details for self-healing (up to 3 retry attempts).
- **Negative Feedback Reflexion:** Submitting negative feedback (thumbs-down) on AI responses triggers a background LLM Reflexion pipeline to analyze the failure, extract a lesson, and store it in ChromaDB's `LessonStore` to avoid repeating the mistake.
- **Lean RAG Knowledge Base:** Automatically chunks and indexes executed SSH command outputs, logs, and server configs into separate **ChromaDB** collections.
- **Semantic Guardrails:** Uses local vector search to intercept and block dangerous terminal commands.
- **Human-in-the-Loop (HITL):** Enforces admin approval (`[y/N]`) inside the terminal for any state-modifying actions.
- **CLI Connection Resilience:** Automatically reconnects to the WebSocket server using exponential backoff if the network drops or the server restarts.
- **Real-Time Streaming:** Streams LLM thoughts and active SSH `stdout`/`stderr` line-by-line using WebSockets with 30s execution timeouts.
- **Encrypted Credentials:** Securely encrypts passwords and SSH private keys using Fernet (AES-256).
- **Server & Session CRUD & Feedback:** Full REST API support for managing server connections, deleting sessions, and submitting user satisfaction ratings.
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
