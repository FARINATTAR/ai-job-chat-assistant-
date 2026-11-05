"""
Unit and integration tests for OrchestratorAgent and chat flows.
Verifies LLM tool-calling intent detection (with regex fallback),
agent handoffs, conversational refinement, and application workflows.
"""
import uuid
import pytest
from app.agents.orchestrator import OrchestratorAgent
from app.core.session import SessionStore
from app.core.db import SessionLocal, init_db
from app.repositories.app_repo import ApplicationRepository
from app.repositories.job_repo import get_job_repository
from app.models.schemas import ResumeProfile, ContactInfo


@pytest.fixture(scope="module")
def setup_db():
    init_db()


@pytest.fixture
def orchestrator():
    return OrchestratorAgent()


def _run_agen(agen):
    """Consumes an async generator synchronously without an event loop."""
    items = []
    while True:
        try:
            coro = agen.asend(None)
            try:
                coro.send(None)
            except StopIteration as si:
                items.append(si.value)
        except StopAsyncIteration:
            break
    return items


def test_intent_detection_apply(orchestrator):
    """Verify apply intents resolve to the apply_to_job tool with correct job reference."""
    res = orchestrator.detect_intent("apply to job 2")
    assert res["tool"] == "apply_to_job"
    assert res["args"]["job_number"] == "2"

    res2 = orchestrator.detect_intent("apply for job 1")
    assert res2["tool"] == "apply_to_job"
    assert res2["args"]["job_number"] == "1"

    res3 = orchestrator.detect_intent("apply to 3")
    assert res3["tool"] == "apply_to_job"
    assert res3["args"]["job_number"] == "3"


def test_intent_detection_tracking(orchestrator):
    """Verify application tracking queries route to list_applications tool."""
    assert orchestrator.detect_intent("show my applied jobs")["tool"] == "list_applications"
    assert orchestrator.detect_intent("what are my applications")["tool"] == "list_applications"
    assert orchestrator.detect_intent("application status")["tool"] == "list_applications"


def test_intent_detection_greeting(orchestrator):
    """Verify greetings route to greet_user tool."""
    assert orchestrator.detect_intent("hi")["tool"] == "greet_user"
    assert orchestrator.detect_intent("hello there")["tool"] == "greet_user"


def test_intent_detection_filters(orchestrator):
    """Verify filter queries route to recommend_jobs with correct parameters."""
    res = orchestrator.detect_intent("show only remote roles")
    assert res["tool"] == "recommend_jobs"
    assert res["args"].get("remote") is True

    res2 = orchestrator.detect_intent("reset filters")
    assert res2["tool"] == "reset_filters"


def test_intent_detection_skills(orchestrator):
    """Verify skill mentions are extracted into recommend_jobs args."""
    res = orchestrator.detect_intent("show me Python and React jobs")
    assert res["tool"] == "recommend_jobs"
    assert "Python" in res["args"].get("skills", [])
    assert "React" in res["args"].get("skills", [])


def test_intent_detection_no_false_greeting(orchestrator):
    """Verify 'hi' substring in longer words doesn't trigger greeting."""
    res = orchestrator.detect_intent("show me jobs at higher companies")
    assert res["tool"] == "recommend_jobs"

    res2 = orchestrator.detect_intent("history of my applications")
    assert res2["tool"] != "greet_user"


def test_orchestrator_chat_stream_greeting(orchestrator, setup_db):
    """Verify greeting flow streams agent_start and greeting message."""
    store = SessionStore()
    session = store.get_or_create("test_session_chat_1")
    db = SessionLocal()
    app_repo = ApplicationRepository(db)

    events = _run_agen(orchestrator.stream_chat(session, "hi", app_repo))
    db.close()

    full_output = "".join(events)
    assert "agent_start" in full_output
    assert "AI Job Chat Assistant" in full_output


def test_orchestrator_chat_stream_recommend_and_apply(orchestrator, setup_db):
    """End-to-end: recommend jobs, apply to job 1, check duplicate, track applications."""
    store = SessionStore()
    unique_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    session = store.get_or_create(unique_id)
    db = SessionLocal()
    app_repo = ApplicationRepository(db)

    # Set up candidate profile
    session.resume_profile = ResumeProfile(
        name="Sarah Connor",
        contact=ContactInfo(email="sarah@example.com"),
        designation="Python Developer",
        skills=["Python", "FastAPI", "SQL", "Docker"],
        years_of_experience=2.0
    )

    # 1. Ask for recommendations
    events = _run_agen(orchestrator.stream_chat(session, "recommend matching jobs for me", app_repo))
    full_output = "".join(events)
    assert "JobMatcher" in full_output
    assert "job_results" in full_output
    assert len(session.last_results) > 0

    # 2. Apply to job 1
    apply_events = _run_agen(orchestrator.stream_chat(session, "apply to job 1", app_repo))
    apply_output = "".join(apply_events)
    assert "ApplicationManager" in apply_output
    assert "Application Recorded" in apply_output

    # 3. Duplicate apply to job 1
    dup_events = _run_agen(orchestrator.stream_chat(session, "apply to job 1", app_repo))
    dup_output = "".join(dup_events)
    assert "already" in dup_output.lower()

    # 4. Track applied jobs
    track_events = _run_agen(orchestrator.stream_chat(session, "show my applied jobs", app_repo))
    track_output = "".join(track_events)
    assert "You have applied to" in track_output

    db.close()
