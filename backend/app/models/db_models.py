"""
SQLAlchemy database models.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, UniqueConstraint
from ..core.db import Base


class ApplicationDB(Base):
    """
    Tracks job applications submitted by users in their session.
    Enforces a database-level unique constraint on (session_id, job_id)
    to prevent duplicate applications.
    """
    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), index=True, nullable=False)
    job_id = Column(String(64), nullable=False)
    job_title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255), default="")
    source_url = Column(String(500), default="")
    applied_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    status = Column(String(50), default="APPLIED", nullable=False)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("session_id", "job_id", name="uq_session_job"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "job_id": self.job_id,
            "job_title": self.job_title,
            "company": self.company,
            "location": self.location,
            "source_url": self.source_url,
            "applied_at": self.applied_at.isoformat() if self.applied_at else "",
            "status": self.status,
            "notes": self.notes or ""
        }
