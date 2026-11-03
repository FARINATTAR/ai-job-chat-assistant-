"""
Server-Sent Events (SSE) streaming helpers.
Formats agent-to-agent handoffs, reasoning thoughts, and message tokens for real-time UI.
"""
import json
from typing import Dict, Any, Optional


def format_sse(event_type: str, data: Any) -> str:
    """Format data as a Server-Sent Event string."""
    payload = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data
    return f"event: {event_type}\ndata: {payload}\n\n"


class StreamEmitter:
    """Helper to emit standard agent lifecycle events."""

    @staticmethod
    def agent_start(agent_name: str, thought: str) -> str:
        return format_sse("agent_start", {
            "agent": agent_name,
            "thought": thought
        })

    @staticmethod
    def agent_handoff(from_agent: str, to_agent: str, reason: str) -> str:
        return format_sse("agent_handoff", {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "reason": reason
        })

    @staticmethod
    def agent_thought(agent_name: str, thought: str) -> str:
        return format_sse("agent_thought", {
            "agent": agent_name,
            "thought": thought
        })

    @staticmethod
    def token(content: str) -> str:
        return format_sse("token", {
            "content": content
        })

    @staticmethod
    def job_results(jobs: list) -> str:
        return format_sse("job_results", {
            "jobs": jobs
        })

    @staticmethod
    def complete(status: str = "success") -> str:
        return format_sse("complete", {
            "status": status
        })

    @staticmethod
    def error(message: str) -> str:
        return format_sse("error", {
            "message": message
        })

