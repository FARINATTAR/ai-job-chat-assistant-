"""
Resume Parser Sub-Agent.
Extracts candidate profile (name, contact, designation, skills, experience, education, projects)
from raw PDF/DOCX resumes and maps them into a structured Pydantic schema.
"""
import re
import os
import json
from typing import Dict, Any, List, Optional
from ..models.schemas import (
    ResumeProfile,
    ContactInfo,
    EducationItem,
    ProjectItem,
)
from ..services.document_extractor import DocumentExtractor
from ..llm.client import LLMClient, get_llm_client
from ..llm.prompts import RESUME_PARSER_SYSTEM_PROMPT
from ..config import settings


class ResumeParserAgent:
    """Sub-agent responsible for parsing resumes into structured ResumeProfile."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or get_llm_client()
        self.taxonomy = self._load_taxonomy()

    def _load_taxonomy(self) -> Dict[str, Any]:
        """Load skills taxonomy and synonyms."""
        path = settings.SKILLS_TAXONOMY_PATH
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ResumeParserAgent] Warning: could not load taxonomy: {e}")
        return {"skills": [], "synonyms": {}}

    def normalize_skill(self, skill: str) -> str:
        """Standardize skill name using synonyms."""
        cleaned = skill.strip()
        lower = cleaned.lower()
        synonyms = self.taxonomy.get("synonyms", {})
        if lower in synonyms:
            return synonyms[lower]
        for canonical in self.taxonomy.get("skills", []):
            if lower == canonical.lower():
                return canonical
        return cleaned

    def parse_document(self, file_bytes: bytes, filename: str) -> ResumeProfile:
        """
        Complete parsing pipeline:
        1. Extract text via DocumentExtractor (handles PDF/DOCX errors)
        2. LLM structured JSON extraction
        3. Deterministic normalization and skill deduplication
        """
        raw_text = DocumentExtractor.extract_from_bytes(file_bytes, filename)

        # 1. Attempt LLM structured parsing
        profile_data = self.llm.generate_json(
            prompt=f"Resume Content:\n\n{raw_text}",
            system_instruction=RESUME_PARSER_SYSTEM_PROMPT
        )

        if profile_data:
            profile = self._build_profile_from_dict(profile_data)
        else:
            # 2. Heuristic fallback when LLM is unavailable (offline or tests)
            profile = self._heuristic_fallback_parse(raw_text, filename)

        # 3. Post-process: normalize & deduplicate skills
        normalized_skills = []
        for s in profile.skills:
            norm = self.normalize_skill(s)
            if norm and norm not in normalized_skills:
                normalized_skills.append(norm)

        # Ensure any taxonomy skills in text are captured
        text_lower = raw_text.lower()
        for skill in self.taxonomy.get("skills", []):
            pattern = r"(?<![a-zA-Z0-9])" + re.escape(skill.lower()) + r"(?![a-zA-Z0-9])"
            if re.search(pattern, text_lower) and skill not in normalized_skills:
                normalized_skills.append(skill)

        profile.skills = normalized_skills
        return profile

    def _build_profile_from_dict(self, data: Dict[str, Any]) -> ResumeProfile:
        """Safely parse dict into Pydantic ResumeProfile."""
        try:
            contact_data = data.get("contact", {})
            contact = ContactInfo(
                email=contact_data.get("email"),
                phone=contact_data.get("phone"),
                linkedin=contact_data.get("linkedin"),
                github=contact_data.get("github"),
            )

            education = [
                EducationItem(
                    degree=item.get("degree"),
                    institution=item.get("institution"),
                    year=str(item.get("year", "")) if item.get("year") else None
                )
                for item in data.get("education", []) if isinstance(item, dict)
            ]

            projects = [
                ProjectItem(
                    name=item.get("name", "Project"),
                    description=item.get("description"),
                    technologies=item.get("technologies", [])
                )
                for item in data.get("projects", []) if isinstance(item, dict)
            ]

            years_exp = 0.0
            try:
                years_exp = float(data.get("years_of_experience", 0.0))
            except (ValueError, TypeError):
                pass

            return ResumeProfile(
                name=data.get("name") or "Candidate",
                contact=contact,
                designation=data.get("designation") or "Software Engineer",
                skills=data.get("skills") or [],
                years_of_experience=years_exp,
                experience_summary=data.get("experience_summary"),
                education=education,
                projects=projects
            )
        except Exception as e:
            print(f"[ResumeParserAgent] Error converting dict to schema: {e}")
            return ResumeProfile()

    def _heuristic_fallback_parse(self, text: str, filename: str) -> ResumeProfile:
        """Deterministic regex-based parsing when LLM is unavailable."""
        # Email
        email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        email = email_match.group(0) if email_match else None

        # Phone
        phone_match = re.search(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        phone = phone_match.group(0) if phone_match else None

        # GitHub & LinkedIn
        gh_match = re.search(r"github\.com/[a-zA-Z0-9_-]+", text, re.IGNORECASE)
        li_match = re.search(r"linkedin\.com/in/[a-zA-Z0-9_-]+", text, re.IGNORECASE)

        # Name heuristic: First non-empty line
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        candidate_name = lines[0] if lines else "Candidate"
        if len(candidate_name) > 40 or "@" in candidate_name:
            candidate_name = "Candidate"

        # Designation heuristic
        designation = "Software Engineer"
        for title_candidate in ["Frontend Developer", "Backend Developer", "Full Stack Developer", "Data Scientist", "DevOps Engineer", "Machine Learning Engineer", "SDE Intern"]:
            if title_candidate.lower() in text.lower():
                designation = title_candidate
                break

        # Experience years heuristic
        exp_years = 0.0
        exp_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:\+|-\s*\d+)?\s*(?:years?|yrs?)(?:\s*of\s*experience)?", text, re.IGNORECASE)
        if exp_match:
            try:
                exp_years = min(float(exp_match.group(1)), 25.0)
            except ValueError:
                pass

        return ResumeProfile(
            name=candidate_name,
            contact=ContactInfo(
                email=email,
                phone=phone,
                github=f"https://{gh_match.group(0)}" if gh_match else None,
                linkedin=f"https://{li_match.group(0)}" if li_match else None,
            ),
            designation=designation,
            skills=[],
            years_of_experience=exp_years,
            experience_summary=f"Parsed from {filename}",
            education=[],
            projects=[]
        )

