"""
Base source class for all job scrapers with automatic retry and error handling.
"""
from abc import ABC, abstractmethod
import json
import time
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional


class BaseJobSource(ABC):
    """Abstract base class representing a job board source."""

    def __init__(self, name: str, timeout: int = 15, max_retries: int = 3, retry_delay: float = 2.0):
        self.name = name
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }

    def fetch_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch URL with exponential backoff retry logic."""
        for attempt in range(1, self.max_retries + 1):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    if response.status == 200:
                        content = response.read().decode("utf-8")
                        return json.loads(content)
                    else:
                        print(f"[{self.name}] HTTP {response.status} on attempt {attempt}")
            except urllib.error.HTTPError as e:
                print(f"[{self.name}] HTTP Error {e.code} on {url}: {e.reason} (Attempt {attempt}/{self.max_retries})")
                if e.code == 429:
                    time.sleep(self.retry_delay * 2 * attempt)
            except Exception as e:
                print(f"[{self.name}] Network error on attempt {attempt}/{self.max_retries}: {e}")
                time.sleep(self.retry_delay * attempt)
        return None

    @abstractmethod
    def fetch_jobs(self, target_count: int = 1000) -> List[Dict[str, Any]]:
        """
        Fetch and normalize jobs from this source.
        Returns a list of dictionaries matching standard Job schema:
        - id: str
        - title: str
        - company: str
        - location: str
        - workplace_type: str ('remote', 'hybrid', 'onsite')
        - remote: bool
        - experience_required: int (years, 0 for fresher/intern)
        - skills: List[str]
        - description: str
        - source_url: str
        - source: str
        """
        pass

