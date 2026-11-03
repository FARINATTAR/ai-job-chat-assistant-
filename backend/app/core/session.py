"""
Session state manager for conversational memory and index-to-ID mapping.
Enables stateful queries like 'apply to job 3' and filter refinement across turns.
"""
import uuid
import re
from typing import Dict, List, Optional
from ..models.schemas import ResumeProfile, ActiveFilters


class SessionState:
    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.resume_profile: Optional[ResumeProfile] = None
        # last_results stores the list of job_ids displayed in the last recommendation (Index 1 -> last_results[0])
        self.last_results: List[str] = []
        self.active_filters: ActiveFilters = ActiveFilters()
        self.history: List[Dict[str, str]] = []  # [{"role": "user"|"assistant", "content": "..."}]

    def resolve_job_index_or_id(self, ref: str) -> Optional[str]:
        """
        Translates a conversational job reference like '2', 'job 3', '#1'
        or a direct job ID ('jf_123') into the concrete job ID.
        """
        ref_clean = ref.strip().lower()

        # Check if reference contains a digit (e.g., 'job 3', '3rd', '2')
        digit_match = re.search(r"\b(\d+)\b", ref_clean)
        if digit_match:
            index = int(digit_match.group(1))
            # 1-based index
            if 1 <= index <= len(self.last_results):
                return self.last_results[index - 1]

        # Check direct job ID
        if ref_clean in self.last_results:
            return ref_clean
        
        # Check if it starts with known ID prefix
        if ref_clean.startswith("jf_") or ref_clean.startswith("an_"):
            return ref_clean

        return None


class SessionStore:
    """Thread-safe in-memory session store."""

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}

    def get_or_create(self, session_id: Optional[str] = None) -> SessionState:
        if not session_id:
            session_id = str(uuid.uuid4())
        
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id)
        
        return self._sessions[session_id]

    def get(self, session_id: str) -> Optional[SessionState]:
        return self._sessions.get(session_id)


# Global singleton instance
session_store = SessionStore()


def get_session_store() -> SessionStore:
    return session_store
