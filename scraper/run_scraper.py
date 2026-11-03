"""
Master Job Scraper Runner.
Crawls real job listings from public sources, deduplicates, and saves to data/jobs.json.

Usage:
    python scraper/run_scraper.py --target 1800
"""
import argparse
import json
import os
import sys
from collections import Counter
from typing import List, Dict, Any

from .jobfound_source import JobfoundSource
from .arbeitnow_source import ArbeitnowSource
from .skill_extractor import SkillExtractor


def deduplicate_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate jobs by ID and (normalized title + company)."""
    seen_ids = set()
    seen_title_company = set()
    unique_jobs: List[Dict[str, Any]] = []

    for job in jobs:
        jid = job.get("id")
        if not jid or jid in seen_ids:
            continue

        title = (job.get("title") or "").strip().lower()
        company = (job.get("company") or "").strip().lower()
        key = f"{title}::{company}"

        if key in seen_title_company:
            continue

        # Basic validity check
        if not title or not company:
            continue

        seen_ids.add(jid)
        seen_title_company.add(key)
        unique_jobs.append(job)

    return unique_jobs


def print_stats(jobs: List[Dict[str, Any]]):
    """Print detailed summary report of scraped jobs."""
    total = len(jobs)
    if total == 0:
        print("No jobs to summarize.")
        return

    companies = set(j["company"] for j in jobs)
    remote_count = sum(1 for j in jobs if j.get("remote"))
    with_skills = sum(1 for j in jobs if j.get("skills"))

    all_skills = [s for j in jobs for s in j.get("skills", [])]
    skill_counts = Counter(all_skills).most_common(10)

    print("\n" + "=" * 50)
    print("🎯 JOB DATASET GENERATION SUMMARY")
    print("=" * 50)
    print(f"Total Unique Jobs:       {total:,}")
    print(f"Unique Companies:        {len(companies):,}")
    print(f"Remote Positions:        {remote_count:,} ({remote_count/total*100:.1f}%)")
    print(f"Jobs with Tagged Skills: {with_skills:,} ({with_skills/total*100:.1f}%)")
    print("\nTop 10 In-Demand Skills:")
    for skill, count in skill_counts:
        print(f"  • {skill:<18}: {count:,} jobs")
    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Scrape real job postings for Hidani assessment.")
    parser.add_argument("--target", type=int, default=1800, help="Target number of jobs (default: 1800)")
    parser.add_argument("--output", type=str, default="data/jobs.json", help="Output path (default: data/jobs.json)")
    args = parser.parse_args()

    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    extractor = SkillExtractor()
    all_jobs: List[Dict[str, Any]] = []

    # 1. Primary: Jobfound
    print(f"--> [Source 1/2] Crawling Jobfound.org...")
    jobfound = JobfoundSource(extractor=extractor)
    jf_jobs = jobfound.fetch_jobs(target_count=args.target)
    all_jobs.extend(jf_jobs)

    # 2. Secondary: If more jobs needed, crawl Arbeitnow
    remaining = args.target - len(all_jobs)
    if remaining > 0:
        print(f"--> [Source 2/2] Fetching additional {remaining} jobs from Arbeitnow...")
        arbeitnow = ArbeitnowSource(extractor=extractor)
        an_jobs = arbeitnow.fetch_jobs(target_count=remaining + 100)
        all_jobs.extend(an_jobs)

    # Deduplicate
    unique_jobs = deduplicate_jobs(all_jobs)

    # Slice to exact target if exceeded
    final_jobs = unique_jobs[:args.target] if len(unique_jobs) > args.target else unique_jobs

    # Save to JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_jobs, f, indent=2, ensure_ascii=False)

    print(f"\n[SUCCESS] Saved {len(final_jobs)} jobs to {output_path}")
    print_stats(final_jobs)


if __name__ == "__main__":
    main()

