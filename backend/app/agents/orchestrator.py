"""
Master Orchestrator Agent.
Central conversational brain managing state machine, intent routing,
sub-agent handoffs, and real-time SSE streaming.
"""
import re
import json
from typing import AsyncGenerator, Dict, Any, List, Optional
from ..models.schemas import ChatRequest, ResumeProfile, ActiveFilters, JobMatch
from ..core.session import SessionState, SessionStore, get_session_store
from ..core.events import StreamEmitter
from ..repositories.job_repo import JobRepository, get_job_repository
from ..repositories.app_repo import ApplicationRepository
from .matcher_agent import MatcherAgent
from .apply_agent import ApplyAgent


class OrchestratorAgent:
    """Master orchestrator routing between MatcherAgent and ApplyAgent."""

    def __init__(
        self,
        job_repo: Optional[JobRepository] = None,
        session_store: Optional[SessionStore] = None
    ):
        self.job_repo = job_repo or get_job_repository()
        self.session_store = session_store or get_session_store()
        self.matcher = MatcherAgent(job_repo=self.job_repo)

    def detect_intent(self, message: str) -> Dict[str, Any]:
        """Detect intent from user natural query."""
        msg_low = message.strip().lower()

        # 1. Apply intent: "apply to job 3", "apply 1", "apply to the first one"
        apply_match = re.search(r"\bapply\b(?:\s+(?:to|for)?\s*(?:job)?\s*#?([a-zA-Z0-9_-]+|\d+))?", msg_low)
        if apply_match and ("job" in msg_low or re.search(r"\b\d+\b", msg_low) or "apply" in msg_low.split()):
            ref = apply_match.group(1) or ""
            # If no ref captured in group, look for any digit
            if not ref:
                num_match = re.search(r"\b(\d+)\b", msg_low)
                if num_match:
                    ref = num_match.group(1)
            return {"intent": "APPLY", "reference": ref or "1"}

        # 2. Tracking intent: "show my applied jobs", "my applications", "status"
        if any(kw in msg_low for kw in ["applied jobs", "my applications", "show applied", "application status", "what did i apply"]):
            return {"intent": "TRACK"}

        # 3. Filter refinement / Search intent
        # Check for pagination: "show more", "next", "more jobs", "next 10", "page 2", etc.
        is_next_page = any(kw in msg_low for kw in [
            "show more", "next 10", "next page", "more jobs", "next jobs", "load more", "page 2", "page 3", "page 4"
        ]) or msg_low in ["next", "more", "load more jobs"]
        if is_next_page:
            return {"intent": "NEXT_PAGE"}

        # Check for remote
        is_remote_query = any(kw in msg_low for kw in ["remote", "work from home", "wfh"])
        is_reset_query = any(kw in msg_low for kw in ["reset", "clear filter", "all jobs", "start over"])
        has_skill_query = any(s in msg_low for s in ["python", "react", "sql", "java", "docker", "aws", "node", "typescript"])
        has_exp_query = any(w in msg_low for w in ["fresher", "intern", "junior", "senior", "mid-level", "years exp", "yr exp", "yrs exp", "experience", "exp"])
        has_source_query = any(src in msg_low for src in ["arbeitnow", "remotive", "linkedin", "all source", "all sources"])
        is_recommend_query = any(kw in msg_low for kw in ["recommend", "matching", "find jobs", "show jobs", "search"])

        if is_reset_query:
            return {"intent": "RESET_FILTERS"}

        if is_remote_query or has_skill_query or has_exp_query or has_source_query or is_recommend_query:
            return {
                "intent": "SEARCH_OR_REFINE",
                "is_remote": True if is_remote_query else None,
                "text": message
            }

        # 4. Greeting or General query
        if any(kw in msg_low for kw in ["hi", "hello", "hey", "help", "who are you", "what can you do"]):
            return {"intent": "GREETING"}

        # Default to search/refine if resume is uploaded
        return {"intent": "SEARCH_OR_REFINE", "text": message}

    async def stream_chat(
        self,
        session: SessionState,
        user_message: str,
        app_repo: ApplicationRepository
    ) -> AsyncGenerator[str, None]:
        """
        Main conversational loop yielding SSE formatted event strings.
        Emits thoughts, agent handoffs, tokens, and job result cards.
        """
        # Save user message to history
        session.history.append({"role": "user", "content": user_message})

        # Emit initial Orchestrator start
        yield StreamEmitter.agent_start("Orchestrator", "Analyzing user request and active conversational context...")

        intent_data = self.detect_intent(user_message)
        intent = intent_data.get("intent")

        # -------------------------------------------------------------
        # Intent: GREETING / HELP
        # -------------------------------------------------------------
        if intent == "GREETING":
            yield StreamEmitter.agent_thought("Orchestrator", "Handling conversational greeting and guide.")
            greeting_msg = (
                "👋 Hello! I'm your **AI Job Chat Assistant**.\n\n"
                "Here is how I can assist you:\n"
                "1. **Upload your resume** (PDF or DOCX) so I can parse your skills, designation, and experience.\n"
                "2. Ask me to **recommend matching jobs** from our dataset of over 1,600 verified roles.\n"
                "3. **Refine naturally** by saying *'show only remote roles'* or *'jobs needing React'*.\n"
                "4. **Apply seamlessly** by saying *'apply to job 2'*.\n"
                "5. **Track applications** anytime by asking *'show my applied jobs'*.\n\n"
                "How would you like to begin?"
            )
            session.history.append({"role": "assistant", "content": greeting_msg})
            yield StreamEmitter.token(greeting_msg)
            yield StreamEmitter.complete()
            return

        # -------------------------------------------------------------
        # Intent: TRACK APPLICATIONS
        # -------------------------------------------------------------
        if intent == "TRACK":
            yield StreamEmitter.agent_handoff("Orchestrator", "ApplicationManager", "User requested previously applied jobs status.")
            apply_agent = ApplyAgent(app_repo=app_repo, session_store=self.session_store, job_repo=self.job_repo)
            applied_jobs = apply_agent.list_applied_jobs(session.session_id)

            if not applied_jobs:
                msg = "You haven't applied to any jobs yet in this session. Ask me to recommend jobs or say *'show remote jobs'* to get started!"
            else:
                msg = f"📋 You have applied to **{len(applied_jobs)}** role{'' if len(applied_jobs) == 1 else 's'}:\n\n"
                for idx, app in enumerate(applied_jobs, start=1):
                    applied_date = app.applied_at[:10] if app.applied_at else "Recently"
                    msg += f"{idx}. **{app.job_title}** at **{app.company}**\n   - Status: `{app.status}` | Applied: {applied_date}\n"

            session.history.append({"role": "assistant", "content": msg})
            yield StreamEmitter.token(msg)
            yield StreamEmitter.complete()
            return

        # -------------------------------------------------------------
        # Intent: APPLY TO JOB
        # -------------------------------------------------------------
        if intent == "APPLY":
            job_ref = intent_data.get("reference", "1")
            yield StreamEmitter.agent_handoff("Orchestrator", "ApplicationManager", f"Delegating application submission for reference '{job_ref}'.")

            apply_agent = ApplyAgent(app_repo=app_repo, session_store=self.session_store, job_repo=self.job_repo)
            result = apply_agent.apply_to_job(session=session, job_reference=job_ref)

            response_msg = result.message
            session.history.append({"role": "assistant", "content": response_msg})
            yield StreamEmitter.token(response_msg)
            yield StreamEmitter.complete()
            return

        # -------------------------------------------------------------
        # Intent: NEXT_PAGE (Pagination)
        # -------------------------------------------------------------
        if intent == "NEXT_PAGE":
            session.active_filters.page += 1
            session.active_filters.offset = (session.active_filters.page - 1) * 10
            yield StreamEmitter.agent_thought(
                "Orchestrator",
                f"Loading page {session.active_filters.page} (jobs #{session.active_filters.offset + 1} to #{session.active_filters.offset + 10})..."
            )

        # -------------------------------------------------------------
        # Intent: RESET FILTERS
        # -------------------------------------------------------------
        elif intent == "RESET_FILTERS":
            session.active_filters = ActiveFilters()
            yield StreamEmitter.agent_thought("Orchestrator", "Reset all conversational filters to default.")
            msg = "All filters have been reset. Re-ranking top jobs based solely on your resume profile..."
            yield StreamEmitter.token(msg + "\n\n")

        # -------------------------------------------------------------
        # Intent: SEARCH_OR_REFINE (New search resets to Page 1)
        # -------------------------------------------------------------
        else:
            session.active_filters.page = 1
            session.active_filters.offset = 0
        # If candidate has not uploaded a resume, create a default software engineer profile
        if not session.resume_profile:
            session.resume_profile = ResumeProfile(
                name="Candidate",
                designation="Software Engineer",
                skills=["Python", "JavaScript", "React", "SQL", "Git"],
                years_of_experience=1.0,
                experience_summary="Default software engineering profile"
            )
            yield StreamEmitter.agent_thought("Orchestrator", "Using default Software Engineer profile until resume is uploaded.")

        # Stack conversational filters
        msg_low = user_message.lower()
        if "remote" in msg_low or "wfh" in msg_low:
            session.active_filters.remote = True
        elif "onsite" in msg_low or "in-office" in msg_low:
            session.active_filters.remote = False

        # Detect specific skill mentions
        for s in ["React", "Python", "TypeScript", "JavaScript", "SQL", "Docker", "AWS", "FastAPI", "Node.js", "Java", "C++", "C#"]:
            if s.lower() in msg_low and s not in session.active_filters.skills:
                session.active_filters.skills.append(s)

        # Detect conversational experience filters:
        # e.g., "fresher jobs", "internship", "0 years", "1-2 years", "max 3 years", "senior"
        if any(w in msg_low for w in ["fresher", "intern", "0 exp", "0 year", "0 yr", "0-1 year", "0-1 yr", "entry level", "entry-level"]):
            session.active_filters.max_experience = 1
        elif any(w in msg_low for w in ["1-2 year", "1-2 yr", "2 year", "2 yr", "junior"]):
            session.active_filters.max_experience = 2
        elif any(w in msg_low for w in ["3 year", "3 yr", "3-5 year", "mid level", "mid-level"]):
            session.active_filters.max_experience = 4
        elif any(w in msg_low for w in ["senior", "lead", "5+ year", "5 year", "5 yr"]):
            session.active_filters.max_experience = 10
        elif "all exp" in msg_low or "all experience" in msg_low or "any experience" in msg_low:
            session.active_filters.max_experience = None

        exp_regex = re.search(r"(?:max|under|below|for)\s+(\d+)\s*(?:years?|yrs?)(?:\s*(?:of\s*)?exp)?", msg_low)
        if exp_regex:
            try:
                session.active_filters.max_experience = int(exp_regex.group(1))
            except ValueError:
                pass

        # Detect specific source requests
        if "arbeitnow" in msg_low:
            session.active_filters.source = "Arbeitnow"
        elif "remotive" in msg_low:
            session.active_filters.source = "Remotive"
        elif "linkedin" in msg_low:
            session.active_filters.source = "LinkedIn"
        elif "all source" in msg_low or "all sources" in msg_low:
            session.active_filters.source = None

        filter_desc = []
        if session.active_filters.source:
            filter_desc.append(f"Source={session.active_filters.source}")
        if session.active_filters.remote is not None:
            filter_desc.append(f"Remote={session.active_filters.remote}")
        if session.active_filters.max_experience is not None:
            filter_desc.append(f"MaxExp={session.active_filters.max_experience}yr{'s' if session.active_filters.max_experience > 1 else ''}")
        if session.active_filters.skills:
            filter_desc.append(f"Skills={', '.join(session.active_filters.skills)}")
        if session.active_filters.page > 1:
            filter_desc.append(f"Page={session.active_filters.page}")

        active_desc_str = ", ".join(filter_desc) if filter_desc else "Default Profile"

        yield StreamEmitter.agent_handoff(
            "Orchestrator",
            "JobMatcher",
            f"Querying {self.job_repo.total_count} verified software jobs. Active filters: {active_desc_str}"
        )

        # Execute Matcher with limit 10
        matches, has_matches = self.matcher.match_jobs(
            profile=session.resume_profile,
            filters=session.active_filters,
            limit=10
        )

        # Handle JD edge case: No matching jobs found
        if not has_matches or not matches:
            yield StreamEmitter.agent_thought("JobMatcher", "Zero matching jobs found with current strict filters.")
            filter_summary = []
            if session.active_filters.source:
                filter_summary.append(f"Source: {session.active_filters.source}")
            if session.active_filters.remote:
                filter_summary.append("Remote only")
            if session.active_filters.skills:
                filter_summary.append(f"Skills: {', '.join(session.active_filters.skills)}")

            criteria_str = " (" + ", ".join(filter_summary) + ")" if filter_summary else ""
            zero_match_msg = (
                f"I couldn't find any additional job listings currently matching your criteria{criteria_str}.\n\n"
                "💡 **Suggestions:**\n"
                "- Say *'reset filters'* to view all recommendations from the beginning.\n"
                "- Try searching another source (e.g., *'show Arbeitnow jobs'* or *'show LinkedIn jobs'*)."
            )
            session.history.append({"role": "assistant", "content": zero_match_msg})
            yield StreamEmitter.token(zero_match_msg)
            yield StreamEmitter.complete()
            return

        # Update last_results and index_to_job_id for index-to-ID mapping ("apply to job 1, 2, 3...")
        session.last_results = [m.job.id for m in matches]
        for m in matches:
            session.index_to_job_id[m.index] = m.job.id

        # Emit job results payload for frontend UI cards
        cards_payload = [m.model_dump() for m in matches]
        yield StreamEmitter.job_results(cards_payload)

        # Text stream response explaining the recommendations
        page_num = session.active_filters.page
        text_resp = f"Here are **matching positions #{matches[0].index} to #{matches[-1].index}** (Page {page_num}):\n\n"
        for m in matches:
            source_tag = f"[{m.job.source}] " if getattr(m.job, 'source', None) else ""
            text_resp += (
                f"**Job {m.index}: {source_tag}{m.job.title}** at **{m.job.company}**\n"
                f"- Match Score: `{m.match_score}%` | Location: {m.job.location} ({'Remote' if m.job.remote else 'Onsite'})\n"
                f"- Key Match: {m.match_reasons[0] if m.match_reasons else 'Aligned with your skills'}\n\n"
            )
        text_resp += f"💡 **Want to see more jobs?** Type *'next'* or click **Load More Jobs** below to view the next 10 roles!\n"
        text_resp += f"👉 To apply, say *'apply to job {matches[0].index}'* or click the **Apply** button on any card."

        session.history.append({"role": "assistant", "content": text_resp})
        yield StreamEmitter.token(text_resp)
        yield StreamEmitter.complete()

