"""
In-memory repository for jobs data loaded from data/jobs.json.
Provides sub-millisecond filtering, keyword search, and indexing.
"""
import json
import os
import re
from typing import List, Dict, Optional, Any, Set
from ..models.schemas import Job, ActiveFilters
from ..config import settings


class JobRepository:
    """Fast in-memory storage and search engine for scraped job listings."""

    def __init__(self, json_path: Optional[str] = None):
        self.json_path = json_path or settings.JOBS_DATA_PATH
        self._jobs: List[Job] = []
        self._jobs_by_id: Dict[str, Job] = {}
        self._skills_index: Dict[str, Set[str]] = {}  # skill_lower -> set of job_ids
        self._load_jobs()

    def _load_jobs(self):
        """Load and index jobs from JSON file."""
        if not os.path.exists(self.json_path):
            print(f"[JobRepository] Warning: File not found at {self.json_path}")
            return

        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            self._jobs = []
            self._jobs_by_id = {}
            self._skills_index = {}

            for item in raw_data:
                try:
                    job = Job(**item)
                    self._jobs.append(job)
                    self._jobs_by_id[job.id] = job

                    # Build inverted skills index
                    for s in job.skills:
                        s_lower = s.strip().lower()
                        if s_lower not in self._skills_index:
                            self._skills_index[s_lower] = set()
                        self._skills_index[s_lower].add(job.id)

                except Exception as ex:
                    # Skip malformed items gracefully
                    continue

            print(f"[JobRepository] Successfully loaded {len(self._jobs)} jobs into memory.")
        except Exception as e:
            print(f"[JobRepository] Error reading jobs file {self.json_path}: {e}")

    @property
    def total_count(self) -> int:
        return len(self._jobs)

    def get_all(self) -> List[Job]:
        return self._jobs

    def get_by_id(self, job_id: str) -> Optional[Job]:
        return self._jobs_by_id.get(job_id)

    def filter_jobs(self, filters: ActiveFilters, limit: int = 50) -> List[Job]:
        """Apply active conversational filters."""
        results = self._jobs

        # Remote filter
        if filters.remote is not None:
            results = [j for j in results if j.remote == filters.remote]

        # Experience filter
        if filters.max_experience is not None:
            results = [j for j in results if j.experience_required <= filters.max_experience]

        # Location filter
        if filters.location:
            loc_query = filters.location.lower().strip()
            results = [j for j in results if loc_query in j.location.lower()]

        # Skills filter (must match at least one of the requested skills)
        if filters.skills:
            filter_skills_lower = [s.lower().strip() for s in filters.skills]
            matching_ids: Set[str] = set()
            for s in filter_skills_lower:
                matching_ids.update(self._skills_index.get(s, set()))
                # Partial match in inverted index
                for indexed_skill, ids in self._skills_index.items():
                    if s in indexed_skill:
                        matching_ids.update(ids)
            
            if matching_ids:
                results = [j for j in results if j.id in matching_ids]

        # Free text query
        if filters.query:
            q_terms = [t.lower() for t in re.findall(r"\w+", filters.query) if len(t) > 2]
            if q_terms:
                def matches_query(job: Job) -> bool:
                    searchable = f"{job.title} {job.company} {job.description}".lower()
                    return any(term in searchable for term in q_terms)
                results = [j for j in results if matches_query(j)]

        return results[:limit]


# Global singleton instance
_job_repository_instance: Optional[JobRepository] = None


def get_job_repository() -> JobRepository:
    global _job_repository_instance
    if _job_repository_instance is None:
        _job_repository_instance = JobRepository()
    return _job_repository_instance

