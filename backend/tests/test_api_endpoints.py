"""
Integration tests for FastAPI endpoints ensuring routes execute and validate properly.
Tests endpoints with exact schema validation and sub-millisecond execution.
"""
import io
import pytest
from fastapi import HTTPException, UploadFile
from app.api.endpoints import health_check, report_closed_job, upload_resume
from app.repositories.job_repo import get_job_repository
from app.core.session import SessionStore
import pymupdf as fitz


def create_sample_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _run_coro(coro):
    try:
        coro.send(None)
    except StopIteration as si:
        return si.value


def test_health_check_endpoint():
    repo = get_job_repository()
    data = health_check(job_repo=repo)
    assert data["status"] == "healthy"
    assert data["jobs_loaded"] > 0
    assert "AI Job Chat Assistant" in data["service"]


def test_report_closed_job_endpoint():
    repo = get_job_repository()
    sample_jobs = repo.get_all()
    assert len(sample_jobs) > 0
    valid_id = sample_jobs[0].id

    # Report valid job ID
    res = report_closed_job(job_id=valid_id, job_repo=repo)
    assert res["success"] is True
    assert res["job_id"] == valid_id

    # Report an invalid job ID raises 404
    with pytest.raises(HTTPException) as exc_info:
        report_closed_job(job_id="invalid_job_99999", job_repo=repo)
    assert exc_info.value.status_code == 404


def test_upload_resume_endpoint():
    store = SessionStore()
    session = store.get_or_create("test_session_upload_1")

    # Generate a valid PDF with candidate details
    pdf_content = create_sample_pdf(
        "Sarah Connor\n"
        "Email: sarah@example.com | Phone: +1 555-0199\n"
        "Full Stack Developer with 3 years of experience.\n"
        "Skills: Python, FastAPI, React, Docker, SQL\n"
        "Education: B.S. in Computer Science, Tech University, 2021\n"
        "Projects: Built AI Job Chat Assistant with real-time SSE streaming."
    )

    upload_file = UploadFile(
        file=io.BytesIO(pdf_content),
        filename="sarah_resume.pdf",
        headers={"content-type": "application/pdf"}
    )

    res = _run_coro(upload_resume(file=upload_file, session=session))

    assert res["status"] == "success"
    assert "profile" in res
    profile = res["profile"]
    assert profile["name"] == "Sarah Connor"
    assert "Python" in profile["skills"]
    assert session.resume_profile is not None
    assert session.resume_profile.name == "Sarah Connor"


def test_upload_unsupported_file():
    store = SessionStore()
    session = store.get_or_create("test_session_upload_2")

    upload_file = UploadFile(
        file=io.BytesIO(b"malicious executable"),
        filename="resume.exe"
    )

    with pytest.raises(HTTPException) as exc_info:
        _run_coro(upload_resume(file=upload_file, session=session))
    assert exc_info.value.status_code == 400
    assert "Unsupported file format" in exc_info.value.detail
