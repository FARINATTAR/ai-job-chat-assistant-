"""
Unit and integration tests for OrchestratorAgent and chat flows.
Verifies intent detection, agent handoffs, conversational refinement, and application workflows.
"""
import asyncio
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


def test_intent_detection_apply(orchestrator):
    assert orchestrator.detect_intent("apply to job 2") == {"intent": "APPLY", "reference": "2"}
    assert orchestrator.detect_intent("apply for job 1") == {"intent": "APPLY", "reference": "1"}
    assert orchestrator.detect_intent("apply to 3") == {"intent": "APPLY", "reference": "3"}


def test_intent_detection_tracking(orchestrator):
    assert orchestrator.detect_intent("show my applied jobs") == {"intent": "TRACK"}
    assert orchestrator.detect_intent("what are my applications") == {"intent": "TRACK"}
    assert orchestrator.detect_intent("application status") == {"intent": "TRACK"}


def test_intent_detection_greeting(orchestrator):
    assert orchestrator.detect_intent("hi") == {"intent": "GREETING"}
    assert orchestrator.detect_intent("hello there") == {"intent": "GREETING"}


def test_intent_detection_filters(orchestrator):
    res = orchestrator.detect_intent("show only remote roles")
    assert res["intent"] == "SEARCH_OR_REFINE"
    assert res["is_remote"] is True

    res2 = orchestrator.detect_intent("reset filters")
    assert res2["intent"] == "RESET_FILTERS"


def test_orchestrator_chat_stream_greeting(orchestrator):
    async def run():
        store = SessionStore()
        session = store.get_or_create("test_session_chat_1")
        db = SessionLocal()
        app_repo = ApplicationRepository(db)

        events = []
        async for event in orchestrator.stream_chat(session, "hi", app_repo):
            events.append(event)
        db.close()

        full_output = "".join(events)
        assert "agent_start" in full_output
        assert "AI Job Chat Assistant" in full_output

    asyncio.run(run())


def test_orchestrator_chat_stream_recommend_and_apply(orchestrator):
    async def run():
        import uuid
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
        events = []
        async for event in orchestrator.stream_chat(session, "recommend matching jobs for me", app_repo):
            events.append(event)

        full_output = "".join(events)
        assert "JobMatcher" in full_output
        assert "job_results" in full_output
        assert len(session.last_results) > 0  # Index mapping created!

        # 2. Apply to job 1
        apply_events = []
        async for event in orchestrator.stream_chat(session, "apply to job 1", app_repo):
            apply_events.append(event)

        apply_output = "".join(apply_events)
        assert "ApplicationManager" in apply_output
        assert "Successfully applied" in apply_output

        # 3. Duplicate apply to job 1
        dup_events = []
        async for event in orchestrator.stream_chat(session, "apply to job 1", app_repo):
            dup_events.append(event)

        dup_output = "".join(dup_events)
        assert "already" in dup_output.lower()

        # 4. Track applied jobs
        track_events = []
        async for event in orchestrator.stream_chat(session, "show my applied jobs", app_repo):
            track_events.append(event)

        track_output = "".join(track_events)
        assert "You have applied to" in track_output

        db.close()

    asyncio.run(run())
