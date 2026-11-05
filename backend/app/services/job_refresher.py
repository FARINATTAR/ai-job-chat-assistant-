"""
Periodic Background Job Ingestion Service.
Periodically fetches fresh software engineering jobs from public APIs (Remotive, Arbeitnow)
in the background without blocking conversational chat requests.
"""
import asyncio
from typing import List, Dict, Any
from ..repositories.job_repo import get_job_repository


def fetch_live_job_batch(target_per_source: int = 50) -> List[Dict[str, Any]]:
    """
    Fetch a fresh batch of verified open software roles from public live APIs.
    Runs synchronously (intended for execution inside asyncio.to_thread).
    """
    all_fresh: List[Dict[str, Any]] = []

    # 1. Remotive (Live remote software developer openings)
    try:
        from scraper.skill_extractor import SkillExtractor
        from scraper.remotive_source import RemotiveSource

        extractor = SkillExtractor()
        remotive = RemotiveSource(extractor=extractor)
        rem_jobs = remotive.fetch_jobs(target_count=target_per_source)
        all_fresh.extend(rem_jobs)
    except Exception as e:
        print(f"[JobRefresher] Remotive sync error: {e}")

    # 2. Arbeitnow (Live verified active tech jobs)
    try:
        from scraper.skill_extractor import SkillExtractor
        from scraper.arbeitnow_source import ArbeitnowSource

        extractor = SkillExtractor()
        arbeitnow = ArbeitnowSource(extractor=extractor)
        an_jobs = arbeitnow.fetch_jobs(target_count=target_per_source)
        all_fresh.extend(an_jobs)
    except Exception as e:
        print(f"[JobRefresher] Arbeitnow sync error: {e}")

    # 3. JSearch (Live MNC roles from LinkedIn / Indeed / Glassdoor)
    try:
        from scraper.skill_extractor import SkillExtractor
        from scraper.jsearch_source import JSearchSource
        from ..config import settings

        extractor = SkillExtractor()
        jsearch = JSearchSource(api_key=settings.RAPIDAPI_KEY, extractor=extractor)
        js_jobs = jsearch.fetch_jobs(target_count=target_per_source)
        all_fresh.extend(js_jobs)
    except Exception as e:
        print(f"[JobRefresher] JSearch sync error: {e}")

    return all_fresh


def check_expired_jobs(sample_size: int = 50) -> int:
    """
    Periodic health-check on active jobs to identify expired links (404/410/closed banners).
    Runs synchronously inside a background worker thread.
    """
    import random
    from .job_validator import check_job_url_active
    repo = get_job_repository()
    active_jobs = [j for j in repo.get_all() if getattr(j, "is_active", True) is not False and j.source_url]
    deactivated = 0

    sample = random.sample(active_jobs, min(sample_size, len(active_jobs))) if active_jobs else []
    for job in sample:
        is_active, reason = check_job_url_active(job.source_url)
        if not is_active:
            repo.mark_job_inactive(job.id)
            deactivated += 1

    return deactivated


async def periodic_job_refresher(stop_event: asyncio.Event, interval_seconds: int = 3600):
    """
    Background worker task running continuously during app lifespan.
    Periodically pulls fresh job postings, deduplicates, and upserts them
    into the in-memory repository without interfering with user chat latency.
    """
    print(f"[JobRefresher] Async background worker initialized (sync interval: {interval_seconds // 60} minutes).", flush=True)

    # Initial delay: wait 90 seconds after server startup before running first background sync
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=90)
        return
    except asyncio.TimeoutError:
        pass

    while not stop_event.is_set():
        try:
            print("[JobRefresher] Executing scheduled background sync from live APIs...", flush=True)
            # Run blocking HTTP requests in a worker thread
            fresh_jobs = await asyncio.to_thread(fetch_live_job_batch, 50)

            if fresh_jobs:
                repo = get_job_repository()
                added_count = repo.upsert_jobs(fresh_jobs)
                print(f"[JobRefresher] Sync complete. Ingested {added_count} new unique jobs from live APIs.", flush=True)
            else:
                print("[JobRefresher] No new jobs retrieved during this cycle.", flush=True)

            # Validate health of existing jobs
            deactivated = await asyncio.to_thread(check_expired_jobs, 50)
            if deactivated > 0:
                print(f"[JobRefresher] Deactivated {deactivated} expired job links.", flush=True)

        except Exception as e:
            print(f"[JobRefresher] Background worker error: {e}", flush=True)

        # Sleep for interval_seconds (or abort early if stop_event is set on shutdown)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            break
        except asyncio.TimeoutError:
            pass

    print("[JobRefresher] Background sync worker stopped cleanly.", flush=True)

