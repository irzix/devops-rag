# Contributing to DevOps Copilot

Thank you for your interest in contributing to DevOps Copilot! 🚀

## Quick Start for Contributors

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- [Ollama](https://ollama.com/download) (for free local LLM)
- Docker & Docker Compose (optional, for demo environment)

### 1. Fork & Clone

```bash
git clone https://github.com/<your-username>/devops-copilot.git
cd devops-copilot
```

### 2. Set Up Development Environment

```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[server]"

# Install dev tools
uv pip install ruff pytest pytest-asyncio httpx

# Copy and configure environment
cp .env.example .env
```

### 3. Set Up Local LLM (Free)

```bash
# Install Ollama and pull a model
ollama pull qwen2.5:7b
```

### 4. Run the Server

```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Run Tests

```bash
pytest tests/ -v
```

### 6. Run Linter

```bash
ruff check app/
ruff format app/
```

---

## Development Guidelines

### Code Style

- We use **Ruff** for linting and formatting (line length: 88)
- All code must pass `ruff check` and `ruff format --check` before merging
- Use type hints for all function signatures
- Write docstrings for public functions and classes

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Ollama support for local LLM inference
fix: resolve SSH timeout on large log fetches
docs: update README with demo instructions
refactor: extract LLM factory to core module
test: add unit tests for guardrails service
```

### Pull Request Process

1. **Fork** the repo and create a feature branch from `main`
2. Make your changes with clear, focused commits
3. Add or update tests for new functionality
4. Ensure all tests pass: `pytest tests/ -v`
5. Ensure linting passes: `ruff check app/`
6. Open a PR with a clear description of what and why

### Architecture Overview

```
app/
├── core/           # Config, database, LLM factories, encryption
├── modules/
│   ├── auth/       # JWT authentication (single-user)
│   ├── servers/    # Server CRUD + SSH credentials
│   ├── guardrails/ # Semantic command blacklist (ChromaDB)
│   ├── knowledge/  # ChromaDB indexing service
│   ├── chat/       # LangGraph agent + WebSocket router
│   └── memory/     # 7-store memory system (ExpeL, Reflexion)
└── cli/            # Typer CLI client
```

### Key Conventions

- **LLM calls**: Use `get_llm()` for streaming (agent node only), `get_llm_non_streaming()` for background tasks
- **Database**: All DB operations must be async via `async_session_maker()`
- **SSH**: All SSH operations go through `execute_ssh_command` tool with guardrails
- **Memory**: Always use `owner_id` for tenant isolation in ChromaDB queries

---

## Good First Issues

Look for issues labeled [`good first issue`](https://github.com/irzix/devops-copilot/labels/good%20first%20issue) for beginner-friendly tasks.

Ideas for contributions:
- Add more read-only command prefixes to `is_write_command()`
- Expand the guardrails blacklist with more dangerous commands
- Add unit tests for existing modules
- Improve CLI output formatting
- Add new tool capabilities to the agent

---

## Reporting Bugs

Please open an [issue](https://github.com/irzix/devops-copilot/issues) with:
- Steps to reproduce
- Expected vs actual behavior
- Environment info (OS, Python version, Ollama/OpenRouter model)

## Questions?

Open a [Discussion](https://github.com/irzix/devops-copilot/discussions) for questions, ideas, or feature requests.
