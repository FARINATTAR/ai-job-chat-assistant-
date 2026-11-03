"""
Multi-Agent Architecture package.
Contains Master Orchestrator and specialized sub-agents:
- ResumeParserAgent
- MatcherAgent
- ApplyAgent
"""
from .parser_agent import ResumeParserAgent

__all__ = ["ResumeParserAgent"]
