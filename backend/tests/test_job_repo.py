"""
Unit tests for JobRepository upsert and background syncing.
"""
import pytest
from app.repositories.job_repo import JobRepository
from app.models.schemas import Job


def test_job_repo_upsert_and_deduplication(tmp_path):
    # Create empty temporary json file
    test_json = tmp_path / "test_jobs.json"
    test_json.write_text("[]", encoding="utf-8")

    repo = JobRepository(json_path=str(test_json))
    assert repo.total_count == 0

    batch = [
        {
            "id": "test_job_1",
            "title": "Software Engineer",
            "company": "Acme Corp",
            "location": "Remote",
            "remote": True,
            "skills": ["Python", "Docker"],
            "experience_required": 1,
            "description": "Building microservices.",
            "source_url": "https://example.com/job1",
            "source": "Remotive"
        },
        {
            "id": "test_job_2",
            "title": "Frontend Engineer",
            "company": "Beta LLC",
            "location": "New York",
            "remote": False,
            "skills": ["React", "TypeScript"],
            "experience_required": 2,
            "description": "Frontend UI.",
            "source_url": "https://example.com/job2",
            "source": "Arbeitnow"
        }
    ]

    added = repo.upsert_jobs(batch)
    assert added == 2
    assert repo.total_count == 2
    assert repo.get_by_id("test_job_1") is not None

    # Verify duplicate prevention: ingesting the exact same batch adds 0
    added_dup = repo.upsert_jobs(batch)
    assert added_dup == 0
    assert repo.total_count == 2

    # Ingesting a job with same title and company but different ID is also deduplicated
    similar_job = [
        {
            "id": "test_job_3",
            "title": "Software Engineer",
            "company": "Acme Corp",
            "location": "Onsite",
            "remote": False,
            "skills": ["Python"],
            "description": "Duplicate title and company.",
            "source_url": "https://example.com/job3"
        }
    ]
    added_similar = repo.upsert_jobs(similar_job)
    assert added_similar == 0
    assert repo.total_count == 2


def test_job_repo_mark_inactive(tmp_path):
    test_json = tmp_path / "test_jobs.json"
    test_json.write_text("[]", encoding="utf-8")

    repo = JobRepository(json_path=str(test_json))
    batch = [
        {
            "id": "job_to_deactivate",
            "title": "Backend Intern",
            "company": "Tech Corp",
            "location": "Remote",
            "remote": True,
            "skills": ["Python"],
            "experience_required": 0,
            "source_url": "https://example.com/expired",
        }
    ]
    repo.upsert_jobs(batch)
    assert repo.get_by_id("job_to_deactivate").is_active is True

    # Mark as inactive
    ok = repo.mark_job_inactive("job_to_deactivate")
    assert ok is True
    assert repo.get_by_id("job_to_deactivate").is_active is False

    # Deactivating unknown job returns False
    assert repo.mark_job_inactive("non_existent_id") is False

