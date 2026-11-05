"""
Real-time Job Health and Expiry Validator.
Detects expired, closed, or filled job postings across LinkedIn, Workday,
and corporate ATS portals using pattern matching and HTTP status codes.
"""
import urllib.request
import urllib.error
from typing import Tuple

CLOSED_PATTERNS = [
    "not currently accepting applications",
    "no longer accepting applications",
    "this job is no longer available",
    "job you are trying to apply for has been filled",
    "page you are looking for doesn't exist",
    "job is no longer open",
    "this position has been filled",
    "position has been filled",
    "this listing has expired",
    "job expired",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def check_job_url_active(url: str, timeout: float = 3.5) -> Tuple[bool, str]:
    """
    Check if a job URL is active and still accepting applications.
    Returns (is_active, reason).
    """
    if not url:
        return True, "no_url"

    url_lower = url.lower()

    # Public verified APIs (Remotive, Arbeitnow) only supply active roles
    if "remotive.com" in url_lower or "arbeitnow.com" in url_lower:
        return True, "verified_api"

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as res:
            if res.status != 200:
                return False, f"http_{res.status}"

            # Read first 120KB of HTML to detect banner warnings without downloading large media
            content = res.read(120000).decode("utf-8", errors="ignore").lower()

            for pattern in CLOSED_PATTERNS:
                if pattern in content:
                    return False, f"pattern_{pattern.replace(' ', '_')}"

            return True, "active"

    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return False, f"http_{e.code}"
        # For 403 / 999 (LinkedIn bot challenge when unauthenticated), do not falsely deactivate
        return True, f"http_{e.code}_allowed"

    except Exception as e:
        # Network timeout or DNS glitch on individual check - keep active to prevent false dropouts
        return True, f"timeout_keep"

