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

    return all_fresh


async def periodic_job_refresher(stop_event: asyncio.Event, interval_seconds: int = 3600):
    """
    Background worker task running continuously during app lifespan.
    Periodically pulls fresh job postings, deduplicates, and upserts them
    into the in-memory repository without interfering with user chat latency.
    """
    print(f"[JobRefresher] Async background worker initialized (sync interval: {interval_seconds // 60} minutes).")

    # Initial delay: wait 90 seconds after server startup before running first background sync
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=90)
        return
    except asyncio.TimeoutError:
        pass

    while not stop_event.is_set():
        try:
            print("[JobRefresher] Executing scheduled background sync from live APIs...")
            # Run blocking HTTP requests in a worker thread
            fresh_jobs = await asyncio.to_thread(fetch_live_job_batch, 50)

            if fresh_jobs:
                repo = get_job_repository()
                added_count = repo.upsert_jobs(fresh_jobs)
                print(f"[JobRefresher] Sync complete. Ingested {added_count} new unique jobs from live APIs.")
            else:
                print("[JobRefresher] No new jobs retrieved during this cycle.")

        except Exception as e:
            print(f"[JobRefresher] Background worker error: {e}")

        # Sleep for interval_seconds (or abort early if stop_event is set on shutdown)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            break
        except asyncio.TimeoutError:
            pass

    print("[JobRefresher] Background sync worker stopped cleanly.")

