"""
Application & Tracker Sub-Agent.
Handles:
1. Index-to-ID resolution ('apply to job 3' -> exact job ID).
2. Database deduplication via unique constraints.
3. Fetching previously applied jobs for status queries.
4. Edge-case handling: invalid job references and applying without a resume.
"""
from typing import Dict, Any, List, Optional, Tuple
from ..models.schemas import Job, ApplicationRecord, ResumeProfile
from ..core.session import SessionStore, get_session_store, SessionState
from ..repositories.job_repo import JobRepository, get_job_repository
from ..repositories.app_repo import ApplicationRepository


class ApplicationResult:
    def __init__(self, success: bool, message: str, application: Optional[ApplicationRecord] = None, is_duplicate: bool = False):
        self.success = success
        self.message = message
        self.application = application
        self.is_duplicate = is_duplicate

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "is_duplicate": self.is_duplicate,
            "application": self.application.model_dump() if self.application else None
        }


class ApplyAgent:
    """Sub-agent responsible for submitting and tracking job applications."""

    def __init__(
        self,
        app_repo: ApplicationRepository,
        session_store: Optional[SessionStore] = None,
        job_repo: Optional[JobRepository] = None
    ):
        self.app_repo = app_repo
        self.session_store = session_store or get_session_store()
        self.job_repo = job_repo or get_job_repository()

    def apply_to_job(
        self,
        session: SessionState,
        job_reference: str,
        notes: Optional[str] = None
    ) -> ApplicationResult:
        """
        Apply to a job using natural reference (e.g., '1', 'job 2', 'jf_...').
        Enforces resume requirement, index resolution, and duplicate prevention.
        """
        # 1. Edge-Case: Candidate must have uploaded a resume first
        if not session.resume_profile:
            return ApplicationResult(
                success=False,
                message="Please upload your resume first before applying so we can submit your qualifications."
            )

        # 2. Edge-Case: Resolve reference to actual Job ID
        job_id = session.resolve_job_index_or_id(job_reference)
        if not job_id:
            available_indices = len(session.last_results)
            if available_indices > 0:
                hint = f"Please choose a number between 1 and {available_indices} from the recommended list."
            else:
                hint = "Please ask to search for matching jobs first so I can list them for you."
            
            return ApplicationResult(
                success=False,
                message=f"I couldn't find a job matching '{job_reference}'. {hint}"
            )

        # 3. Retrieve job from repository
        job = self.job_repo.get_by_id(job_id)
        if not job:
            return ApplicationResult(
                success=False,
                message=f"Job listing with ID '{job_id}' is no longer available."
            )

        # 4. Check & insert into database (handles duplicate constraint)
        record, is_new = self.app_repo.create_application(
            session_id=session.session_id,
            job=job,
            notes=notes
        )

        if not is_new:
            # Duplicate application detected
            applied_date = record.applied_at[:10] if record.applied_at else "earlier"
            return ApplicationResult(
                success=True,
                is_duplicate=True,
                message=f"You already submitted an application for **{job.title}** at **{job.company}** on {applied_date}. Status: **{record.status}**.",
                application=record
            )

        return ApplicationResult(
            success=True,
            is_duplicate=False,
            message=f"Successfully applied to **{job.title}** at **{job.company}**! Your application has been recorded.",
            application=record
        )

    def list_applied_jobs(self, session_id: str) -> List[ApplicationRecord]:
        """Fetch all applications for the session."""
        return self.app_repo.get_user_applications(session_id)
