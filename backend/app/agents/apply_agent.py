"""
Application & Tracker Sub-Agent.
Handles:
1. Index-to-ID resolution ('apply to job 3' -> exact job ID).
2. Database deduplication via unique constraints.
3. Fetching previously applied jobs for status queries.
4. Edge-case handling: invalid job references and graceful session defaults.
"""
from typing import Dict, Any, List, Optional
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
        Resolves index and guarantees database recording with duplicate prevention.
        """
        # 1. Edge-Case: Candidate must have uploaded a resume first
        if not session.resume_profile:
            return ApplicationResult(
                success=False,
                message="Please upload your resume (PDF/DOCX) on the left first so your qualifications can be attached to the application!"
            )

        # 2. Resolve reference to actual Job ID
        job_id = session.resolve_job_index_or_id(job_reference)

        # Fallback: if reference is direct job ID
        if not job_id:
            all_matching = [j for j in self.job_repo.get_all() if j.id == job_reference.strip()]
            if all_matching:
                job_id = all_matching[0].id

        if not job_id:
            available_indices = len(session.last_results)
            if available_indices > 0:
                hint = f"Please select a number between 1 and {available_indices} from the recommended list."
            else:
                hint = "Please ask me to recommend jobs first so I can list them with numbers."

            return ApplicationResult(
                success=False,
                message=f"I couldn't find a job matching '{job_reference}'. {hint}"
            )

        # Retrieve job from repository
        job = self.job_repo.get_by_id(job_id)
        if not job:
            return ApplicationResult(
                success=False,
                message=f"Job listing '{job_id}' is no longer active."
            )

        # Check & insert into database (handles duplicate constraint)
        record, is_new = self.app_repo.create_application(
            session_id=session.session_id,
            job=job,
            notes=notes
        )

        if not is_new:
            applied_date = record.applied_at[:10] if record.applied_at else "earlier"
            return ApplicationResult(
                success=True,
                is_duplicate=True,
                message=(
                    f"**Already Applied:** You previously submitted an application for **{job.title}** at **{job.company}** on {applied_date}.\n\n"
                    f"- **Status:** `{record.status}`\n"
                    f"- **Notice:** Duplicate submissions are prevented."
                ),
                application=record
            )

        resume_note = ""
        if not session.resume_profile:
            resume_note = "\n- *(Tip: Attach your resume in chat anytime to update your candidate profile).*"

        return ApplicationResult(
            success=True,
            is_duplicate=False,
            message=(
                f"**Application Recorded:** Your profile has been submitted for **{job.title}** at **{job.company}**.\n\n"
                f"- **Status:** `{record.status}` | **Job ID:** `{job.id}`\n"
                f"- **Tracking:** Saved to your 'Applied Jobs' drawer\n"
                f"- **Official Posting:** [View Role on {job.source or 'Portal'}]({job.source_url}){resume_note}"
            ),
            application=record
        )

    def list_applied_jobs(self, session_id: str) -> List[ApplicationRecord]:
        """Fetch all applications for the session."""
        return self.app_repo.get_user_applications(session_id)
