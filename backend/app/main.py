"""
Main FastAPI Application Entrypoint.
Initializes the in-memory JobRepository and database on startup.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .core.db import init_db
from .repositories.job_repo import get_job_repository
from .services.job_refresher import periodic_job_refresher
from .api.endpoints import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database tables and load jobs into memory
    print("[Startup] Initializing database...")
    init_db()

    print("[Startup] Pre-loading jobs dataset into memory...")
    repo = get_job_repository()
    print(f"[Startup] Ready! Loaded {repo.total_count} jobs.")

    # Start automated background job refresher (syncs fresh roles every 60 mins)
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(
        periodic_job_refresher(stop_event, interval_seconds=3600)
    )

    yield

    # Shutdown
    print("[Shutdown] Stopping background workers and cleaning up resources...")
    stop_event.set()
    worker_task.cancel()
    try:
        await worker_task
    except (asyncio.CancelledError, Exception):
        pass


app = FastAPI(
    title="AI Job Chat Assistant API",
    description="Backend API for conversational job assistant with resume parsing, matching, and application tracking.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware configuration
cors_origins = settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app" if not settings.DEBUG else None,
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

