"""
FastAPI route definitions for health, applications, resume upload, and chat.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse
from ..models.schemas import ApplicationRecord, ResumeProfile, ChatRequest
from ..repositories.job_repo import JobRepository, get_job_repository
from ..repositories.app_repo import ApplicationRepository
from ..agents.parser_agent import ResumeParserAgent
from ..agents.orchestrator import OrchestratorAgent
from ..services.document_extractor import DocumentExtractionError
from .dependencies import get_current_session, get_application_repo, SessionState, get_session_store, SessionStore

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


class DirectApplyBody(BaseModel):
    job_id: str
    notes: Optional[str] = None


@router.post("/apply", tags=["Applications"])
def direct_apply(
    body: DirectApplyBody,
    session: SessionState = Depends(get_current_session),
    app_repo: ApplicationRepository = Depends(get_application_repo),
    job_repo: JobRepository = Depends(get_job_repository)
):
    """Direct 1-click apply endpoint for job cards."""
    job = job_repo.get_by_id(body.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    record, is_new = app_repo.create_application(
        session_id=session.session_id,
        job=job,
        notes=body.notes
    )

    return {
        "success": True,
        "is_duplicate": not is_new,
        "message": f"Application recorded for {job.title} at {job.company} (Status: APPLIED)." if is_new else f"You already applied to {job.title} at {job.company}.",
        "application": record.model_dump()
    }


@router.post("/jobs/{job_id}/report-closed", tags=["Jobs"])
def report_closed_job(
    job_id: str,
    job_repo: JobRepository = Depends(get_job_repository)
):
    """Allows candidates to report an expired or filled role, deactivating it platform-wide."""
    success = job_repo.mark_job_inactive(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or already deactivated")
    return {
        "success": True,
        "message": "Job marked as closed/inactive. It will no longer be recommended to users.",
        "job_id": job_id
    }


@router.post("/chat", tags=["Chat"])
async def chat_stream(
    request: ChatRequest,
    x_session_id: Optional[str] = Header(None, description="Optional header override for session UUID"),
    store: SessionStore = Depends(get_session_store),
    app_repo: ApplicationRepository = Depends(get_application_repo),
    job_repo: JobRepository = Depends(get_job_repository)
):
    """
    Conversational chat endpoint with Server-Sent Events (SSE) streaming.
    Streams real-time sub-agent handoffs, thoughts, tokens, and interactive job cards.
    Accepts session ID via request body or X-Session-Id header.
    """
    session_id = (request.session_id or x_session_id or "").strip()
    session = store.get_or_create(session_id)
    orchestrator = OrchestratorAgent(job_repo=job_repo, session_store=store)

    return StreamingResponse(
        orchestrator.stream_chat(
            session=session,
            user_message=request.message,
            app_repo=app_repo,
            filter_overrides=request.filter_overrides,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/upload", response_model=Dict[str, Any], tags=["Resume"])
async def upload_resume(
    file: UploadFile = File(...),
    session: SessionState = Depends(get_current_session)
):
    """
    Upload and auto-parse candidate resume (PDF or DOCX).
    Extracts name, contact, designation, skills, experience, education, and projects.
    Saves extracted profile to user's active session.
    """
    # 1. Validate file extension
    filename = file.filename or "resume.pdf"
    if not (filename.lower().endswith(".pdf") or filename.lower().endswith(".docx") or filename.lower().endswith(".doc")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a PDF or DOCX resume."
        )

    # 2. Read file bytes with size check (max 10MB)
    try:
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds maximum allowed limit of 10MB."
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {e}"
        )

    # 3. Parse resume with ResumeParserAgent
    try:
        parser = ResumeParserAgent()
        profile = parser.parse_document(content, filename)

        # 4. Save to session context & reset stale conversational filters for clean matching
        session.resume_profile = profile
        session.active_filters = ActiveFilters()

        return {
            "status": "success",
            "message": f"Resume parsed successfully for {profile.name} ({profile.designation}).",
            "profile": profile.model_dump()
        }

    except DocumentExtractionError as e:
        # Handles unreadable, scanned, or corrupt document specifically as required by JD
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while parsing the resume: {str(e)}"
        )


@router.get("/resume", response_model=Dict[str, Any], tags=["Resume"])
def get_parsed_resume(session: SessionState = Depends(get_current_session)):
    """Retrieve the parsed resume profile for the current session."""
    if not session.resume_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resume has been uploaded in this session yet."
        )
    return {
        "status": "success",
        "profile": session.resume_profile.model_dump()
    }


@router.get("/applications", response_model=List[ApplicationRecord], tags=["Applications"])
def list_applications(
    session: SessionState = Depends(get_current_session),
    app_repo: ApplicationRepository = Depends(get_application_repo)
):
    """Retrieve all jobs applied by the current user session."""
    return app_repo.get_user_applications(session.session_id)

