FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy application files (ignoring directories defined in .dockerignore)
COPY . /app

# Install the package along with its optional server dependencies directly
RUN uv pip install --system .[server]

# Create persistent storage directory for SQLite and ChromaDB
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
