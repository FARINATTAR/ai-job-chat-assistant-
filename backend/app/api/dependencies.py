"""
FastAPI dependency injections for database, job repository, and session store.
"""
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from ..core.db import get_db
from ..core.session import SessionStore, get_session_store, SessionState
from ..repositories.job_repo import JobRepository, get_job_repository
from ..repositories.app_repo import ApplicationRepository


def get_current_session(
    x_session_id: str = Header(..., description="Anonymous user session UUID"),
    store: SessionStore = Depends(get_session_store)
) -> SessionState:
    """Retrieve or create session from X-Session-Id header."""
    if not x_session_id or not x_session_id.strip():
        raise HTTPException(status_code=400, detail="X-Session-Id header is required")
    return store.get_or_create(x_session_id.strip())


def get_application_repo(db: Session = Depends(get_db)) -> ApplicationRepository:
    return ApplicationRepository(db)

