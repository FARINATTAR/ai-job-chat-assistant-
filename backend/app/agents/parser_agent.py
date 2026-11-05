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

        sections = self._extract_sections(raw_text)

        if profile_data:
            profile = self._build_profile_from_dict(profile_data)
        else:
            # 2. Heuristic fallback when LLM is unavailable (offline or tests)
            profile = self._heuristic_fallback_parse(raw_text, filename, sections)

        # 3. Post-process: normalize & deduplicate skills
        normalized_skills = []
        for s in profile.skills:
            norm = self.normalize_skill(s)
            if norm and norm not in normalized_skills:
                normalized_skills.append(norm)

        # Ensure any skills from skills section are added
        if "skills" in sections:
            section_skills = self._extract_skills_from_section(sections["skills"])
            for s in section_skills:
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

    @staticmethod
    def _extract_sections(raw_text: str) -> Dict[str, str]:
        """Split resume text into semantic sections using header detection."""
        headers = [
            ("education", r"(?:^|\n)\s*(?:EDUCATION|ACADEMIC\s+BACKGROUND|QUALIFICATIONS)\b"),
            ("skills", r"(?:^|\n)\s*(?:TECHNICAL\s+SKILLS|CORE\s+COMPETENCIES|CORE\s+SKILLS|SKILLS|TECHNOLOGIES)\b"),
            ("projects", r"(?:^|\n)\s*(?:PROJECTS|PERSONAL\s+PROJECTS|KEY\s+PROJECTS|ACADEMIC\s+PROJECTS|TECHNICAL\s+PROJECTS)\b"),
            ("experience", r"(?:^|\n)\s*(?:WORK\s+EXPERIENCE|PROFESSIONAL\s+EXPERIENCE|EXPERIENCE|INTERNSHIPS?|EMPLOYMENT\s+HISTORY)\b"),
        ]
        matches = []
        for sec_name, pattern in headers:
            m = re.search(pattern, raw_text, re.IGNORECASE)
            if m:
                matches.append((m.start(), m.end(), sec_name))
        matches.sort(key=lambda x: x[0])

        sections: Dict[str, str] = {}
        for i, (start, end, name) in enumerate(matches):
            next_start = matches[i + 1][0] if i + 1 < len(matches) else len(raw_text)
            sections[name] = raw_text[end:next_start].strip()
        return sections

    @staticmethod
    def _extract_skills_from_section(section_text: str) -> List[str]:
        """Extract skill keywords cleanly from the skills section."""
        extracted: List[str] = []
        # First fix any line-wrapped hyphens in the section text
        cleaned_sec = re.sub(r"(\b[A-Za-z]+)-\s*\n\s*([A-Za-z]+\b)", r"\1\2", section_text)
        lines = [l.strip() for l in cleaned_sec.splitlines() if l.strip()]

        for line in lines:
            # 1. Strip leading bullet markers (•, -, *, 1., etc.)
            clean_line = re.sub(r"^[•\*\-\d+\.]+\s*", "", line).strip()
            # 2. Strip leading category labels like 'GenAI & AI Capabilities:', 'Languages:', etc.
            clean_content = re.sub(r"^[A-Za-z0-9\s&/\\()\-]+[:\-]\s*", "", clean_line).strip()
            # 3. Split on commas, pipes, bullets, and newlines
            tokens = re.split(r"[,|•\*\n]+", clean_content)
            for t in tokens:
                cleaned = t.strip()
                # Remove parens info like 'Python (Advanced)'
                cleaned = re.sub(r"\(.*?\)", "", cleaned).strip()
                # Remove leading stray punctuation like '& AI' or '- Tool'
                cleaned = re.sub(r"^[&/\\:\-\*•\s]+", "", cleaned).strip()
                # Validate length and content
                if (
                    cleaned
                    and 2 <= len(cleaned) <= 35
                    and not re.match(r"^\d+$", cleaned)
                    and not cleaned.lower().startswith("capabilities")
                ):
                    if cleaned not in extracted:
                        extracted.append(cleaned)
        return extracted

    def _heuristic_fallback_parse(
        self, text: str, filename: str, sections: Optional[Dict[str, str]] = None
    ) -> ResumeProfile:
        """Deterministic regex-based parsing when LLM is unavailable."""
        if sections is None:
            sections = self._extract_sections(text)

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

        # Designation heuristic: comprehensive multi-domain career track detection
        designation = "Software Engineer"
        career_tracks = [
            # Embedded, Firmware & Hardware
            (r"\b(?:embedded\s+(?:systems?\s+)?(?:engineer|developer)|firmware\s+engineer|iot\s+engineer|hardware\s+engineer|rtos\s+developer)\b", "Embedded Engineer"),
            # Human Resources & Talent
            (r"\b(?:human\s+resources|talent\s+acquisition|hr\s+(?:generalist|executive|specialist|manager|intern|partner)|technical\s+recruiter|recruiter|people\s+operations)\b", "HR Specialist"),
            # Data & Analytics
            (r"\b(?:data\s+analyst|business\s+analyst|data\s+scientist|data\s+engineer|bi\s+developer|analytics\s+engineer)\b", "Data Analyst"),
            # UI/UX & Design
            (r"\b(?:ui[/-]ux\s+designer|product\s+designer|ux\s+researcher|graphic\s+designer|web\s+designer)\b", "UI/UX Designer"),
            # Quality Assurance & Testing
            (r"\b(?:qa\s+engineer|sdet|quality\s+assurance|test\s+engineer|automation\s+tester|software\s+tester)\b", "QA Engineer"),
            # Product & Project Management
            (r"\b(?:product\s+manager|associate\s+product\s+manager|technical\s+program\s+manager|project\s+manager|scrum\s+master)\b", "Product Manager"),
            # DevOps & Cloud Infrastructure
            (r"\b(?:devops\s+engineer|cloud\s+engineer|site\s+reliability\s+engineer|sre|platform\s+engineer|infrastructure\s+engineer)\b", "DevOps Engineer"),
            # AI / Machine Learning & GenAI
            (r"\b(?:genai\s+engineer|generative\s+ai|ai\s+engineer|machine\s+learning\s+engineer|nlp\s+engineer|deep\s+learning\s+engineer|prompt\s+engineer)\b", "AI Engineer"),
            # Marketing & Growth
            (r"\b(?:digital\s+marketing|marketing\s+(?:manager|specialist|executive|intern|lead)|growth\s+marketer|seo\s+specialist|content\s+strategist|brand\s+manager)\b", "Marketing Specialist"),
            # Sales & Business Development
            (r"\b(?:business\s+development|sales\s+(?:manager|executive|representative|associate|lead)|account\s+executive)\b", "Business Development"),
            # Finance & Accounting
            (r"\b(?:financial\s+analyst|accountant|finance\s+specialist|chartered\s+accountant|investment\s+analyst)\b", "Financial Analyst"),
            # Web & Software Development Tracks
            (r"\b(?:full\s*stack\s+developer|full\s*stack\s+engineer)\b", "Full Stack Developer"),
            (r"\b(?:frontend\s+developer|frontend\s+engineer|react\s+developer|web\s+developer)\b", "Frontend Developer"),
            (r"\b(?:backend\s+developer|backend\s+engineer|node\s+developer|python\s+developer|java\s+developer)\b", "Backend Developer"),
            (r"\b(?:mobile\s+developer|android\s+developer|ios\s+developer|flutter\s+developer)\b", "Mobile Developer"),
            (r"\b(?:sde\s+intern|software\s+intern|engineering\s+intern)\b", "SDE Intern"),
            (r"\b(?:software\s+(?:development\s+)?engineer|sde|software\s+developer)\b", "Software Engineer"),
        ]

        # First scan the candidate header (first 5 lines) where candidates state their title
        header_text = "\n".join(lines[:5])
        found_title = None
        for pattern, title_val in career_tracks:
            if re.search(pattern, header_text, re.IGNORECASE):
                found_title = title_val
                break

        # If not found in header, scan the full resume text
        if not found_title:
            for pattern, title_val in career_tracks:
                if re.search(pattern, text, re.IGNORECASE):
                    found_title = title_val
                    break

        if found_title:
            designation = found_title

        # Experience years heuristic: look for years and months (e.g. internships)
        exp_years = 0.0
        exp_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:\+|-\s*\d+)?\s*(?:years?|yrs?)(?:\s*of\s*experience)?", text, re.IGNORECASE)
        if exp_match:
            try:
                exp_years = min(float(exp_match.group(1)), 25.0)
            except ValueError:
                pass
        elif "intern" in text.lower() or "internship" in text.lower():
            months_match = re.search(r"(\d+)\s*(?:months?|mos?)(?:\s*internship|\s*experience)?", text, re.IGNORECASE)
            if months_match:
                try:
                    exp_years = round(float(months_match.group(1)) / 12.0, 1)
                except ValueError:
                    pass

        # Education heuristic: extract degree, institution, and year from text or education section
        education = self._extract_education_heuristic(text, sections.get("education"))

        # Projects heuristic: extract project names and descriptions
        projects = self._extract_projects_heuristic(text, sections.get("projects"))

        # Skills from skills section
        skills = []
        if "skills" in sections:
            skills = self._extract_skills_from_section(sections["skills"])

        return ResumeProfile(
            name=candidate_name,
            contact=ContactInfo(
                email=email,
                phone=phone,
                github=f"https://{gh_match.group(0)}" if gh_match else None,
                linkedin=f"https://{li_match.group(0)}" if li_match else None,
            ),
            designation=designation,
            skills=skills,
            years_of_experience=exp_years,
            experience_summary=f"Parsed from {filename}",
            education=education,
            projects=projects,
        )

    # ------------------------------------------------------------------
    # Heuristic sub-extractors for education and projects
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_education_heuristic(text: str, edu_section: Optional[str] = None) -> list:
        """Extract education entries grouping degree, college (with apostrophes), and year."""
        from ..models.schemas import EducationItem

        education: list = []
        deg_regex = re.compile(
            r"\b(?:Bachelor(?:\s+of\s+[A-Za-z\s]+)?|B\.?Tech|B\.?E\.?|B\.?S\.?|Master(?:\s+of\s+[A-Za-z\s]+)?|M\.?Tech|M\.?E\.?|M\.?S\.?|MCA|BCA|B\.?Sc|M\.?Sc|MBA|Ph\.?D|Diploma)\b[^\n\(\),;]*",
            re.IGNORECASE,
        )
        year_regex = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
        inst_regex = re.compile(
            r"([A-Za-z0-9\s&\'\.,\-]+(?:University|Institute|College|School|Academy)[A-Za-z0-9\s&\'\.,\-]*)",
            re.IGNORECASE,
        )

        source_text = edu_section if edu_section else text
        lines = [l.strip() for l in source_text.splitlines() if l.strip()]

        current_entry: Dict[str, Any] = {}
        for line in lines:
            if re.search(r"\b(?:cgpa|percentage|marks|grade)\b", line, re.IGNORECASE):
                continue
            y_match = year_regex.findall(line)
            year = y_match[-1] if y_match else None

            d_match = deg_regex.search(line)
            i_match = inst_regex.search(line)

            if d_match:
                deg = d_match.group(0).strip().rstrip(",. ")
                if "degree" in current_entry:
                    education.append(
                        EducationItem(
                            degree=current_entry.get("degree"),
                            institution=current_entry.get("institution"),
                            year=current_entry.get("year"),
                        )
                    )
                    current_entry = {}
                current_entry["degree"] = deg
                if year and "year" not in current_entry:
                    current_entry["year"] = year

            if i_match:
                inst = i_match.group(0).strip().rstrip(",. ")
                # If current already has both, flush it
                if "institution" in current_entry and "degree" in current_entry:
                    education.append(
                        EducationItem(
                            degree=current_entry.get("degree"),
                            institution=current_entry.get("institution"),
                            year=current_entry.get("year"),
                        )
                    )
                    current_entry = {}
                current_entry["institution"] = inst
                if year and "year" not in current_entry:
                    current_entry["year"] = year

            if year and "year" not in current_entry:
                current_entry["year"] = year

        if current_entry and (current_entry.get("degree") or current_entry.get("institution")):
            education.append(
                EducationItem(
                    degree=current_entry.get("degree") or "Bachelor of Engineering",
                    institution=current_entry.get("institution"),
                    year=current_entry.get("year"),
                )
            )

        return education

    @staticmethod
    def _extract_projects_heuristic(text: str, proj_section: Optional[str] = None) -> list:
        """Extract project entries cleanly."""
        from ..models.schemas import ProjectItem

        projects: list = []
        source_text = proj_section

        if not source_text:
            proj_match = re.search(
                r"(?:^|\n)\s*(?:Projects?|Personal Projects?|Key Projects?)\s*[:\-]?\s*(.+)",
                text,
                re.IGNORECASE | re.DOTALL,
            )
            if proj_match:
                remaining = proj_match.group(1)
                cutoff = re.search(r"\n\s*(?:Education|Experience|Technical Skills|Skills|Certifications?|Awards?)\s*[:\-]", remaining, re.IGNORECASE)
                source_text = remaining[:cutoff.start()].strip() if cutoff else remaining.strip()

        if source_text:
            lines = [l.strip() for l in re.split(r"(?:\n\s*(?:[•\-\*\d]+[.\)]\s*)|\n+)", source_text) if l.strip()]
            for item in lines:
                clean_item = re.sub(r"^[•\*\-\d+\.]+\s*", "", item).strip()
                if len(clean_item) < 6:
                    continue
                if " - " in clean_item:
                    name, desc = clean_item.split(" - ", 1)
                elif ":" in clean_item:
                    name, desc = clean_item.split(":", 1)
                elif " | " in clean_item:
                    name, desc = clean_item.split(" | ", 1)
                else:
                    name = clean_item[:50].strip()
                    desc = clean_item.strip()
                projects.append(ProjectItem(name=name.strip(), description=desc.strip()))

        return projects

