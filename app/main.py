from fastapi import FastAPI
from app.modules.users.router import router as users_router

app = FastAPI(
    title="SaaS API (FastAPI)",
    description="A modular FastAPI project styled after NestJS architectural concepts.",
    version="1.0.0",
)

# Register routers (analogous to importing Controllers/Routers inside AppModule)
app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
