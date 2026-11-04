"""
Integration tests for FastAPI endpoints ensuring routes import and execute properly.
"""
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["jobs_loaded"] > 0


def test_report_closed_job_endpoint():
    # Report a valid job ID
    response = client.post("/api/jobs/jf_6ae6dbc3000d846108df/report-closed")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Report an invalid job ID
    response = client.post("/api/jobs/invalid_job_99999/report-closed")
    assert response.status_code == 404
