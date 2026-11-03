"""
Repositories package for data access.
"""
from .job_repo import JobRepository, get_job_repository
from .app_repo import ApplicationRepository

__all__ = ["JobRepository", "get_job_repository", "ApplicationRepository"]
