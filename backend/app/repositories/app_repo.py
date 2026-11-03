"""
Repository for managing job applications in the database.
Handles duplicate detection and status queries.
"""
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ..models.db_models import ApplicationDB
from ..models.schemas import Job, ApplicationRecord


class ApplicationRepository:
    def __init__(self, db: Session):
        self.db = db

    def has_applied(self, session_id: str, job_id: str) -> bool:
        """Check if user has already applied to this job in their session."""
        return self.db.query(ApplicationDB).filter(
            ApplicationDB.session_id == session_id,
            ApplicationDB.job_id == job_id
        ).first() is not None

    def create_application(self, session_id: str, job: Job, notes: Optional[str] = None) -> Tuple[Optional[ApplicationRecord], bool]:
        """
        Record a job application.
        Returns (ApplicationRecord, is_new).
        If already applied, returns (existing_record, False).
        """
        # 1. First check if already exists
        existing = self.db.query(ApplicationDB).filter(
            ApplicationDB.session_id == session_id,
            ApplicationDB.job_id == job.id
        ).first()

        if existing:
            return ApplicationRecord(**existing.to_dict()), False

        # 2. Insert new record
        new_app = ApplicationDB(
            session_id=session_id,
            job_id=job.id,
            job_title=job.title,
            company=job.company,
            location=job.location,
            source_url=job.source_url,
            status="APPLIED",
            notes=notes
        )

        try:
            self.db.add(new_app)
            self.db.commit()
            self.db.refresh(new_app)
            return ApplicationRecord(**new_app.to_dict()), True
        except IntegrityError:
            self.db.rollback()
            existing = self.db.query(ApplicationDB).filter(
                ApplicationDB.session_id == session_id,
                ApplicationDB.job_id == job.id
            ).first()
            if existing:
                return ApplicationRecord(**existing.to_dict()), False
            raise

    def get_user_applications(self, session_id: str) -> List[ApplicationRecord]:
        """Get all jobs applied by the current user session, ordered by most recent."""
        records = self.db.query(ApplicationDB).filter(
            ApplicationDB.session_id == session_id
        ).order_by(ApplicationDB.applied_at.desc()).all()

        return [ApplicationRecord(**r.to_dict()) for r in records]

