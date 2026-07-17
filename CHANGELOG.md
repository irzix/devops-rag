# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Web UI with dedicated server management page.
- Notifications module.
- Monitoring module with background scheduler.
- Server tags and expanded server schemas.
- `LLM_PROVIDER` configuration for explicit OpenRouter/Ollama selection.
- `SECURITY.md`, `CODE_OF_CONDUCT.md`, and this changelog.

## [0.1.4] - 2025

### Added
- MIT LICENSE for open-source distribution.
- GitHub Actions workflow for PyPI Trusted Publishing (OIDC).
- GitHub Actions CI workflow for lint (`ruff`) and tests (`pytest`).
- Unit tests for auth, security, agent, and LLM config modules.
- `CONTRIBUTING.md` and GitHub issue templates.
- README rewritten for open-source adoption.
- Ollama support for free, local LLM inference.
- Docker Compose demo environment with a sandboxed SSH server.
- LangSmith tracing integration for LangGraph agent observability.

### Fixed
- CLI hang after human-in-the-loop approval.
- Deterministic `action_id` generation to prevent duplicate/colliding IDs.
- `GraphInterrupt` re-raised correctly in `tools_node` so LangGraph pauses as expected.
- LangGraph approval loop caused by non-deterministic `action_id`.
- Self-correction loop now skips terminal SSH/network errors to avoid infinite approval loops.
- Auto-migration for new database columns on app startup.

### Changed
- Extracted LLM factories into `app/core/llm.py`.
- Cleaned up imports and extracted constants in the reflexion pipeline.

## Earlier History

Prior to 0.1.4, the project evolved through its core architecture: the
LangGraph `StateGraph` agent, the 7-store memory system (semantic, lesson,
episodic, user-fact, procedural, plus consolidation and reflexion pipelines),
semantic guardrails backed by ChromaDB, SSH tooling via AsyncSSH, and JWT-based
auth. See `git log` for full detail predating this changelog.

[Unreleased]: https://github.com/irzix/devops-copilot/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/irzix/devops-copilot/releases/tag/v0.1.4
