"""
Pydantic schemas for data validation, serialization, and LLM structured outputs.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Job(BaseModel):
    """Standardized job listing schema matching data/jobs.json."""
    id: str
    title: str
    company: str
    location: str
    workplace_type: str = "remote"
    remote: bool = False
    experience_required: int = 0
    skills: List[str] = Field(default_factory=list)
    description: str = ""
    source_url: str = ""
    source: Optional[str] = "unknown"
    posted_at: Optional[str] = ""
    is_active: bool = True


class ContactInfo(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None


class EducationItem(BaseModel):
    degree: Optional[str] = None
    institution: Optional[str] = None
    year: Optional[str] = None


class ProjectItem(BaseModel):
    name: str
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)


class ResumeProfile(BaseModel):
    """Structured extraction of candidate resume required by assessment JD."""
    name: str = "Candidate"
    contact: ContactInfo = Field(default_factory=ContactInfo)
    designation: str = "Software Engineer"
    skills: List[str] = Field(default_factory=list)
    years_of_experience: float = 0.0
    experience_summary: Optional[str] = None
    education: List[EducationItem] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)


class JobMatch(BaseModel):
    """Recommendation result containing grounded match explanation."""
    index: int  # 1-based index (e.g., Job 1, Job 2) for natural chat referencing
    job: Job
    match_score: int  # 0 to 100
    match_reasons: List[str] = Field(default_factory=list)
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)


class ActiveFilters(BaseModel):
    """Conversational filters applied across chat turns."""
    remote: Optional[bool] = None
    skills: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    max_experience: Optional[int] = None
    source: Optional[str] = None  # "LinkedIn", "Arbeitnow", "Remotive", or None
    page: int = 1
    offset: int = 0
    query: Optional[str] = None


class ApplicationCreate(BaseModel):
    job_reference: str  # Can be index ("2") or direct ID ("jf_...")
    notes: Optional[str] = None


class ApplicationRecord(BaseModel):
    """Application record saved in DB."""
    id: str
    session_id: str
    job_id: str
    job_title: str
    company: str
    applied_at: str
    status: str = "APPLIED"
    source_url: Optional[str] = None
    notes: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    message: str
    session_id: str
    agent_trace: Optional[List[Dict[str, Any]]] = None
    job_results: Optional[List[JobMatch]] = None

