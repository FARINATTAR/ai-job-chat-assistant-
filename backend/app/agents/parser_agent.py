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

        # Education heuristic: extract degree, institution, and year from text
        education = self._extract_education_heuristic(text)

        # Projects heuristic: extract project names and descriptions from text
        projects = self._extract_projects_heuristic(text)

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
            education=education,
            projects=projects,
        )

    # ------------------------------------------------------------------
    # Heuristic sub-extractors for education and projects
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_education_heuristic(text: str) -> list:
        """Extract education entries using regex patterns."""
        from ..models.schemas import EducationItem

        education: list = []
        degree_patterns = [
            r"((?:Bachelor|Master|B\.?S\.?|M\.?S\.?|B\.?Tech|M\.?Tech|B\.?E\.?|M\.?E\.?|B\.?Sc|M\.?Sc|MBA|Ph\.?D|Diploma)"
            r"[^,\n]{0,80}?)"
            r"[,\s]+([A-Z][a-zA-Z\s&]+(?:University|Institute|College|School|Academy)[a-zA-Z\s]*)"
            r"[,\s]*(\d{4})?",
        ]
        for pattern in degree_patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                degree = m.group(1).strip().rstrip(",. ")
                institution = m.group(2).strip().rstrip(",. ")
                year = m.group(3) if m.lastindex >= 3 else None
                education.append(EducationItem(degree=degree, institution=institution, year=year))

        # Simpler fallback: look for lines like "B.S. Computer Science, 2022"
        if not education:
            simple = re.findall(
                r"((?:Bachelor|Master|B\.?S\.?|M\.?S\.?|B\.?Tech|M\.?Tech|B\.?E\.?|M\.?E\.?|B\.?Sc|M\.?Sc|MBA|Ph\.?D|Diploma)"
                r"[^.\n]{5,100}?)"
                r"[,\s]*(\d{4})",
                text,
                re.IGNORECASE,
            )
            for deg_text, year in simple:
                education.append(EducationItem(degree=deg_text.strip(), year=year))

        return education

    @staticmethod
    def _extract_projects_heuristic(text: str) -> list:
        """Extract project entries from sections labeled 'Projects'."""
        from ..models.schemas import ProjectItem

        projects: list = []

        # Find a "Projects" section
        proj_match = re.search(
            r"(?:^|\n)\s*(?:Projects?|Personal Projects?|Key Projects?)\s*[:\-]?\s*(.+)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if proj_match:
            remaining = proj_match.group(1)
            # Stop at the next major section header if any
            cutoff = re.search(r"\n\s*(?:Education|Experience|Technical Skills|Skills|Certifications?|Awards?)\s*[:\-]", remaining, re.IGNORECASE)
            section_text = remaining[:cutoff.start()].strip() if cutoff else remaining.strip()

            # Split by lines or bullet points
            lines = [l.strip() for l in re.split(r"(?:\n\s*(?:[•\-\*\d]+[.\)]\s*)|\n+)", section_text) if l.strip()]
            for item in lines:
                if len(item) < 8:
                    continue
                # Split on colon or hyphen if present
                if ":" in item:
                    name, desc = item.split(":", 1)
                elif " - " in item:
                    name, desc = item.split(" - ", 1)
                else:
                    name = item[:80].strip()
                    desc = item.strip()
                projects.append(ProjectItem(name=name.strip(), description=desc.strip()))

        return projects

