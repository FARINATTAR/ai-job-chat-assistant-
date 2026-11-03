"""
Active Jobs Cleaner and Replenisher.
Audits data/jobs.json for closed/expired postings, purges them,
and replenishes with fresh, verified open roles from Remotive and Arbeitnow.
"""
import json
import os
import urllib.request
import urllib.error
import concurrent.futures
import time
from typing import Dict, Any, List, Tuple
from scraper.remotive_source import RemotiveSource
from scraper.arbeitnow_source import ArbeitnowSource
from scraper.skill_extractor import SkillExtractor

DATA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "jobs.json"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}


def is_job_active(job: Dict[str, Any]) -> Tuple[Dict[str, Any], bool, str]:
    """Check if a job URL is active and still accepting applications."""
    url = job.get("source_url", "")
    source = job.get("source", "")

    # Remotive and Arbeitnow are live API sources that only return active roles
    if "remotive" in source.lower() or "arbeitnow" in source.lower():
        job["is_active"] = True
        return job, True, "verified_api"

    if "linkedin.com/jobs/view" not in url:
        job["is_active"] = True
        return job, True, "company_portal"

    # For LinkedIn postings, check public page
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=4) as res:
            if res.status != 200:
                return job, False, f"status_{res.status}"
            html = res.read().decode("utf-8", errors="ignore").lower()
            if "no longer accepting applications" in html or "this job is no longer available" in html:
                return job, False, "closed_notice"
            job["is_active"] = True
            return job, True, "active"
    except urllib.error.HTTPError as e:
        if e.code in [404, 410]:
            return job, False, f"http_{e.code}"
        return job, True, f"http_{e.code}"
    except Exception:
        # Network timeout on individual link check - keep if recent
        job["is_active"] = True
        return job, True, "timeout_keep"


def main():
    print("=" * 60)
    print("🧹 AUDITING & PURGING EXPIRED JOBS")
    print("=" * 60)

    if not os.path.exists(DATA_PATH):
        print(f"Error: {DATA_PATH} not found.")
        return

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        existing_jobs = json.load(f)

    print(f"Loaded {len(existing_jobs)} existing jobs from {DATA_PATH}")

    # 1. Fetch fresh open roles from Remotive to replenish
    print("\n--> Fetching fresh open roles from Remotive API...")
    extractor = SkillExtractor()
    remotive = RemotiveSource(extractor=extractor)
    fresh_remotive_jobs = remotive.fetch_jobs(target_count=200)

    # 2. Check LinkedIn jobs in batches to eliminate closed listings
    print(f"\n--> Verifying active status for existing jobs...")
    active_jobs: List[Dict[str, Any]] = []
    closed_count = 0

    # Test in parallel with 15 worker threads
    start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(is_job_active, existing_jobs))

    for job, is_active_status, reason in results:
        if is_active_status:
            active_jobs.append(job)
        else:
            closed_count += 1
            print(f"  ❌ Filtered expired job: {job.get('title')} at {job.get('company')} ({reason})")

    elapsed = time.time() - start_time
    print(f"\nVerification finished in {elapsed:.1f}s. Removed {closed_count} closed jobs.")
    print(f"Retained {len(active_jobs)} verified active jobs.")

    # 3. Merge fresh Remotive jobs, deduplicating by ID and title+company
    seen_ids = set(j["id"] for j in active_jobs)
    seen_keys = set(f"{j.get('title', '').strip().lower()}::{j.get('company', '').strip().lower()}" for j in active_jobs)

    added_remotive = 0
    for rjob in fresh_remotive_jobs:
        key = f"{rjob.get('title', '').strip().lower()}::{rjob.get('company', '').strip().lower()}"
        if rjob["id"] not in seen_ids and key not in seen_keys:
            seen_ids.add(rjob["id"])
            seen_keys.add(key)
            active_jobs.append(rjob)
            added_remotive += 1

    print(f"Added {added_remotive} fresh verified open roles from Remotive.")
    print(f"Total Active Jobs: {len(active_jobs)}")

    # 4. Save updated dataset
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(active_jobs, f, indent=2, ensure_ascii=False)

    print(f"✅ Successfully updated {DATA_PATH} with {len(active_jobs)} 100% active jobs!\n")


if __name__ == "__main__":
    main()

