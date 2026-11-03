"""
Jobfound.org API adapter.
Scrapes real job postings from Jobfound's open REST API.
"""
from typing import List, Dict, Any
from .base_source import BaseJobSource
from .skill_extractor import SkillExtractor


class JobfoundSource(BaseJobSource):
    def __init__(self, extractor: SkillExtractor = None):
        super().__init__(name="Jobfound", timeout=12, max_retries=3)
        self.extractor = extractor or SkillExtractor()
        self.base_url = "https://jobfound.org/api/jobs"

        # Explicit software and technology filtering
        self.tech_domains = {
            "software engineering", "software engineer", "engineering and development",
            "data & ai", "devops", "quality assurance", "product development",
            "frontend", "backend", "full stack", "cloud", "artificial intelligence"
        }
        self.tech_keywords = [
            "software", "developer", "engineer", "frontend", "backend", "full stack", "fullstack",
            "web", "mobile", "android", "ios", "devops", "cloud", "data", "ai", "ml", "machine learning",
            "python", "react", "node", "java", "c++", "c#", "sde", "qa", "database", "programmer", "tech intern"
        ]
        self.excluded_roles = [
            "customer support", "customer success", "sales", "telesales", "telecaller",
            "accountant", "audit", "nurse", "cook", "driver", "procurement", "carpenter",
            "receptionist", "hr intern", "recruiter", "bpo", "content writer", "marketing executive"
        ]

    def _is_software_job(self, title: str, domain: str, skills: List[str]) -> bool:
        """Ensure job is strictly a Software / Engineering / Tech position."""
        t_low = title.lower()
        d_low = (domain or "").lower()
        s_low = " ".join(s.lower() for s in skills)

        # Exclude pure non-tech roles
        if any(ex in t_low for ex in self.excluded_roles):
            return False

        # Include if domain matches tech
        if any(td in d_low for td in self.tech_domains):
            return True

        # Include if title matches tech keywords
        if any(tk in t_low for tk in self.tech_keywords):
            return True

        # Include if has multiple core tech skills
        tech_skill_matches = sum(1 for s in ["python", "java", "react", "sql", "docker", "aws", "git", "javascript", "c++", "node", "api", "html", "css"] if s in s_low)
        return tech_skill_matches >= 2

    def fetch_jobs(self, target_count: int = 1600) -> List[Dict[str, Any]]:
        jobs: List[Dict[str, Any]] = []
        page = 1
        limit = 50  # Jobfound API page size
        seen_ids = set()

        print(f"[{self.name}] Fetching PURE SOFTWARE & TECH jobs. Target: {target_count}...")

        while len(jobs) < target_count:
            url = f"{self.base_url}?page={page}&limit={limit}"
            print(f"[{self.name}] Fetching page {page} ({len(jobs)}/{target_count} tech jobs collected)...")
            
            data = self.fetch_url(url)
            if not data or not isinstance(data, dict):
                break

            batch = data.get("jobs", [])
            if not batch:
                break

            for item in batch:
                title = (item.get("title") or "").strip()
                domain = (item.get("domain") or "").strip()

                # Extract skills first
                raw_skills = item.get("skills") or []
                extracted_skills = []
                if isinstance(raw_skills, list):
                    for s in raw_skills:
                        if isinstance(s, str) and s.strip():
                            extracted_skills.append(self.extractor.normalize_skill(s.strip()))
                elif isinstance(raw_skills, str) and raw_skills.strip():
                    for s in raw_skills.split(","):
                        if s.strip():
                            extracted_skills.append(self.extractor.normalize_skill(s.strip()))

                if not extracted_skills:
                    extracted_skills = self.extractor.extract_skills_from_text(f"{title} {item.get('description', '')}")

                # STRICT SOFTWARE/TECH FILTER CHECK
                if not self._is_software_job(title, domain, extracted_skills):
                    continue

                raw_id = item.get("$id") or item.get("id") or str(len(jobs) + 1)
                if raw_id in seen_ids:
                    continue
                seen_ids.add(raw_id)

                company = (item.get("companyName") or "Unknown Company").strip()
                desc = (item.get("description") or "").strip()
                workplace = (item.get("workplaceType") or "remote").strip().lower()
                location = (item.get("location") or item.get("country") or "Remote").strip()
                is_remote = workplace == "remote" or "remote" in location.lower() or "remote" in title.lower()

                # Experience years
                exp_raw = item.get("experience")
                if exp_raw is not None and str(exp_raw).isdigit():
                    experience = int(exp_raw)
                else:
                    experience = self.extractor.extract_experience_years(f"{title} {desc}")

                apply_url = item.get("applyUrl") or ""
                if not apply_url and item.get("slug"):
                    apply_url = f"https://jobfound.org/jobs/{item.get('slug')}"

                job_obj = {
                    "id": f"jf_{raw_id}",
                    "title": title,
                    "company": company,
                    "location": location,
                    "workplace_type": workplace if workplace in ["remote", "hybrid", "onsite"] else ("remote" if is_remote else "onsite"),
                    "remote": is_remote,
                    "experience_required": experience,
                    "skills": list(dict.fromkeys(extracted_skills)),
                    "description": desc,
                    "source_url": apply_url,
                    "source": "jobfound.org",
                    "domain": domain or "Software Engineering",
                    "posted_at": item.get("postedAt") or ""
                }

                jobs.append(job_obj)
                if len(jobs) >= target_count:
                    break

            page += 1
            if not data.get("hasMore", True):
                break

        print(f"[{self.name}] Finished. Total pure software jobs fetched: {len(jobs)}")
        return jobs

