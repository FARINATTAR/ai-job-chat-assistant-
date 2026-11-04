"""
Unit tests for JSearchSource API adapter and MNC job ingestion.
"""
from scraper.jsearch_source import JSearchSource
from app.repositories.job_repo import JobRepository


def test_jsearch_source_graceful_fallback_without_key():
    source = JSearchSource(api_key="")
    jobs = source.fetch_jobs(target_count=10)
    assert jobs == []


def test_jsearch_normalized_job_schema_ingestion(tmp_path):
    test_json = tmp_path / "test_jobs.json"
    test_json.write_text("[]", encoding="utf-8")

    repo = JobRepository(json_path=str(test_json))

    # Mock sample job matching JSearch normalized output
    sample_jsearch_job = {
        "id": "js_abc12345",
        "title": "Software Development Engineer Intern",
        "company": "Amazon",
        "location": "Bengaluru, India",
        "workplace_type": "on-site",
        "remote": False,
        "experience_required": 0,
        "skills": ["Java", "AWS", "Python", "Data Structures"],
        "description": "Amazon is hiring SDE Interns for our cloud infrastructure team.",
        "source_url": "https://www.linkedin.com/jobs/view/999999999",
        "source": "LinkedIn",
        "is_active": True,
    }

    added = repo.upsert_jobs([sample_jsearch_job])
    assert added == 1
    assert repo.total_count == 1

    stored = repo.get_by_id("js_abc12345")
    assert stored is not None
    assert stored.company == "Amazon"
    assert stored.source == "LinkedIn"
    assert stored.remote is False
    assert stored.experience_required == 0

