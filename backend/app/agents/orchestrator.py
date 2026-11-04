"""
Master Orchestrator Agent.
Uses LLM function calling (Gemini / OpenAI) for intent classification with
conversation history, and deterministic regex as a zero-latency fallback.
Routes to sub-agents and streams real-time SSE events.
"""
import re
import json
from typing import AsyncGenerator, Dict, Any, List, Optional
from ..models.schemas import ChatRequest, ResumeProfile, ActiveFilters, JobMatch
from ..core.session import SessionState, SessionStore, get_session_store
from ..core.events import StreamEmitter
from ..repositories.job_repo import JobRepository, get_job_repository
from ..repositories.app_repo import ApplicationRepository
from ..llm.client import LLMClient, get_llm_client
from ..llm.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from .matcher_agent import MatcherAgent
from .apply_agent import ApplyAgent


class OrchestratorAgent:
    """Master orchestrator using LLM tool calling for intent routing."""

    def __init__(
        self,
        job_repo: Optional[JobRepository] = None,
        session_store: Optional[SessionStore] = None
    ):
        self.job_repo = job_repo or get_job_repository()
        self.session_store = session_store or get_session_store()
        self.matcher = MatcherAgent(job_repo=self.job_repo)
        self.llm = get_llm_client()

    # ------------------------------------------------------------------
    # Regex fallback: fast-path for unambiguous patterns or when LLM is
    # unavailable (no API key configured, network failure, etc.)
    # ------------------------------------------------------------------
    def _regex_classify(self, message: str) -> Dict[str, Any]:
        """Deterministic regex fallback for intent classification."""
        msg_low = message.strip().lower()

        # Apply intent: "apply to job 3", "apply 1"
        apply_match = re.search(
            r"\bapply\b(?:\s+(?:to|for)?\s*(?:job)?\s*#?([a-zA-Z0-9_-]+|\d+))?",
            msg_low,
        )
        if apply_match and (
            "job" in msg_low
            or re.search(r"\b\d+\b", msg_low)
            or "apply" in msg_low.split()
        ):
            ref = apply_match.group(1) or ""
            if not ref:
                num_match = re.search(r"\b(\d+)\b", msg_low)
                if num_match:
                    ref = num_match.group(1)
            return {"tool": "apply_to_job", "args": {"job_number": ref or "1"}}

        # Tracking intent
        if any(
            kw in msg_low
            for kw in [
                "applied jobs", "my applications", "show applied",
                "application status", "what did i apply",
            ]
        ):
            return {"tool": "list_applications", "args": {}}

        # Pagination
        if any(
            kw in msg_low
            for kw in [
                "show more", "next 10", "next page", "more jobs",
                "next jobs", "load more",
            ]
        ) or msg_low in ["next", "more", "load more jobs"]:
            return {"tool": "next_page", "args": {}}

        # Reset filters
        if any(
            kw in msg_low
            for kw in ["reset", "clear filter", "all jobs", "start over"]
        ):
            return {"tool": "reset_filters", "args": {}}

        # Greeting (word-boundary match to avoid false positives on
        # words like "history" or "higher")
        if re.search(r"\b(hi|hello|hey|help)\b", msg_low) and len(msg_low.split()) <= 5:
            if not any(
                kw in msg_low
                for kw in [
                    "remote", "job", "recommend", "apply", "filter",
                    "python", "react", "show",
                ]
            ):
                return {"tool": "greet_user", "args": {}}

        # Search / refine — extract filter parameters from the message
        args: Dict[str, Any] = {}

        if any(kw in msg_low for kw in ["all modes", "all roles", "clear remote", "any workplace", "onsite and remote", "both remote and onsite"]):
            args["remote"] = None
        elif any(kw in msg_low for kw in ["remote", "work from home", "wfh"]):
            args["remote"] = True
        elif any(kw in msg_low for kw in ["onsite", "in-office", "on-site", "in office"]):
            args["remote"] = False

        # Skills detection
        all_skills = {
            "python": "Python", "react": "React", "typescript": "TypeScript",
            "javascript": "JavaScript", "sql": "SQL", "docker": "Docker",
            "aws": "AWS", "fastapi": "FastAPI", "node.js": "Node.js",
            "node": "Node.js", "java": "Java", "c++": "C++", "c#": "C#",
            "golang": "Go", "go": "Go", "rust": "Rust", "ruby": "Ruby",
            "kotlin": "Kotlin", "swift": "Swift", "flutter": "Flutter",
            "vue": "Vue", "angular": "Angular", "django": "Django",
            "spring": "Spring", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
            "terraform": "Terraform", "mongodb": "MongoDB", "postgres": "PostgreSQL",
            "redis": "Redis", "graphql": "GraphQL", "next.js": "Next.js",
            "nextjs": "Next.js", "pytorch": "PyTorch", "tensorflow": "TensorFlow",
        }
        detected_skills = []
        for keyword, canonical in all_skills.items():
            if re.search(r"\b" + re.escape(keyword) + r"\b", msg_low):
                if canonical not in detected_skills:
                    detected_skills.append(canonical)
        if detected_skills:
            args["skills"] = detected_skills

        # Experience detection
        if any(
            w in msg_low
            for w in [
                "fresher", "intern", "0 exp", "0 year", "0 yr",
                "0-1 year", "entry level", "entry-level",
            ]
        ):
            args["max_experience"] = 1
        elif any(w in msg_low for w in ["junior", "1-2 year", "2 year"]):
            args["max_experience"] = 2
        elif any(w in msg_low for w in ["mid level", "mid-level", "3 year", "3-5 year"]):
            args["max_experience"] = 4
        elif any(w in msg_low for w in ["senior", "lead", "5+ year", "5 year"]):
            args["max_experience"] = 10

        exp_regex = re.search(
            r"(?:max|under|below|for)\s+(\d+)\s*(?:years?|yrs?)(?:\s*(?:of\s*)?exp)?",
            msg_low,
        )
        if exp_regex:
            try:
                args["max_experience"] = int(exp_regex.group(1))
            except ValueError:
                pass

        # Source detection
        for src_kw, src_name in [
            ("arbeitnow", "Arbeitnow"), ("remotive", "Remotive"),
            ("linkedin", "LinkedIn"), ("jobfound", "Jobfound"),
        ]:
            if src_kw in msg_low:
                args["source"] = src_name
                break

        # Company detection — scan the message for any company name
        if re.search(r"\b(at|from|by|company)\b", msg_low):
            # Extract potential company name after these keywords
            company_match = re.search(
                r"\b(?:at|from|by|company)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)",
                message,
            )
            if company_match:
                args["company"] = company_match.group(1)

        # Role keyword detection
        role_map = {
            "sde": "sde", "software engineer": "software engineer",
            "full stack": "full stack", "fullstack": "full stack",
            "backend": "backend", "frontend": "frontend",
            "devops": "devops", "cloud": "cloud",
            "data engineer": "data engineer", "data scientist": "data scientist",
            "machine learning": "machine learning", "ml": "machine learning",
            "ai": "ai",
        }
        for keyword, query_val in role_map.items():
            if keyword in msg_low:
                args["query"] = query_val
                break

        return {"tool": "recommend_jobs", "args": args}

    # ------------------------------------------------------------------
    # Primary intent classification: LLM function calling with fallback
    # ------------------------------------------------------------------
    def detect_intent(self, message: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """Classify user intent using LLM function calling, falling back to regex.

        Returns ``{"tool": "<tool_name>", "args": {<parameters>}}`` matching
        the tool schemas defined in ``llm.client.ORCHESTRATOR_TOOLS``.
        """
        # Attempt LLM function calling when a provider is configured
        if self.llm.provider != "fallback":
            result = self.llm.classify_intent(
                user_message=message,
                conversation_history=history or [],
                system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            )
            if result:
                return result

        # Deterministic regex fallback
        return self._regex_classify(message)

    # ------------------------------------------------------------------
    # Streaming chat loop
    # ------------------------------------------------------------------
    async def stream_chat(
        self,
        session: SessionState,
        user_message: str,
        app_repo: ApplicationRepository,
        filter_overrides: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Main conversational loop yielding SSE formatted event strings.
        Uses LLM function calling for intent detection, with conversation
        history for multi-turn context understanding.
        """
        session.history.append({"role": "user", "content": user_message})

        yield StreamEmitter.agent_start(
            "Orchestrator",
            "Analyzing request with conversation context...",
        )

        # Classify intent via LLM (with regex fallback)
        intent_data = self.detect_intent(user_message, history=session.history)
        tool_name = intent_data.get("tool", "recommend_jobs")
        tool_args = intent_data.get("args", {})

        if filter_overrides:
            tool_args.update(filter_overrides)

        yield StreamEmitter.agent_thought(
            "Orchestrator",
            f"Intent resolved → {tool_name}({json.dumps(tool_args, default=str)})",
        )

        # ----- Tool: greet_user -----
        if tool_name == "greet_user":
            yield StreamEmitter.agent_thought("Orchestrator", "Responding to greeting.")
            greeting_msg = (
                "Hello! I am your **AI Job Chat Assistant**.\n\n"
                "Here is how I can assist you:\n"
                "1. **Upload your resume** (PDF or DOCX) so I can parse your skills, designation, and experience.\n"
                "2. Ask me to **recommend matching jobs** from our dataset of over 2,500 verified roles.\n"
                "3. **Refine naturally** by saying *'show only remote roles'* or *'jobs needing React'*.\n"
                "4. **Apply seamlessly** by saying *'apply to job 2'*.\n"
                "5. **Track applications** anytime by asking *'show my applied jobs'*.\n\n"
                "How would you like to begin?"
            )
            session.history.append({"role": "assistant", "content": greeting_msg})
            yield StreamEmitter.token(greeting_msg)
            yield StreamEmitter.complete()
            return

        # ----- Tool: list_applications -----
        if tool_name == "list_applications":
            yield StreamEmitter.agent_handoff(
                "Orchestrator", "ApplicationManager",
                "Retrieving applied jobs and status.",
            )
            apply_agent = ApplyAgent(
                app_repo=app_repo,
                session_store=self.session_store,
                job_repo=self.job_repo,
            )
            applied_jobs = apply_agent.list_applied_jobs(session.session_id)

            if not applied_jobs:
                msg = (
                    "You haven't applied to any jobs yet in this session. "
                    "Ask me to recommend jobs or say *'show remote jobs'* to get started!"
                )
            else:
                msg = f"You have applied to **{len(applied_jobs)}** role{'s' if len(applied_jobs) != 1 else ''}:\n\n"
                for idx, app in enumerate(applied_jobs, start=1):
                    applied_date = app.applied_at[:10] if app.applied_at else "Recently"
                    msg += (
                        f"{idx}. **{app.job_title}** at **{app.company}**\n"
                        f"   - Status: `{app.status}` | Applied: {applied_date}\n"
                    )

            session.history.append({"role": "assistant", "content": msg})
            yield StreamEmitter.token(msg)
            yield StreamEmitter.complete()
            return

        # ----- Tool: apply_to_job -----
        if tool_name == "apply_to_job":
            job_ref = str(tool_args.get("job_number", "1"))
            yield StreamEmitter.agent_handoff(
                "Orchestrator", "ApplicationManager",
                f"Submitting application for reference '{job_ref}'.",
            )
            apply_agent = ApplyAgent(
                app_repo=app_repo,
                session_store=self.session_store,
                job_repo=self.job_repo,
            )
            result = apply_agent.apply_to_job(session=session, job_reference=job_ref)

            session.history.append({"role": "assistant", "content": result.message})
            yield StreamEmitter.token(result.message)
            yield StreamEmitter.complete()
            return

        # ----- Tool: next_page -----
        if tool_name == "next_page":
            session.active_filters.page += 1
            session.active_filters.offset = (session.active_filters.page - 1) * 10
            yield StreamEmitter.agent_thought(
                "Orchestrator",
                f"Loading page {session.active_filters.page} "
                f"(jobs #{session.active_filters.offset + 1}–"
                f"#{session.active_filters.offset + 10})...",
            )

        # ----- Tool: reset_filters -----
        elif tool_name == "reset_filters":
            session.active_filters = ActiveFilters()
            yield StreamEmitter.agent_thought(
                "Orchestrator", "Reset all conversational filters to default."
            )
            yield StreamEmitter.token(
                "All filters have been reset. Re-ranking top jobs based solely on your resume profile...\n\n"
            )

        # ----- Tool: recommend_jobs (new search resets to page 1) -----
        else:
            session.active_filters.page = 1
            session.active_filters.offset = 0

        # Apply filter parameters from LLM tool args (or regex extraction)
        if tool_name == "recommend_jobs" or tool_name in ("next_page", "reset_filters"):
            self._apply_tool_filters(session, tool_args)

        # Ensure a resume profile exists for matching
        if not session.resume_profile:
            session.resume_profile = ResumeProfile(
                name="Candidate",
                designation="Software Engineer",
                skills=["Python", "JavaScript", "React", "SQL", "Git"],
                years_of_experience=1.0,
                experience_summary="Default profile — upload your resume for personalized results.",
            )
            yield StreamEmitter.agent_thought(
                "Orchestrator",
                "No resume uploaded yet. Using a default profile for initial recommendations.",
            )

        # Build human-readable filter summary
        filter_desc = self._describe_filters(session.active_filters)
        active_desc_str = ", ".join(filter_desc) if filter_desc else "Default Profile"

        yield StreamEmitter.agent_handoff(
            "Orchestrator", "JobMatcher",
            f"Querying {self.job_repo.total_count} verified jobs. "
            f"Active filters: {active_desc_str}",
        )

        # Execute matcher
        matches, has_matches = self.matcher.match_jobs(
            profile=session.resume_profile,
            filters=session.active_filters,
            limit=10,
        )

        # Handle zero-match edge case
        if not has_matches or not matches:
            yield StreamEmitter.agent_thought(
                "JobMatcher", "Zero matching jobs found with current filters."
            )
            filter_summary = []
            if session.active_filters.source:
                filter_summary.append(f"Source: {session.active_filters.source}")
            if session.active_filters.remote:
                filter_summary.append("Remote only")
            if session.active_filters.skills:
                filter_summary.append(f"Skills: {', '.join(session.active_filters.skills)}")

            criteria_str = (
                " (" + ", ".join(filter_summary) + ")" if filter_summary else ""
            )
            zero_match_msg = (
                f"No additional jobs found matching your criteria{criteria_str}.\n\n"
                "Suggestions:\n"
                "- Type 'reset' to view all recommendations from the beginning.\n"
                "- Try searching another source (e.g. 'show Arbeitnow jobs' or 'show LinkedIn jobs')."
            )
            session.history.append({"role": "assistant", "content": zero_match_msg})
            yield StreamEmitter.token(zero_match_msg)
            yield StreamEmitter.complete()
            return

        # Update session index mapping for "apply to job N"
        session.last_results = [m.job.id for m in matches]
        for m in matches:
            session.index_to_job_id[m.index] = m.job.id

        # Emit job cards to frontend
        cards_payload = [m.model_dump() for m in matches]
        yield StreamEmitter.job_results(cards_payload)

        # Concise text response
        page_num = session.active_filters.page
        count = len(matches)
        source_str = f" from {session.active_filters.source}" if session.active_filters.source else ""
        company_str = f" at {session.active_filters.company}" if session.active_filters.company else ""

        text_resp = (
            f"Showing next {count} positions (Page {page_num}):"
            if page_num > 1
            else f"Found {count} matching roles{company_str}{source_str} for your profile:"
        )

        session.history.append({"role": "assistant", "content": text_resp})
        yield StreamEmitter.token(text_resp)
        yield StreamEmitter.complete()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _apply_tool_filters(session: SessionState, args: Dict[str, Any]) -> None:
        """Merge LLM-extracted filter arguments into the session's active filters.

        Filters are *stacked* across turns — a new parameter overrides the
        previous value for that specific field without resetting others.
        """
        if "remote" in args:
            session.active_filters.remote = args["remote"]
        if "skills" in args:
            for s in args["skills"]:
                if s not in session.active_filters.skills:
                    session.active_filters.skills.append(s)
        if "max_experience" in args:
            session.active_filters.max_experience = args["max_experience"]
        if "source" in args:
            session.active_filters.source = args["source"]
        if "company" in args:
            session.active_filters.company = args["company"]
        if "query" in args:
            session.active_filters.query = args["query"]

    @staticmethod
    def _describe_filters(filters: ActiveFilters) -> List[str]:
        """Build human-readable filter description list."""
        desc = []
        if filters.source:
            desc.append(f"Source={filters.source}")
        if filters.company:
            desc.append(f"Company={filters.company}")
        if filters.query:
            desc.append(f"Role={filters.query.upper()}")
        if filters.remote is not None:
            desc.append(f"Remote={filters.remote}")
        if filters.max_experience is not None:
            exp = filters.max_experience
            desc.append(f"MaxExp={exp}yr{'s' if exp > 1 else ''}")
        if filters.skills:
            desc.append(f"Skills={', '.join(filters.skills)}")
        if filters.page > 1:
            desc.append(f"Page={filters.page}")
        return desc
