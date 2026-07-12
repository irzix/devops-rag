# DevOps-RAG

A modular FastAPI project for AI-driven DevOps management.

## Requirements

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) (recommended)

## Quick Start

1. Create a virtual environment and install dependencies:
   ```bash
   uv venv
   uv pip install -r pyproject.toml
   ```

2. Run the development server:
   ```bash
   uv run uvicorn app.main:app --reload
   ```

3. Open the API documentation:
   - Swagger UI: http://127.0.0.1:8000/docs
   - ReDoc: http://127.0.0.1:8000/redoc
