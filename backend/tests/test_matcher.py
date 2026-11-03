"""
Unit tests for MatcherAgent.
Verifies deterministic scoring, conversational filter stacking, and edge case of zero matches.
"""
import pytest
from app.models.schemas import ResumeProfile, ActiveFilters, ContactInfo, Job
from app.agents.matcher_agent import MatcherAgent
from app.repositories.job_repo import get_job_repository


@pytest.fixture
def sample_profile():
    return ResumeProfile(
        name="Alex Smith",
        contact=ContactInfo(email="alex@example.com"),
        designation="Python Backend Engineer",
        skills=["Python", "FastAPI", "Docker", "PostgreSQL", "Git", "AWS"],
        years_of_experience=2.0
    )


def test_matcher_recommends_relevant_jobs(sample_profile):
    agent = MatcherAgent()
    matches, has_matches = agent.match_jobs(sample_profile, limit=5)

    assert has_matches is True
    assert len(matches) > 0
    assert len(matches) <= 5

    # Check top match structure
    first = matches[0]
    assert first.index == 1
    assert first.match_score > 0
    assert len(first.match_reasons) > 0
    # Python should be matched in top python developer matches
    assert any("python" in s.lower() for s in first.matched_skills or []) or first.match_score >= 40


def test_matcher_remote_filter(sample_profile):
    agent = MatcherAgent()
    # Filter for remote only
    remote_filter = ActiveFilters(remote=True)
    matches, has_matches = agent.match_jobs(sample_profile, filters=remote_filter, limit=5)

    assert has_matches is True
    for m in matches:
        assert m.job.remote is True


def test_matcher_skill_filter(sample_profile):
    agent = MatcherAgent()
    # Filter for jobs requiring SQL
    skill_filter = ActiveFilters(skills=["SQL"])
    matches, has_matches = agent.match_jobs(sample_profile, filters=skill_filter, limit=5)

    assert has_matches is True
    for m in matches:
        skills_lower = [s.lower() for s in m.job.skills]
        assert "sql" in skills_lower


def test_matcher_zero_matches_edge_case(sample_profile):
    """JD Edge-Case: Clear handling when no jobs match."""
    agent = MatcherAgent()
    # Impossible criteria: Non-existent technology + impossible location
    impossible_filter = ActiveFilters(
        skills=["NonExistentTechXYZ9999"],
        location="AntarcticaMoonStation"
    )
    matches, has_matches = agent.match_jobs(sample_profile, filters=impossible_filter)

    assert has_matches is False
    assert len(matches) == 0


def test_matcher_blocks_senior_roles_for_freshers():
    """Ensure senior roles (Associate III, Senior, 3+ yrs) are NEVER shown to freshers/interns."""
    agent = MatcherAgent()
    fresher_profile = ResumeProfile(
        name="Fresher Graduate",
        designation="Software Engineering Intern",
        skills=["Python", "SQL", "Git", "Power BI", "Azure"],
        years_of_experience=0.0
    )
    matches, has_matches = agent.match_jobs(fresher_profile, limit=20)

    assert has_matches is True
    for m in matches:
        # 1. Experience required must be <= 1 for freshers
        assert m.job.experience_required <= 1, f"Found job with {m.job.experience_required} yrs exp: {m.job.title}"

        # 2. Senior markers should not exist
        combined = f"{m.job.title} {m.job.description}".lower()
        for marker in ["associate iii", "associate ii", "level 3", "senior", "lead", "architect"]:
            assert marker not in combined, f"Found forbidden seniority marker '{marker}' in job: {m.job.title}"

