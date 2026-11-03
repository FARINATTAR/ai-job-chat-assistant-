"""
Job Matcher Sub-Agent.
Matches candidate ResumeProfile against the verified software engineering job dataset.
Uses strict deterministic skill-overlap scoring, experience suitability,
and title similarity to ensure 100% relevant software jobs with zero hallucination.
"""
import re
from typing import List, Dict, Any, Tuple, Optional
from ..models.schemas import Job, ResumeProfile, JobMatch, ActiveFilters
from ..repositories.job_repo import JobRepository, get_job_repository
from ..llm.client import LLMClient, get_llm_client


class MatcherAgent:
    """Sub-agent responsible for ranking jobs and generating grounded explanations."""

    def __init__(self, job_repo: Optional[JobRepository] = None, llm_client: Optional[LLMClient] = None):
        self.job_repo = job_repo or get_job_repository()
        self.llm = llm_client or get_llm_client()

    def match_jobs(
        self,
        profile: ResumeProfile,
        filters: Optional[ActiveFilters] = None,
        limit: int = 10
    ) -> Tuple[List[JobMatch], bool]:
        """
        Rank top software jobs for the candidate considering active conversational filters.
        Returns (ranked_job_matches, has_matches).
        """
        filters = filters or ActiveFilters()
        all_jobs = self.job_repo.get_all()

        if not all_jobs:
            return [], False

        candidate_skills_lower = set(s.strip().lower() for s in profile.skills if s.strip())
        candidate_title = profile.designation.lower()
        candidate_exp = profile.years_of_experience

        scored_candidates: List[Tuple[Job, int, List[str], List[str]]] = []

        for job in all_jobs:
            # 1. Apply conversational filters
            if filters.remote is True and not job.remote:
                continue
            if filters.remote is False and job.remote:
                continue
            if filters.location and filters.location.lower() not in job.location.lower():
                continue
            if filters.skills:
                job_skills_lower = set(s.strip().lower() for s in job.skills)
                requested_lower = set(s.strip().lower() for s in filters.skills)
                if not job_skills_lower.intersection(requested_lower):
                    continue

            # Experience-Gate & User Filter
            title_and_desc = f"{job.title} {job.description}".lower()
            senior_markers = [
                "associate iii", "associate ii", "level 3", "level 2", "lead",
                "senior", "sr.", "principal", "staff engineer", "architect", "manager"
            ]

            # 1. User Explicit Experience Filter (Takes top precedence if chosen)
            if filters.max_experience is not None:
                if job.experience_required > filters.max_experience:
                    continue
                # If user explicitly asked for Fresher/Entry-level (<= 1 yr), filter out senior titles
                if filters.max_experience <= 1 and any(marker in title_and_desc for marker in senior_markers):
                    continue

            # 2. Candidate Resume Profile Gating (When no explicit experience filter is active)
            else:
                # If candidate is fresher/intern/early-career (<= 1.0 yr exp)
                if candidate_exp <= 1.0 or "intern" in candidate_title:
                    if job.experience_required > 1:
                        continue
                    if any(marker in title_and_desc for marker in senior_markers):
                        continue
                else:
                    if job.experience_required > candidate_exp:
                        continue

            # 2. Strict Score Calculation
            score, matched_skills, missing_skills = self._calculate_match_score(
                candidate_skills_lower=candidate_skills_lower,
                candidate_title=candidate_title,
                candidate_exp=candidate_exp,
                job=job
            )

            # Only retain candidates with score >= 15 to eliminate irrelevant noise
            if score >= 15:
                scored_candidates.append((job, score, matched_skills, missing_skills))

        # Sort by match score descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        if not scored_candidates:
            return [], False

        top_candidates = scored_candidates[:limit]
        job_matches: List[JobMatch] = []

        for idx, (job, score, matched_skills, missing_skills) in enumerate(top_candidates, start=1):
            reasons = self._generate_grounded_reasons(
                profile=profile,
                job=job,
                matched_skills=matched_skills,
                score=score
            )

            job_matches.append(JobMatch(
                index=idx,
                job=job,
                match_score=score,
                match_reasons=reasons,
                matched_skills=matched_skills,
                missing_skills=missing_skills
            ))

        return job_matches, True

    def _calculate_match_score(
        self,
        candidate_skills_lower: set,
        candidate_title: str,
        candidate_exp: float,
        job: Job
    ) -> Tuple[int, List[str], List[str]]:
        """
        High-precision matching formula:
        - Exact skill matching (no false-positive character substrings)
        - Title & Tech Domain similarity
        - Experience suitability
        """
        job_skills = job.skills or []
        matched_skills: List[str] = []
        missing_skills: List[str] = []

        # 1. Clean Exact Skill Matching
        for orig_skill in job_skills:
            s_low = orig_skill.strip().lower()
            if s_low in candidate_skills_lower:
                matched_skills.append(orig_skill)
            else:
                missing_skills.append(orig_skill)

        num_matched = len(matched_skills)
        total_req = max(len(job_skills), 3)

        if num_matched == 0:
            skill_score = 0.0
        else:
            # Multi-skill overlap reward curve
            skill_score = min(100.0, (num_matched / total_req) * 115.0)

        # 2. Title & Role Relevance
        title_low = job.title.lower()
        title_score = 30.0

        tech_roles = ["software", "developer", "engineer", "frontend", "backend", "full stack", "fullstack", "sde", "intern", "web", "data", "ai", "cloud"]
        cand_words = set(re.findall(r"\w+", candidate_title))

        # Title keyword overlap
        if any(w in title_low for w in cand_words if len(w) > 3):
            title_score = 85.0
        elif any(r in title_low for r in tech_roles):
            title_score = 65.0

        # 3. Experience Fit
        req_exp = float(job.experience_required)
        if candidate_exp >= req_exp:
            exp_score = 100.0
        elif req_exp - candidate_exp <= 1.0:
            exp_score = 80.0
        elif req_exp - candidate_exp <= 2.0:
            exp_score = 50.0
        else:
            exp_score = 20.0

        # If zero technical skills matched and title is weak, reject early
        if num_matched == 0 and title_score < 70:
            return 0, [], missing_skills

        # Weighted Composite Score
        total_score = int(0.60 * skill_score + 0.25 * title_score + 0.15 * exp_score)
        total_score = max(10, min(98, total_score))

        return total_score, matched_skills, missing_skills

    def _generate_grounded_reasons(
        self,
        profile: ResumeProfile,
        job: Job,
        matched_skills: List[str],
        score: int
    ) -> List[str]:
        """Produce factual, verified bullet points."""
        reasons: List[str] = []

        if matched_skills:
            count = len(matched_skills)
            skills_preview = ", ".join(matched_skills[:5])
            reasons.append(f"Matches {count} verified technical skill{'' if count == 1 else 's'}: {skills_preview}.")
        else:
            reasons.append("Software engineering role matching your core technology track.")

        req_exp = job.experience_required
        cand_exp = profile.years_of_experience
        if req_exp == 0:
            reasons.append("Entry-level / Internship role suited for students, freshers, and early engineers.")
        elif cand_exp >= req_exp:
            reasons.append(f"Your {cand_exp:g} yrs experience fully meets the {req_exp} yrs requirement.")
        else:
            reasons.append(f"Requires {req_exp} yrs; your background provides a strong foundational fit.")

        if job.remote:
            reasons.append("100% Remote flexibility.")
        elif job.location:
            reasons.append(f"Located in {job.location}.")

        return reasons[:3]
