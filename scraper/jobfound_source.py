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

    def fetch_jobs(self, target_count: int = 1500) -> List[Dict[str, Any]]:
        jobs: List[Dict[str, Any]] = []
        page = 1
        limit = 50  # Jobfound API page size
        seen_ids = set()

        print(f"[{self.name}] Starting fetch. Target: {target_count} jobs...")

        while len(jobs) < target_count:
            url = f"{self.base_url}?page={page}&limit={limit}"
            print(f"[{self.name}] Fetching page {page} ({len(jobs)}/{target_count} collected)...")
            
            data = self.fetch_url(url)
            if not data or not isinstance(data, dict):
                print(f"[{self.name}] No valid response on page {page}. Stopping.")
                break

            batch = data.get("jobs", [])
            if not batch:
                print(f"[{self.name}] Empty jobs list on page {page}. Stopping.")
                break

            for item in batch:
                raw_id = item.get("$id") or item.get("id") or str(len(jobs) + 1)
                if raw_id in seen_ids:
                    continue
                seen_ids.add(raw_id)

                title = (item.get("title") or "").strip()
                company = (item.get("companyName") or "Unknown Company").strip()
                desc = (item.get("description") or "").strip()
                workplace = (item.get("workplaceType") or "remote").strip().lower()
                location = (item.get("location") or item.get("country") or "Remote").strip()
                
                # Remote flag
                is_remote = workplace == "remote" or "remote" in location.lower() or "remote" in title.lower()

                # Skills: Jobfound provides skills as list or comma-separated string
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

                # If no skills provided, extract from description & title
                if not extracted_skills:
                    extracted_skills = self.extractor.extract_skills_from_text(f"{title} {desc}")

                # Experience years
                exp_raw = item.get("experience")
                if exp_raw is not None and str(exp_raw).isdigit():
                    experience = int(exp_raw)
                else:
                    experience = self.extractor.extract_experience_years(f"{title} {desc}")

                # Source URL
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
                    "skills": list(dict.fromkeys(extracted_skills)),  # remove duplicates keeping order
                    "description": desc,
                    "source_url": apply_url,
                    "source": "jobfound.org",
                    "posted_at": item.get("postedAt") or ""
                }

                jobs.append(job_obj)
                if len(jobs) >= target_count:
                    break

            page += 1
            if not data.get("hasMore", True):
                print(f"[{self.name}] Reached end of available jobs.")
                break

        print(f"[{self.name}] Finished. Total fetched: {len(jobs)}")
        return jobs

