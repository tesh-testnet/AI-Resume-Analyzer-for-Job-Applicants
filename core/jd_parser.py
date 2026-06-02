"""
Robust extraction of job requirements from a job description text.
Used in the /compare-job-description endpoint.
"""

import re
from typing import Dict, Optional, Union

# ------------------------------------------------------------------
# 1. Job Title extraction
# ------------------------------------------------------------------
def extract_job_title(text: str) -> str:
    """
    Extract job title from job description.
    Priority: 
      - Look for common title markers: 'Job Title:', 'Position:', 'Role:', 'Title:'
      - Otherwise, take the first non‑empty line that contains typical title keywords.
    """
    lines = text.split('\n')
    # Strip and filter empty lines
    lines = [line.strip() for line in lines if line.strip()]
    if not lines:
        return "Not specified"

    # Patterns for explicit title fields
    patterns = [
        r'(?:Job\s*Title|Position|Role|Title)\s*:?\s*(.+)',
        r'(?:We are looking for a|Hiring a)\s+(.+)',
        r'(?:About the role|The role):?\s*(.+)'
    ]
    for pattern in patterns:
        for line in lines[:10]:  # only first 10 lines
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                if title and len(title) < 100:
                    return title

    # If no explicit marker, take first line that looks like a title
    title_keywords = ['engineer', 'developer', 'analyst', 'manager', 'lead', 'architect',
                      'scientist', 'specialist', 'consultant', 'director', 'head', 'chief']
    for line in lines[:5]:
        lower_line = line.lower()
        if any(kw in lower_line for kw in title_keywords):
            # Also avoid lines that are too long (likely not title)
            if len(line) < 80:
                return line

    # Fallback: first line of the description
    return lines[0][:80]

# ------------------------------------------------------------------
# 2. Education extraction
# ------------------------------------------------------------------
def extract_education(text: str) -> str:
    """
    Extract required education level.
    Returns a string like "Bachelor's degree" or "Master's or PhD".
    """
    text_lower = text.lower()
    education_levels = {
        'phd': 'PhD',
        'doctorate': 'PhD',
        'master': "Master's degree",
        'mba': 'MBA',
        'bachelor': "Bachelor's degree",
        'bs': 'Bachelor of Science',
        'ba': 'Bachelor of Arts',
        'associate': "Associate's degree",
        'high school': 'High school diploma',
    }
    found = []
    for key, value in education_levels.items():
        if re.search(r'\b' + re.escape(key) + r'\b', text_lower):
            found.append(value)
    # Remove duplicates
    found = list(dict.fromkeys(found))
    if found:
        if len(found) == 1:
            return found[0]
        else:
            # e.g., "Bachelor's or Master's"
            return " or ".join(found)
    # Check for "or equivalent"
    if re.search(r'or equivalent', text_lower):
        base = "Bachelor's degree or equivalent"
        if 'master' in text_lower or 'phd' in text_lower:
            base = "Advanced degree or equivalent"
        return base
    return "Not specified"

# ------------------------------------------------------------------
# 3. Experience years extraction
# ------------------------------------------------------------------
def extract_experience_years(text: str) -> Optional[float]:
    """
    Extract minimum required years of experience.
    Returns a float (e.g., 3.0) or None if not found.
    """
    patterns = [
        # "3+ years", "3+ years of experience"
        r'(\d+(?:\.\d+)?)\s*\+\s*years?',
        # "3-5 years"
        r'(\d+(?:\.\d+)?)\s*[-–]\s*\d+\s*years?',
        # "minimum of 3 years", "at least 3 years"
        r'(?:minimum|at least)\s+(\d+(?:\.\d+)?)\s*years?',
        # "3 years of experience"
        r'(\d+(?:\.\d+)?)\s*years?\s+of\s+experience',
        # "experience: 3+ years"
        r'experience:?\s*(\d+(?:\.\d+)?)\s*\+?\s*years?',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None

# ------------------------------------------------------------------
# 4. Salary extraction
# ------------------------------------------------------------------
def extract_salary(text: str) -> str:
    """
    Extract salary range or amount.
    Returns a string like "$120k - $150k" or "Not mentioned".
    """
    # Look for patterns like $120,000, $120k, 120k, 120,000, etc.
    salary_patterns = [
        # $100,000 - $120,000
        r'\$?(\d{1,3}(?:,\d{3})*|\d+(?:\.\d+)?[kK]?)\s*[-–]\s*\$?(\d{1,3}(?:,\d{3})*|\d+(?:\.\d+)?[kK]?)',
        # $100k - $120k
        r'\$?(\d+(?:\.\d+)?[kK])\s*[-–]\s*\$?(\d+(?:\.\d+)?[kK])',
        # $100,000 per year
        r'\$(\d{1,3}(?:,\d{3})*|\d+(?:\.\d+)?[kK]?)\s*(?:per\s*yea|/yr|annually)',
        # $100k
        r'\$(\d+(?:\.\d+)?[kK])\b',
    ]
    for pattern in salary_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 2:
                return f"${groups[0]} - ${groups[1]}"
            else:
                return f"${groups[0]}"
    return "Not mentioned"

# ------------------------------------------------------------------
# 5. Main function
# ------------------------------------------------------------------
def extract_job_requirements(jd_text: str) -> Dict[str, Union[str, float, None]]:
    """
    Extract job title, required education, experience years, and salary from a job description.
    Returns a dictionary with keys: job_title, required_education, required_experience_years, salary_range
    """
    return {
        "job_title": extract_job_title(jd_text),
        "required_education": extract_education(jd_text),
        "required_experience_years": extract_experience_years(jd_text),
        "salary_range": extract_salary(jd_text),
    }

# ------------------------------------------------------------------
# Quick test (if run directly)
# ------------------------------------------------------------------
if __name__ == "__main__":
    sample_jd = """
    Job Title: Senior Machine Learning Engineer
    We are looking for a Senior ML Engineer with at least 5+ years of experience.
    Required: Master's degree in CS or related field, PhD is a plus.
    Salary: $150k - $180k per year.
    """
    result = extract_job_requirements(sample_jd)
    print(result)