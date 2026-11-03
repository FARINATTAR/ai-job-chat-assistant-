"""
Main FastAPI Application Entrypoint.
Initializes the in-memory JobRepository and database on startup.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .core.db import init_db
from .repositories.job_repo import get_job_repository
from .api.endpoints import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database tables and load jobs into memory
    print("[Startup] Initializing database...")
    init_db()

    print("[Startup] Pre-loading jobs dataset into memory...")
    repo = get_job_repository()
    print(f"[Startup] Ready! Loaded {repo.total_count} jobs.")

    yield

    # Shutdown
    print("[Shutdown] Cleaning up resources...")


app = FastAPI(
    title="AI Job Chat Assistant API",
    description="Backend API for conversational job assistant with resume parsing, matching, and application tracking.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local dev and Vercel deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router)


@app.get("/")
def root():
    return {
        "message": "AI Job Chat Assistant Backend is running.",
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)

