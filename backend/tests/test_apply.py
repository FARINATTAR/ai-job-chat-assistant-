"""
Unit and integration tests for ApplyAgent.
Verifies index resolution, duplicate prevention, and invalid reference handling.
"""
import uuid
import pytest
from app.core.db import SessionLocal, init_db
from app.core.session import SessionStore
from app.models.schemas import ResumeProfile, ContactInfo
from app.repositories.app_repo import ApplicationRepository
from app.repositories.job_repo import get_job_repository
from app.agents.apply_agent import ApplyAgent


@pytest.fixture(scope="module")
def setup_database():
    init_db()


@pytest.fixture
def db_session(setup_database):
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def session_and_agent(db_session):
    store = SessionStore()
    session = store.get_or_create(f"test_session_{uuid.uuid4().hex[:8]}")

    # Attach sample resume profile
    session.resume_profile = ResumeProfile(
        name="Test User",
        contact=ContactInfo(email="test@example.com"),
        designation="Software Engineer",
        skills=["Python", "FastAPI"],
        years_of_experience=1.0
    )

    # Prepopulate last_results with real job IDs from the repository
    job_repo = get_job_repository()
    sample_jobs = job_repo.get_all()[:3]
    session.last_results = [j.id for j in sample_jobs]

    app_repo = ApplicationRepository(db_session)
    agent = ApplyAgent(app_repo=app_repo, session_store=store, job_repo=job_repo)

    return session, agent, sample_jobs


def test_apply_by_index_success(session_and_agent):
    session, agent, sample_jobs = session_and_agent

    # Apply to job 1
    result = agent.apply_to_job(session=session, job_reference="job 1")

    assert result.success is True
    assert result.is_duplicate is False
    assert result.application is not None
    assert result.application.job_id == sample_jobs[0].id
    assert result.application.status == "APPLIED"


def test_apply_duplicate_prevention(session_and_agent):
    """JD Requirement: Applications are saved and not duplicated."""
    session, agent, sample_jobs = session_and_agent

    # First apply
    first_res = agent.apply_to_job(session=session, job_reference="2")
    assert first_res.success is True
    assert first_res.is_duplicate is False

    # Second apply to the exact same job
    second_res = agent.apply_to_job(session=session, job_reference="2")
    assert second_res.success is True
    assert second_res.is_duplicate is True
    assert "already" in second_res.message.lower()


def test_apply_invalid_job_reference(session_and_agent):
    """JD Edge-Case: Clear handling of invalid job references."""
    session, agent, _ = session_and_agent

    # Out of bounds index
    bad_result = agent.apply_to_job(session=session, job_reference="job 99")
    assert bad_result.success is False
    assert "couldn't find" in bad_result.message.lower()


def test_apply_without_resume_uploaded(session_and_agent):
    """Edge-Case: Prevent applying before uploading resume."""
    session, agent, _ = session_and_agent
    session.resume_profile = None  # Remove resume

    result = agent.apply_to_job(session=session, job_reference="1")
    assert result.success is False
    assert "upload your resume" in result.message.lower()


def test_list_applied_jobs(session_and_agent):
    """JD Requirement: 'show my applied jobs'."""
    session, agent, _ = session_and_agent
    # Re-attach resume
    session.resume_profile = ResumeProfile(name="Test User", skills=["Python"])

    # Apply to job 1
    agent.apply_to_job(session=session, job_reference="1")

    # List applications
    apps = agent.list_applied_jobs(session.session_id)
    assert len(apps) >= 1
    assert any(a.job_id == session.last_results[0] for a in apps)

