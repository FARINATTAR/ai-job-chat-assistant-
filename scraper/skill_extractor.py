"""
Skill and experience extractor for job descriptions.
Extracts standardized tech skills and required experience using taxonomy and regex.
"""
import re
import json
import os
from typing import List, Tuple, Set

TAXONOMY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "skills_taxonomy.json")


class SkillExtractor:
    def __init__(self, taxonomy_path: str = TAXONOMY_PATH):
        self.skills: List[str] = []
        self.synonyms = {}
        self._load_taxonomy(taxonomy_path)

    def _load_taxonomy(self, path: str):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.skills = data.get("skills", [])
                    self.synonyms = data.get("synonyms", {})
            except Exception as e:
                print(f"Error loading taxonomy from {path}: {e}")

    def normalize_skill(self, skill: str) -> str:
        """Map raw skill string or alias to canonical form."""
        skill_clean = skill.strip()
        lower = skill_clean.lower()
        if lower in self.synonyms:
            return self.synonyms[lower]
        for canonical in self.skills:
            if lower == canonical.lower():
                return canonical
        return skill_clean

    def extract_skills_from_text(self, text: str) -> List[str]:
        """Find tech skills in freeform description text."""
        if not text:
            return []
        
        found: Set[str] = set()
        text_lower = f" {text.lower()} "

        # Check for known taxonomy skills
        for skill in self.skills:
            pattern = r"(?<![a-zA-Z0-9])" + re.escape(skill.lower()) + r"(?![a-zA-Z0-9])"
            if re.search(pattern, text_lower):
                found.add(skill)

        # Check for synonyms
        for alias, canonical in self.synonyms.items():
            pattern = r"(?<![a-zA-Z0-9])" + re.escape(alias) + r"(?![a-zA-Z0-9])"
            if re.search(pattern, text_lower):
                found.add(canonical)

        return sorted(list(found))

    def extract_experience_years(self, text: str, default: int = 0) -> int:
        """Extract minimum years of experience from text (e.g. '3+ years', '1 to 2 yrs')."""
        if not text:
            return default
        
        lower = text.lower()
        if any(term in lower for term in ["intern", "internship", "fresher", "entry level", "graduate"]):
            return 0

        # Pattern: "X+ years", "X-Y years", "minimum X years", "X yrs"
        matches = re.findall(r"(\d+)\s*(?:\+|-\s*\d+)?\s*(?:to\s*\d+\s*)?(?:years?|yrs?)(?:\s*of\s*experience)?", lower)
        if matches:
            try:
                years = [int(m) for m in matches if int(m) <= 20]
                if years:
                    return min(years)
            except ValueError:
                pass

        return default

