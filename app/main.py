from fastapi import FastAPI

app = FastAPI(
    title="DevOps-RAG API",
    description="An AI-driven DevOps management agent for bare-metal servers.",
    version="0.1.0",
)

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
