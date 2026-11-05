"""
Job Matcher Sub-Agent.
Matches candidate ResumeProfile against the verified software engineering job dataset.
Uses strict deterministic skill-overlap scoring, experience suitability,
and title similarity to ensure 100% relevant software jobs with zero hallucination.
"""
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from ..models.schemas import Job, ResumeProfile, JobMatch, ActiveFilters
from ..repositories.job_repo import JobRepository, get_job_repository
from ..llm.client import LLMClient, get_llm_client


def parse_job_date(posted_at: Any) -> Optional[datetime]:
    if not posted_at:
        return None
    try:
        s = str(posted_at).strip()
        if s.isdigit():
            ts = float(s)
            if ts > 1e11:
                ts /= 1000
            return datetime.fromtimestamp(ts, tz=timezone.utc).date()
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


CAREER_DOMAINS = {
    "embedded": ["embedded", "firmware", "iot", "hardware", "microcontroller", "rtos", "arm", "pcb", "fpga", "robotics", "device driver"],
    "hr": ["hr", "human resources", "talent acquisition", "recruiter", "recruitment", "people operations", "staffing", "human capital", "onboarding"],
    "data": ["data analyst", "data engineer", "data scientist", "analytics", "bi developer", "tableau", "power bi", "etl", "data warehouse"],
    "design": ["designer", "ui/ux", "product design", "figma", "graphic design", "user experience"],
    "qa": ["qa", "tester", "testing", "quality assurance", "sdet", "test automation"],
    "devops": ["devops", "cloud engineer", "sre", "site reliability", "infrastructure", "platform engineer", "kubernetes"],
    "ai_ml": ["ai", "machine learning", "deep learning", "nlp", "computer vision", "genai", "generative ai", "llm", "azure openai", "rag", "prompt engineering"],
    "frontend": ["frontend", "react", "next.js", "vue", "angular", "ui developer", "web developer"],
    "backend": ["backend", "api", "fastapi", "django", "node", "express", "golang", "java developer"],
    "marketing": ["marketing", "seo", "sem", "content strategy", "social media", "google ads", "hubspot", "brand management", "email marketing", "growth hacking"],
    "finance": ["finance", "accounting", "chartered accountant", "ca", "cfa", "investment banking", "financial analyst"],
}

# Domains where the dataset might have limited direct matches
NICHE_DOMAINS = {"hr", "design", "marketing", "finance", "legal", "medical"}


class MatcherAgent:
    """Sub-agent responsible for ranking jobs and generating grounded explanations."""

    def __init__(self, job_repo: Optional[JobRepository] = None, llm_client: Optional[LLMClient] = None):
        self.job_repo = job_repo or get_job_repository()
        self.llm = llm_client or get_llm_client()

    @staticmethod
    def _detect_domain(candidate_title: str, candidate_skills_lower: set) -> str:
        """Detect primary career domain of candidate."""
        combined = candidate_title.lower() + " " + " ".join(candidate_skills_lower)
        for dom, kws in CAREER_DOMAINS.items():
            for k in kws:
                if len(k) <= 3:
                    if re.search(r"\b" + re.escape(k) + r"\b", combined):
                        return dom
                elif k in combined:
                    return dom
        # If title or skills contain tech/software markers, classify as software
        software_markers = [
            "software", "developer", "engineer", "programmer", "coding",
            "sde", "swe", "web", "computer", "tech", "it", "fullstack",
            "backend", "frontend", "intern"
        ]
        for marker in software_markers:
            if len(marker) <= 3:
                if re.search(r"\b" + re.escape(marker) + r"\b", combined):
                    return "software"
            elif marker in combined:
                return "software"
        return "other"

    def match_jobs(
        self,
        profile: ResumeProfile,
        filters: Optional[ActiveFilters] = None,
        limit: int = 10
    ) -> Tuple[List[JobMatch], bool]:
        """
        Rank top jobs for the candidate considering active conversational filters.
        Returns (ranked_job_matches, has_matches).
        """
        filters = filters or ActiveFilters()
        all_jobs = self.job_repo.get_all()

        if not all_jobs:
            return [], False

        candidate_skills_lower = set(s.strip().lower() for s in profile.skills if s.strip())
        candidate_title = profile.designation.lower()
        candidate_exp = profile.years_of_experience
        cand_domain = self._detect_domain(candidate_title, candidate_skills_lower)

        scored_candidates: List[Tuple[Job, int, List[str], List[str]]] = []

        for job in all_jobs:
            # 0. Skip any expired or inactive job
            if getattr(job, "is_active", True) is False:
                continue

            # 1. Apply conversational filters
            if filters.remote is True and not job.remote:
                continue
            if filters.remote is False and job.remote:
                continue
            if filters.location and filters.location.lower() not in job.location.lower():
                continue
            if filters.source and filters.source.lower() not in (job.source or "").lower():
                continue
            if filters.skills:
                job_skills_lower = set(s.strip().lower() for s in job.skills)
                requested_lower = set(s.strip().lower() for s in filters.skills)
                if not job_skills_lower.intersection(requested_lower):
                    continue

            # Company filter
            if filters.company and filters.company.lower() not in (job.company or "").lower():
                continue

            # Date posted recency filter (e.g. 1 day for 24h, 3 days, 7 days)
            if filters.posted_within_days is not None:
                job_date = parse_job_date(job.posted_at)
                if job_date:
                    today = datetime.now(timezone.utc).date()
                    if (today - job_date).days > filters.posted_within_days:
                        continue
                else:
                    continue

            # Role / Query filter
            if filters.query:
                q_term = filters.query.lower()
                job_full = f"{job.title} {job.company} {job.description} {' '.join(job.skills)}".lower()
                
                # Expand domain synonyms
                terms_to_match = [q_term]
                if q_term in ["sde", "software engineer", "swe", "software developer"]:
                    terms_to_match = ["sde", "software development engineer", "software engineer", "software developer", "developer"]
                elif "full stack" in q_term or "fullstack" in q_term:
                    terms_to_match = ["full stack", "fullstack"]
                elif "ai" in q_term or "ml" in q_term or "machine learning" in q_term:
                    terms_to_match = ["machine learning", "artificial intelligence", "ai", "ml"]

                if not any(t in job_full for t in terms_to_match):
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

            # 2. Candidate Resume Profile Gating (When no explicit experience filter is active and not querying specific company)
            elif not filters.company:
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

        # 1. Deduplicate identical (company, title)
        seen_keys = set()
        deduped_candidates = []
        for item in scored_candidates:
            j = item[0]
            k = (j.company.strip().lower(), j.title.strip().lower())
            if k in seen_keys:
                continue
            seen_keys.add(k)
            deduped_candidates.append(item)

        # 2. Source Balancing: If user didn't request a specific source, prevent any single platform from dominating
        if not (filters and filters.source):
            balanced_candidates = []
            pool = list(deduped_candidates)
            while pool:
                found_idx = None
                for idx, item in enumerate(pool):
                    src = (item[0].source or "Other").lower()
                    if (
                        len(balanced_candidates) >= 2
                        and (balanced_candidates[-1][0].source or "Other").lower() == src
                        and (balanced_candidates[-2][0].source or "Other").lower() == src
                    ):
                        continue
                    found_idx = idx
                    break

                if found_idx is not None:
                    balanced_candidates.append(pool.pop(found_idx))
                else:
                    balanced_candidates.extend(pool)
                    break
            deduped_candidates = balanced_candidates

        if not deduped_candidates:
            return [], False

        offset = filters.offset if filters else 0
        top_candidates = deduped_candidates[offset : offset + limit]
        job_matches: List[JobMatch] = []

        for idx, (job, score, matched_skills, missing_skills) in enumerate(top_candidates, start=offset + 1):
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

        # 2. Domain & Title Alignment
        cand_domain = self._detect_domain(candidate_title, candidate_skills_lower)
        title_low = job.title.lower()
        job_skills_lower = set(s.strip().lower() for s in job_skills)

        # Check if job belongs to candidate's domain
        is_job_in_domain = False
        if cand_domain in CAREER_DOMAINS:
            dom_kws = CAREER_DOMAINS[cand_domain]
            if (
                any(k in title_low for k in dom_kws)
                or any(k in s for s in job_skills_lower for k in dom_kws)
            ):
                is_job_in_domain = True
        else:
            is_job_in_domain = False

        # For niche domains or completely out-of-league fields: if no skill overlap AND job is not in domain, reject
        # to avoid polluting results with random tech jobs
        if (cand_domain in NICHE_DOMAINS or cand_domain == "other") and not is_job_in_domain and num_matched == 0:
            return 0, [], missing_skills

        # Title score calculation
        cand_words = set(re.findall(r"\w+", candidate_title))
        title_score = 30.0

        if any(w in title_low for w in cand_words if len(w) > 3):
            title_score = 90.0
        elif is_job_in_domain:
            title_score = 80.0
        elif cand_domain == "software" and any(r in title_low for r in ["software", "developer", "engineer", "sde"]):
            title_score = 65.0
        else:
            title_score = 15.0

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

        # Early rejection for zero skill overlap and weak title
        if num_matched == 0 and title_score < 70:
            return 0, [], missing_skills

        # Weighted Composite Score
        total_score = int(0.55 * skill_score + 0.30 * title_score + 0.15 * exp_score)

        # Domain Alignment Bonus
        if is_job_in_domain and cand_domain != "software":
            total_score += 20

        # Brand Boost (Only awarded if candidate has real skill or domain relevance)
        top_tier = [
            "google", "amazon", "microsoft", "apple", "meta", "adobe", "uber",
            "atlassian", "salesforce", "cisco", "flipkart", "oracle",
            "goldman sachs", "jpmorgan", "intuit", "phonepe", "swiggy", "zomato"
        ]
        comp_lower = (job.company or "").lower()
        if (num_matched > 0 or is_job_in_domain) and any(tt in comp_lower for tt in top_tier):
            total_score += 10

        # Core Track Boost
        if cand_domain in ["software", "frontend", "backend"] and any(
            st in title_low for st in ["sde", "software development engineer", "software engineer", "full stack", "backend", "frontend"]
        ):
            total_score += 8

        # Boost verified live platforms with guaranteed active application links
        source_low = (job.source or "").lower()
        if any(v in source_low for v in ["jobfound", "arbeitnow", "remotive"]):
            total_score += 5

        total_score = max(10, min(99, total_score))

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
