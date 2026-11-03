"""
Arbeitnow API adapter.
Scrapes real job postings from Arbeitnow's public job board API.
"""
from typing import List, Dict, Any
from .base_source import BaseJobSource
from .skill_extractor import SkillExtractor


class ArbeitnowSource(BaseJobSource):
    def __init__(self, extractor: SkillExtractor = None):
        super().__init__(name="Arbeitnow", timeout=12, max_retries=3)
        self.extractor = extractor or SkillExtractor()
        self.base_url = "https://www.arbeitnow.com/api/job-board-api"

    def fetch_jobs(self, target_count: int = 500) -> List[Dict[str, Any]]:
        jobs: List[Dict[str, Any]] = []
        page = 1
        seen_ids = set()

        print(f"[{self.name}] Starting fetch. Target: {target_count} jobs...")

        while len(jobs) < target_count:
            url = f"{self.base_url}?page={page}"
            print(f"[{self.name}] Fetching page {page} ({len(jobs)}/{target_count} collected)...")

            data = self.fetch_url(url)
            if not data or not isinstance(data, dict):
                break

            batch = data.get("data", [])
            if not batch:
                break

            for item in batch:
                slug = item.get("slug") or str(len(jobs) + 1)
                if slug in seen_ids:
                    continue
                seen_ids.add(slug)

                title = (item.get("title") or "").strip()
                company = (item.get("company_name") or "Unknown Company").strip()
                desc = (item.get("description") or "").strip()
                location = (item.get("location") or "Remote").strip()
                is_remote = bool(item.get("remote")) or "remote" in location.lower() or "remote" in title.lower()

                # Tags / Skills
                raw_tags = item.get("tags") or []
                skills = [self.extractor.normalize_skill(t) for t in raw_tags if isinstance(t, str)]
                if not skills:
                    skills = self.extractor.extract_skills_from_text(f"{title} {desc}")

                # Experience years
                experience = self.extractor.extract_experience_years(f"{title} {desc}")

                job_obj = {
                    "id": f"an_{slug}",
                    "title": title,
                    "company": company,
                    "location": location,
                    "workplace_type": "remote" if is_remote else "onsite",
                    "remote": is_remote,
                    "experience_required": experience,
                    "skills": list(dict.fromkeys(skills)),
                    "description": desc,
                    "source_url": item.get("url") or f"https://www.arbeitnow.com/view/{slug}",
                    "source": "arbeitnow.com",
                    "posted_at": item.get("created_at") or ""
                }

                jobs.append(job_obj)
                if len(jobs) >= target_count:
                    break

            page += 1
            if not data.get("links", {}).get("next"):
                break

        print(f"[{self.name}] Finished. Total fetched: {len(jobs)}")
        return jobs

