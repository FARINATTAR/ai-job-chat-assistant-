"""
Multi-Agent Architecture package.
Contains Master Orchestrator and specialized sub-agents:
- ResumeParserAgent
- MatcherAgent
- ApplyAgent
"""
from .parser_agent import ResumeParserAgent
from .matcher_agent import MatcherAgent

__all__ = ["ResumeParserAgent", "MatcherAgent"]
