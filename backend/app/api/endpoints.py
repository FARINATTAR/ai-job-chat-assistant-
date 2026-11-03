"""
FastAPI route definitions for health, applications, resume upload, and chat.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from ..models.schemas import ApplicationRecord
from ..repositories.job_repo import JobRepository, get_job_repository
from ..repositories.app_repo import ApplicationRepository
from .dependencies import get_current_session, get_application_repo, SessionState

router = APIRouter(prefix="/api")


@router.get("/health", tags=["Health"])
def health_check(job_repo: JobRepository = Depends(get_job_repository)):
    """Health check endpoint reporting system status and jobs in memory."""
    return {
        "status": "healthy",
        "service": "AI Job Chat Assistant Backend",
        "jobs_loaded": job_repo.total_count,
        "database": "connected"
    }


@router.get("/applications", response_model=List[ApplicationRecord], tags=["Applications"])
def list_applications(
    session: SessionState = Depends(get_current_session),
    app_repo: ApplicationRepository = Depends(get_application_repo)
):
    """Retrieve all jobs applied by the current user session."""
    return app_repo.get_user_applications(session.session_id)

