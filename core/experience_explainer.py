"""
Experience Extraction Explainer
KIC-HNDCSAI-251F (002, 003, 006, 020)

Wraps ExperienceDateExtractor to return not just the final year count,
but the exact text spans and date pairs the CRF model detected —
so we can show the evidence in the UI.
"""

import os
import re
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)


_RANGE_PATTERN = re.compile(
    r"""
    (
        (?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|
           Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|
           Dec(?:ember)?)
        [\s,]+\d{4}
        |
        \d{1,2}[/\-]\d{4}
        |
        \d{4}
    )
    \s*[-–to]+\s*
    (
        (?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|
           Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|
           Dec(?:ember)?)
        [\s,]+\d{4}
        |
        \d{1,2}[/\-]\d{4}
        |
        \d{4}
        |
        present|current|now|ongoing|till\s+date|to\s+date
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

_LONE_DATE_PATTERN = re.compile(
    r"""
    (?:
        (?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|
           Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|
           Dec(?:ember)?)
        [\s,\-–/]+\d{4}
    )
    |(?:\d{1,2}[/\-]\d{4})
    |(?:\d{4})
    |(?:present|current|now|ongoing|till\s+date|to\s+date)
    """,
    re.VERBOSE | re.IGNORECASE,
)

_MONTH_MAP = {
    "jan": 1, "january": 1,   "feb": 2, "february": 2,
    "mar": 3, "march": 3,     "apr": 4, "april": 4,
    "may": 5,                 "jun": 6, "june": 6,
    "jul": 7, "july": 7,      "aug": 8, "august": 8,
    "sep": 9, "september": 9, "oct":10, "october": 10,
    "nov":11, "november":11,  "dec":12, "december": 12,
}


def _month_map_get(token: str) -> int:
    for k, v in _MONTH_MAP.items():
        if token.lower().startswith(k):
            return v
    return 1


def _parse_date(text: str) -> Optional[datetime]:
    text = text.strip().lower()
    if re.match(r"present|current|now|ongoing|till.+date|to.+date", text):
        return datetime.now()

    # Month YYYY
    m = re.match(
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?"
        r"|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?"
        r"|dec(?:ember)?)[,\s]+(\d{4})", text
    )
    if m:
        month = _month_map_get(m.group(1))
        year  = int(m.group(2))
        return datetime(year, month, 1)

    # MM/YYYY or MM-YYYY
    m = re.match(r"(\d{1,2})[/\-](\d{4})", text)
    if m:
        return datetime(int(m.group(2)), int(m.group(1)), 1)

    # bare year
    m = re.match(r"(\d{4})$", text)
    if m:
        return datetime(int(m.group(1)), 1, 1)

    return None


def _months_between(d1: datetime, d2: datetime) -> float:
    return abs((d2.year - d1.year) * 12 + (d2.month - d1.month)) / 12.0


def explain_experience(
    resume_text:    str,
    crf_model_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract experience date spans from a resume and return full evidence.

    Tries CRF extractor first (if model available), then falls back to
    regex pattern matching for span-level evidence.

    Returns
    -------
    {
        "method"         : "CRF" | "regex" | "CRF (fallback to regex sum)",
        "total_years"    : float,
        "date_ranges"    : [
            {
                "raw_text"    : "Nov 2020 - Present",
                "start"       : "Nov 2020",
                "end"         : "Present",
                "years"       : 5.5,
                "context_line": "Senior Engineer at WSO2, Nov 2020 - Present",
                "char_start"  : int,
                "char_end"    : int,
            },
            ...
        ],
        "unmatched_dates": ["2015", "2016"],
        "crf_error"      : str | None,
    }
    """
    result: Dict[str, Any] = {
        "method":          "regex",
        "total_years":     0.0,
        "date_ranges":     [],
        "unmatched_dates": [],
        "crf_error":       None,
    }

    # ── Try CRF first ─────────────────────────────────────────────────────
    crf_years = None
    if crf_model_path and os.path.exists(crf_model_path):
        try:
            from experience_date_extractor import ExperienceDateExtractor
            ext       = ExperienceDateExtractor(crf_model_path)
            crf_years = ext.calculate_total_experience(resume_text)
            result["method"] = "CRF"
        except Exception as e:
            result["crf_error"] = str(e)

    # ── Regex span extraction — gives us the evidence regardless ──────────
    ranges     = []
    used_chars = set()

    for m in _RANGE_PATTERN.finditer(resume_text):
        start_str = m.group(1)
        end_str   = m.group(2)
        d1 = _parse_date(start_str)
        d2 = _parse_date(end_str)
        if not d1 or not d2:
            continue

        yrs = _months_between(d1, d2)
        if yrs < 0.1 or yrs > 50:
            continue

        # Grab the full surrounding line as context
        line_start = resume_text.rfind("\n", 0, m.start()) + 1
        line_end   = resume_text.find("\n", m.end())
        if line_end == -1:
            line_end = len(resume_text)
        context = resume_text[line_start:line_end].strip()

        ranges.append({
            "raw_text":     m.group(0).strip(),
            "start":        start_str.strip(),
            "end":          end_str.strip(),
            "years":        round(yrs, 2),
            "context_line": context,
            "char_start":   m.start(),
            "char_end":     m.end(),
        })
        used_chars.update(range(m.start(), m.end()))

    # ── Collect lone dates (not part of any detected range) ───────────────
    for m in _LONE_DATE_PATTERN.finditer(resume_text):
        if not any(i in used_chars for i in range(m.start(), m.end())):
            token = m.group(0).strip()
            if token not in result["unmatched_dates"]:
                result["unmatched_dates"].append(token)

    result["date_ranges"] = sorted(ranges, key=lambda r: r["char_start"])

    # ── Decide final total_years ───────────────────────────────────────────
    if crf_years is not None and crf_years > 0:
        result["total_years"] = round(crf_years, 2)
    else:
        result["total_years"] = round(sum(r["years"] for r in ranges), 2)
        if result["method"] == "CRF":
            result["method"] = "CRF (fallback to regex sum)"

    return result