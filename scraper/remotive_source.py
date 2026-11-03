"""
Remotive API adapter.
Scrapes 100% active, verified open remote software engineering jobs.
Free, public JSON API without API key requirement.
"""
from typing import List, Dict, Any
import html
import re
from .base_source import BaseJobSource
from .skill_extractor import SkillExtractor


class RemotiveSource(BaseJobSource):
    """Fetches verified open remote developer positions from Remotive API."""

    def __init__(self, extractor: SkillExtractor = None):
        super().__init__(name="Remotive", timeout=15, max_retries=3)
        self.extractor = extractor or SkillExtractor()
        self.api_url = "https://remotive.com/api/remote-jobs?category=software-dev"

    def _infer_domain(self, title: str, skills: List[str]) -> str:
        combined = f"{title} {' '.join(skills)}".lower()
        if any(k in combined for k in ["data", "ai", "machine learning", "ml", "nlp", "scientist"]):
            return "Data & AI"
        if any(k in combined for k in ["devops", "cloud", "aws", "docker", "kubernetes", "ci/cd"]):
            return "DevOps"
        if any(k in combined for k in ["frontend", "react", "vue", "angular", "css", "html"]):
            return "Frontend"
        if any(k in combined for k in ["backend", "python", "golang", "django", "node", "java"]):
            return "Backend"
        return "Full Stack"

    def fetch_jobs(self, target_count: int = 500) -> List[Dict[str, Any]]:
        jobs: List[Dict[str, Any]] = []
        print(f"[{self.name}] Fetching verified open remote developer roles from Remotive API...")

        data = self.fetch_url(self.api_url)
        if not data or not isinstance(data, dict):
            print(f"[{self.name}] Failed to fetch from Remotive API.")
            return []

        raw_jobs = data.get("jobs", [])
        print(f"[{self.name}] Received {len(raw_jobs)} active open positions from Remotive.")

        for item in raw_jobs:
            if len(jobs) >= target_count:
                break

            job_id = f"rem_{item.get('id')}"
            title = (item.get("title") or "").strip()
            company = (item.get("company_name") or "Tech Company").strip()
            raw_desc = item.get("description") or ""

            # Clean HTML from description
            cleaned_desc = re.sub(r"<[^>]+>", " ", raw_desc)
            cleaned_desc = html.unescape(cleaned_desc)
            cleaned_desc = re.sub(r"\s+", " ", cleaned_desc).strip()

            location = (item.get("candidate_required_location") or "Remote / Worldwide").strip()
            source_url = item.get("url") or f"https://remotive.com/jobs/{item.get('id')}"

            # Extract tags and skills
            raw_tags = item.get("tags") or []
            skills = [self.extractor.normalize_skill(t) for t in raw_tags if isinstance(t, str)]
            if len(skills) < 2:
                extracted = self.extractor.extract_skills_from_text(f"{title} {cleaned_desc[:400]}")
                for s in extracted:
                    if s not in skills:
                        skills.append(s)

            # Detect experience required
            exp = 0
            title_desc_low = f"{title} {cleaned_desc[:300]}".lower()
            if any(k in title_desc_low for k in ["senior", "sr.", "lead", "staff", "principal"]):
                exp = 4
            elif any(k in title_desc_low for k in ["mid-level", "mid level", "intermediate", "2+ years", "3+ years"]):
                exp = 2
            elif any(k in title_desc_low for k in ["intern", "junior", "entry level", "graduate", "fresher"]):
                exp = 0

            domain = self._infer_domain(title, skills)

            jobs.append({
                "id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "workplace_type": "remote",
                "remote": True,
                "experience_required": exp,
                "skills": skills[:8],
                "description": cleaned_desc[:400] + ("..." if len(cleaned_desc) > 400 else ""),
                "source_url": source_url,
                "source": "Remotive",
                "domain": domain,
                "posted_at": item.get("publication_date") or "",
                "is_active": True
            })

        print(f"[{self.name}] Successfully normalized {len(jobs)} active open positions.")
        return jobs
