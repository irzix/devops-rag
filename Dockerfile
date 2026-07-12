FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency configuration files
COPY pyproject.toml /app/

# Install dependencies directly into system python of the container
RUN uv pip install --system -r pyproject.toml

# Copy application code
COPY app /app/app

# Create persistent storage directory for SQLite and ChromaDB
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
