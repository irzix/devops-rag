# DevOps Copilot 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/irzix/devops-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/irzix/devops-rag/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/devops-copilot.svg)](https://pypi.org/project/devops-copilot/)

**An autonomous, self-learning AI DevOps agent that manages bare-metal servers with Memory-First Architecture, Experiential Learning, and Real-Time SSH Tunneling.**

<!-- 
🎬 DEMO GIF HERE
Record with: vhs or asciinema
![DevOps Copilot Demo](docs/demo.gif) 
-->

---

## ⚡ What Makes This Different?

Unlike standard AI chat wrappers that forget previous troubleshooting sessions, DevOps Copilot **learns from every incident** and **never repeats dead ends**:

| Feature | Traditional Tools | DevOps Copilot |
|---------|------------------|----------------|
| Memory across sessions | ❌ | ✅ 7-store memory system |
| Learns from past incidents | ❌ | ✅ ExpeL postmortems |
| Blocks dangerous commands | ❌ | ✅ Semantic guardrails |
| Self-corrects on failure | ❌ | ✅ 3-retry evaluator |
| Requires approval for writes | ❌ | ✅ Human-in-the-loop |

---

## 🚀 Quick Start (2 minutes)

### Option A: Local with Ollama (Free, No API Key)

```bash
# 1. Install Ollama → https://ollama.com/download
ollama pull qwen2.5:7b

# 2. Clone and configure
git clone https://github.com/irzix/devops-rag.git
cd devops-rag
cp .env.example .env

# 3. Run with Docker
docker compose -f docker-compose.demo.yaml up -d
```

### Option B: Cloud with OpenRouter

```bash
# Same as above, but edit .env:
# Comment out OLLAMA_BASE_URL
# Set OPENROUTER_API_KEY=your_key_here
```

### Register & Start Chatting

```bash
# Install CLI client
uv pip install -e .

# Create admin account
devops-copilot login

# Start chatting with your servers
devops-copilot chat
```

> 💡 **Try the demo**: The `docker-compose.demo.yaml` includes a sandboxed SSH server (`demo` / `demo123`) so you can experiment safely without real infrastructure.

---

## 🏛️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DevOps Copilot CLI                        │
│     (Typer + WebSocket Streaming + [y/N] Approval)          │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST + WebSocket
┌──────────────────────▼──────────────────────────────────────┐
│                   FastAPI Backend                            │
│                                                             │
│   ┌──────────────────────────────────────────────────────┐  │
│   │          LangGraph StateGraph Agent                   │  │
│   │                                                      │  │
│   │  read_memory → agent → tools → evaluator → agent     │  │
│   │       │                  │         │           │      │  │
│   │       ▼                  ▼         ▼           ▼      │  │
│   │  MemoryManager    SSH/Knowledge   Self-       write   │  │
│   │  (7 stores)       Guardrails     Correction   _memory │  │
│   │                   HITL           (×3 retry)           │  │
│   └──────────────────────────────────────────────────────┘  │
│                                                             │
│   ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐  │
│   │   Auth    │ │  Servers  │ │ Guardrails│ │ Knowledge │  │
│   │  (JWT)    │ │ (AsyncSSH)│ │ (Vector)  │ │ (ChromaDB)│  │
│   └───────────┘ └───────────┘ └───────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### The Agent Flow

1. **`read_memory`** — Retrieves lessons learned, episodic summaries, and user facts from ChromaDB
2. **`agent`** — LLM reasoning with all tools bound (Ollama or OpenRouter)
3. **`tools`** — Executes SSH commands, searches knowledge, fetches logs/configs
4. **`evaluator`** — Detects failures, triggers self-correction (up to 3 retries)
5. **`write_memory`** — Background extraction of facts and episodic summaries

### Experiential Learning (ExpeL)

```
 Incident Occurs → Agent Diagnoses → Resolution Found
                                           │
                      ┌────────────────────▼────────────────────┐
                      │         Automatic Postmortem             │
                      │  Problem | Root Cause | What Worked      │
                      │  What Didn't Work | Time to Resolve      │
                      └────────────────────┬────────────────────┘
                                           │
                                    ChromaDB Index
                                           │
                      Next Similar Incident ▼
                      ┌─────────────────────────────────────────┐
                      │  "I've seen this before. Last time,      │
                      │   restarting X didn't work but Y fixed   │
                      │   it in 5 minutes. Let me try Y first."  │
                      └─────────────────────────────────────────┘
```

---

## ✨ Key Features

- **🧠 Memory-First Architecture** — 7 ChromaDB stores (Semantic, Lesson, Episodic, UserFact, Procedural) with automatic read/write on every turn
- **🔁 Experiential Learning (ExpeL)** — Structured postmortems indexed and auto-injected into future troubleshooting
- **🛡️ Semantic Guardrails** — Vector search blocks dangerous commands (`rm -rf /`, `mkfs`, etc.) before execution
- **🧑‍💻 Human-in-the-Loop** — Write commands require `[y/N]` approval via LangGraph's native `interrupt`
- **🔄 Self-Correction** — Evaluator node retries failed commands up to 3 times with error context
- **⚡ Real-Time Streaming** — SSH stdout/stderr streamed line-by-line via WebSocket
- **🔒 Encrypted Credentials** — SSH passwords and keys encrypted at rest with Fernet (AES-256)
- **📊 LangSmith Tracing** — Optional full observability of graph nodes, tools, and memory operations
- **🦙 Ollama Support** — Run completely free and local with no API keys

---

## 🏗️ Project Structure

```
app/
├── core/
│   ├── config.py            # Pydantic settings (env vars)
│   ├── database/            # Async SQLite engine + auto-migration
│   ├── llm.py               # LLM factories (Ollama + OpenRouter)
│   └── security.py          # Fernet AES-256 encryption
├── modules/
│   ├── auth/                # JWT authentication
│   ├── servers/             # Server CRUD + SSH credentials
│   ├── guardrails/          # Semantic command blacklist
│   ├── knowledge/           # ChromaDB indexing service
│   ├── chat/
│   │   ├── agent.py         # LangGraph StateGraph definition
│   │   ├── router.py        # WebSocket handler + REST endpoints
│   │   ├── models.py        # ChatSession, ChatMessage, AgentAction
│   │   └── schema.py        # Pydantic request/response schemas
│   └── memory/
│       ├── manager.py       # MemoryManager (read_context / write_after_turn)
│       ├── stores.py        # 7 ChromaDB collection wrappers
│       ├── extraction.py    # LLM fact extraction pipeline
│       ├── consolidation.py # Deduplication before persistence
│       ├── summarizer.py    # Episodic session summarizer
│       ├── reflexion.py     # Negative feedback analysis pipeline
│       └── types.py         # AgentState, ExtractedFact, MemoryContext
├── cli/                     # Typer CLI client
└── tests/                   # Unit & integration tests
```

---

## 🔧 Configuration

### LLM Providers

| Provider | Cost | Setup | Best For |
|----------|------|-------|----------|
| **Ollama** | Free | `ollama pull qwen2.5:7b` | Development, self-hosted |
| **OpenRouter** | Pay-per-use | Get API key at [openrouter.ai](https://openrouter.ai) | Production, best models |

### Environment Variables

See [`.env.example`](.env.example) for all available configuration options.

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, coding standards, and guidelines.

**Good first issues:**
- Add more read-only command prefixes to `is_write_command()`
- Expand the guardrails blacklist with more dangerous patterns
- Add unit tests for existing modules
- Improve CLI output formatting

---

## 📄 License

[MIT](LICENSE) © [irzix](https://github.com/irzix)
