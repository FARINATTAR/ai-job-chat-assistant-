"""
Deep seniority and experience parser.
Audits data/jobs.json to detect hidden seniority levels (e.g. Associate III, Senior, Lead)
and updates experience_required accurately.
"""
import json
import re
import os

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "jobs.json")

def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    updated = 0
    for j in jobs:
        title = j.get("title", "")
        desc = j.get("description", "")
        combined = f"{title} {desc}".lower()
        exp = j.get("experience_required", 0)

        # 1. Seniority markers
        if any(k in combined for k in ["associate iii", "level 3", "l3", "engineer iii", "developer iii"]):
            exp = max(exp, 3)
        elif any(k in combined for k in ["associate ii", "level 2", "l2", "engineer ii", "developer ii"]):
            exp = max(exp, 2)
        elif any(k in combined for k in ["lead", "principal", "staff", "manager", "architect"]):
            exp = max(exp, 5)
        elif "senior" in combined[:120] or "sr." in combined[:120]:
            exp = max(exp, 4)

        # 2. Check explicit regex for "X+ years", "X yrs"
        matches = re.findall(r"(\d+)\s*(?:\+|-\s*\d+)?\s*(?:years?|yrs?)(?:\s*of\s*experience)?", combined)
        if matches:
            try:
                valid_years = [int(m) for m in matches if 1 <= int(m) <= 15]
                if valid_years:
                    exp = max(exp, min(valid_years))
            except ValueError:
                pass

        # 3. If explicit Intern / Fresher / Trainee in title, force 0
        if any(k in title.lower() for k in ["intern", "trainee", "graduate", "fresher"]):
            exp = 0

        if exp != j.get("experience_required", 0):
            j["experience_required"] = exp
            updated += 1

    print(f"Updated {updated} jobs with accurate experience requirements.")
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()

