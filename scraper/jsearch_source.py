"""
JSearch API adapter.
Aggregates real-time software engineering and intern roles from LinkedIn, Indeed,
and Glassdoor using RapidAPI JSearch, with a particular focus on MNCs (Google,
Microsoft, Amazon, Meta, Nvidia, Apple).
"""
import os
import re
import json
import urllib.parse
import urllib.request
from typing import List, Dict, Any, Optional
from .base_source import BaseJobSource
from .skill_extractor import SkillExtractor


class JSearchSource(BaseJobSource):
    """Fetches live MNC tech roles from LinkedIn, Indeed, and Glassdoor via JSearch API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        extractor: Optional[SkillExtractor] = None,
        timeout: int = 15,
        max_retries: int = 3,
    ):
        super().__init__(name="JSearch", timeout=timeout, max_retries=max_retries)
        self.api_key = api_key or os.getenv("RAPIDAPI_KEY", "")
        self.extractor = extractor or SkillExtractor()
        self.base_url = "https://jsearch.p.rapidapi.com/search"

    def fetch_jobs(
        self,
        target_count: int = 50,
        query: str = "software engineer intern OR fresher developer Google Microsoft Amazon Meta Nvidia",
    ) -> List[Dict[str, Any]]:
        """
        Fetch fresh software engineering and intern jobs.
        If RAPIDAPI_KEY is configured, queries real-time LinkedIn/Indeed/Glassdoor postings.
        """
        if not self.api_key:
            print(
                f"[{self.name}] Notice: RAPIDAPI_KEY is not configured in environment. "
                "Set RAPIDAPI_KEY in .env to query real-time LinkedIn/Indeed listings."
            )
            return []

        jobs: List[Dict[str, Any]] = []
        params = {
            "query": query,
            "page": "1",
            "num_pages": "1",
            "date_posted": "month",
        }
        url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
        print(f"[{self.name}] Querying live MNC software roles via JSearch API...")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "x-rapidapi-host": "jsearch.p.rapidapi.com",
            "x-rapidapi-key": self.api_key,
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    raw_items = data.get("data", [])
                    print(f"[{self.name}] Retrieved {len(raw_items)} job listings.")

                    for item in raw_items:
                        if len(jobs) >= target_count:
                            break

                        jid = f"js_{item.get('job_id')}"
                        title = (item.get("job_title") or "").strip()
                        company = (item.get("employer_name") or "Tech Company").strip()
                        city = item.get("job_city") or ""
                        country = item.get("job_country") or ""
                        location = f"{city}, {country}".strip(", ") or "Global"
                        is_remote = bool(item.get("job_is_remote", False))
                        description = item.get("job_description") or ""
                        source_url = item.get("job_apply_link") or item.get("job_google_link") or ""
                        publisher = item.get("job_publisher") or "LinkedIn"

                        # Clean description
                        clean_desc = re.sub(r"\s+", " ", description).strip()[:1000]

                        # Extract skills using taxonomy
                        skills = self.extractor.extract_skills(f"{title} {clean_desc}")

                        # Estimate experience required
                        req_exp_obj = item.get("job_required_experience") or {}
                        exp_months = req_exp_obj.get("required_experience_in_months") or 0
                        exp_years = exp_months // 12 if exp_months else 0
                        if "intern" in title.lower() or "fresher" in title.lower():
                            exp_years = 0

                        jobs.append({
                            "id": jid,
                            "title": title,
                            "company": company,
                            "location": location,
                            "workplace_type": "remote" if is_remote else "on-site",
                            "remote": is_remote,
                            "experience_required": exp_years,
                            "skills": skills,
                            "description": clean_desc[:500],
                            "source_url": source_url,
                            "source": publisher,
                            "posted_at": item.get("job_posted_at_datetime_utc") or "",
                            "is_active": True,
                        })

        except Exception as e:
            print(f"[{self.name}] API request error: {e}")

        return jobs

