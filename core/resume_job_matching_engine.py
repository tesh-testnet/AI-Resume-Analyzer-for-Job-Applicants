"""
Resume-Job Role Matching Engine
AI-Based Resume Analyzer for Job Applicants

Implements the job role matching strategy from the project presentation:
1. Cosine similarity for content relevance (Roy et al., 2020)
2. Weighted suitability scoring across 4 components
3. Rule-based recommendation generation

Usage:
    from resume_job_matching_engine import analyze_resume_job_fit
    result = analyze_resume_job_fit(resume_result, job_result)

Authors: KIC-HNDCSAI-251F (002, 003, 006, 020)
Date: February 2026
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np


# =============================================================================
# SIMILARITY FUNCTIONS
# =============================================================================

def cosine_similarity_tfidf(tfidf_resume: Dict[str, float],
                             tfidf_job:    Dict[str, float]) -> float:
    if not tfidf_resume or not tfidf_job:
        return 0.0
    all_terms = set(tfidf_resume.keys()) | set(tfidf_job.keys())
    if not all_terms:
        return 0.0
    vec_resume = np.array([tfidf_resume.get(t, 0.0) for t in all_terms])
    vec_job    = np.array([tfidf_job.get(t, 0.0)    for t in all_terms])
    dot   = np.dot(vec_resume, vec_job)
    norm1 = np.linalg.norm(vec_resume)
    norm2 = np.linalg.norm(vec_job)
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return float(max(0.0, min(1.0, dot / (norm1 * norm2))))


def cosine_similarity_tokens(tokens_resume: List[str],
                              tokens_job:    List[str]) -> float:
    if not tokens_resume or not tokens_job:
        return 0.0
    vocab     = list(set(tokens_resume) | set(tokens_job))
    vec_res   = np.array([tokens_resume.count(t) for t in vocab], dtype=float)
    vec_job   = np.array([tokens_job.count(t)    for t in vocab], dtype=float)
    n1, n2 = np.linalg.norm(vec_res), np.linalg.norm(vec_job)
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    return float(np.dot(vec_res, vec_job) / (n1 * n2))


# =============================================================================
# COMPONENT SCORING FUNCTIONS
# =============================================================================

EDUCATION_LEVELS: Dict[str, int] = {
    'Unknown': 0,
    'Diploma': 1,
    'Bachelors': 2,
    'Masters': 3,
    'PhD': 4
}


def skill_match_score(
        candidate_skills: List[str],
        required_skills:  List[str]
) -> Tuple[float, List[str], List[str]]:
    cand_set = {s.lower().strip() for s in (candidate_skills or [])}
    req_set  = {s.lower().strip() for s in (required_skills  or [])}
    if not req_set:
        return 1.0, [], []
    matching = sorted(cand_set & req_set)
    missing  = sorted(req_set - cand_set)
    score    = len(matching) / len(req_set)
    return score, matching, missing


def experience_match_score(candidate_years: float,
                            required_years:  float,
                            tolerance:       float = 0.5) -> float:
    if required_years <= 0:
        return 1.0 if candidate_years >= 0 else 0.0
    ratio = candidate_years / required_years
    if ratio >= 1.0:
        return 1.0
    if ratio >= tolerance:
        return (ratio - tolerance) / (1.0 - tolerance)
    return 0.0


def education_match_score(candidate_education: str,
                           required_education:  str) -> float:
    cand_level = EDUCATION_LEVELS.get(candidate_education or 'Unknown', 0)
    req_level  = EDUCATION_LEVELS.get(required_education  or 'Unknown', 0)
    if req_level == 0:
        return 1.0 if cand_level >= 0 else 0.0
    if cand_level >= req_level:
        return 1.0
    return max(0.0, cand_level - req_level)


# =============================================================================
# DEFAULT WEIGHTS
# =============================================================================

DEFAULT_WEIGHTS: Dict[str, float] = {
    'text_similarity':  0.30,
    'skill_match':      0.40,
    'experience_match': 0.20,
    'education_match':  0.10,
}


# =============================================================================
# RECOMMENDATION GENERATOR (UPDATED – evidence‑based)
# =============================================================================

def generate_recommendations(
        skill_score:        float,
        exp_score:          float,
        edu_score:          float,
        text_sim:           float,
        missing_skills:     List[str],
        candidate_years:    float,
        required_years:     float,
        candidate_edu:      str,
        required_edu:       str,
        section_completeness: Dict[str, bool],
        priority:           str
) -> List[Dict[str, str]]:
    """
    Generate structured, evidence-based improvement recommendations.

    Architecture based on:
    - Weerasinghe et al. (2023): multi-dimensional content scoring with
      missing content suggestions using NLP and rule-based techniques.
    - Amin et al. (2019): weighted scoring formula for resume-job matching.
    - Frontiers XAI review (2025): explainable output layers for PJRS.

    Each recommendation is anchored to a measurable threshold, tagged with
    a priority level, and includes a concrete actionable step.
    """
    recs: List[Dict[str, str]] = []

    # =================================================================
    # DIMENSION 1: SKILLS (Amin et al. 2019 – 50% weight in overall fit)
    # =================================================================
    if skill_score < 0.40:
        top_missing = missing_skills[:5]
        extras = len(missing_skills) - 5
        recs.append({
            'category': 'Skills',
            'priority': 'High',
            'message': (
                f"Critical skill gap: only {skill_score*100:.0f}% of required "
                f"skills present. Missing: {', '.join(top_missing)}"
                f"{f' and {extras} more' if extras > 0 else ''}."
            ),
            'action': (
                "Focus on acquiring these core skills through online courses, "
                "certifications, or hands-on projects. Highlight any transferable "
                "experience that demonstrates equivalent competency."
            )
        })
    elif skill_score < 0.70:
        top_missing = missing_skills[:3]
        extras = len(missing_skills) - 3
        recs.append({
            'category': 'Skills',
            'priority': 'High',
            'message': (
                f"Moderate skill gap ({skill_score*100:.0f}% match). "
                f"Add: {', '.join(top_missing)}"
                f"{f' (+{extras} more)' if extras > 0 else ''}."
            ),
            'action': (
                "Mention any exposure or coursework involving these skills. "
                "Even introductory-level familiarity can improve your match score."
            )
        })
    elif skill_score < 0.90 and missing_skills:
        recs.append({
            'category': 'Skills',
            'priority': 'Medium',
            'message': (
                f"Near-complete skill match ({skill_score*100:.0f}%). "
                f"Consider adding: {', '.join(missing_skills[:3])}."
            ),
            'action': (
                "These are low-effort, high-impact additions. Mention any "
                "related tools or willingness to learn them."
            )
        })
    else:
        recs.append({
            'category': 'Strengths',
            'priority': 'Info',
            'message': (
                f"Excellent skill alignment ({skill_score*100:.0f}% match). "
                "Your technical skills strongly match the role requirements."
            ),
            'action': (
                "Keep these skills current and consider deepening expertise "
                "through advanced projects or certifications."
            )
        })

    # =================================================================
    # DIMENSION 2: EXPERIENCE (Amin et al. 2019 – 20% weight)
    # =================================================================
    if exp_score < 0.30:
        gap = max(0, required_years - candidate_years)
        recs.append({
            'category': 'Experience',
            'priority': 'High',
            'message': (
                f"Significant experience gap: {candidate_years:.1f} years "
                f"detected vs. {required_years:.1f} years required "
                f"(gap: {gap:.1f} years)."
            ),
            'action': (
                f"To bridge the {gap:.1f}-year gap, emphasize internships, "
                "freelance work, open-source contributions, and academic "
                "projects. Quantify achievements with metrics where possible."
            )
        })
    elif exp_score < 0.60:
        gap = max(0, required_years - candidate_years)
        recs.append({
            'category': 'Experience',
            'priority': 'Medium',
            'message': (
                f"Minor experience gap: {candidate_years:.1f} years vs. "
                f"{required_years:.1f} required ({gap:.1f} year gap)."
            ),
            'action': (
                "Highlight leadership roles, rapid skill acquisition, or "
                "project outcomes that demonstrate maturity beyond your "
                "formal years of experience."
            )
        })
    elif exp_score < 0.85:
        recs.append({
            'category': 'Experience',
            'priority': 'Medium',
            'message': "Slightly below the preferred experience range.",
            'action': (
                "Quantify achievements with specific metrics (e.g., 'Reduced "
                "server costs by 25%') to maximize the perceived impact of "
                "your experience."
            )
        })
    else:
        recs.append({
            'category': 'Strengths',
            'priority': 'Info',
            'message': (
                f"Your experience level ({candidate_years:.1f} years) meets "
                "or exceeds the requirement."
            ),
            'action': (
                "Present achievements with measurable business impact to "
                "further strengthen your profile."
            )
        })

    # =================================================================
    # DIMENSION 3: EDUCATION (Amin et al. 2019 – 20% weight)
    # =================================================================
    if edu_score < 0.50:
        recs.append({
            'category': 'Education',
            'priority': 'Medium',
            'message': (
                f"Education mismatch: {candidate_edu} vs. {required_edu} "
                "required. Your qualification level is significantly below "
                "the role requirement."
            ),
            'action': (
                "Highlight relevant certifications (e.g., AWS, Azure, Google), "
                "online courses (Coursera, edX), or ongoing studies that "
                "compensate for the formal education gap."
            )
        })
    elif edu_score < 0.80:
        recs.append({
            'category': 'Education',
            'priority': 'Medium',
            'message': (
                f"Education level ({candidate_edu}) is slightly below the "
                f"preferred qualification ({required_edu})."
            ),
            'action': (
                "List relevant industry certifications and specialized "
                "training to demonstrate equivalent competency."
            )
        })

    # =================================================================
    # DIMENSION 4: CONTENT RELEVANCE (Roy et al. 2020 – TF-IDF cosine)
    # =================================================================
    if text_sim < 0.20:
        recs.append({
            'category': 'Content Relevance',
            'priority': 'High',
            'message': (
                f"Low content relevance ({text_sim*100:.0f}%). Your resume "
                "language does not strongly align with the job description."
            ),
            'action': (
                "Incorporate key terms and phrases directly from the job "
                "description into your resume. Tailor your professional "
                "summary and experience descriptions to reflect the role's "
                "specific requirements and vocabulary."
            )
        })
    elif text_sim < 0.35:
        recs.append({
            'category': 'Content Relevance',
            'priority': 'Medium',
            'message': (
                f"Moderate content alignment ({text_sim*100:.0f}%). Consider "
                "closer tailoring to the job description."
            ),
            'action': (
                "Review the job description for domain-specific terminology "
                "and ensure your resume uses similar language in context."
            )
        })

    # =================================================================
    # DIMENSION 5: RESUME COMPLETENESS
    # (Weerasinghe et al. 2023 – missing content suggestion)
    # =================================================================
    if not section_completeness.get('has_summary', False):
        recs.append({
            'category': 'Resume Quality',
            'priority': 'High',
            'message': (
                "Missing section: Professional Summary. This is often the "
                "first section recruiters read."
            ),
            'action': (
                "Add a 2-3 sentence summary highlighting your years of "
                "experience, key technical strengths, and career focus. "
                "Example: 'Results-driven Software Engineer with X years "
                "of experience in [primary stack]...'"
            )
        })

    if not section_completeness.get('has_experience', False):
        recs.append({
            'category': 'Resume Quality',
            'priority': 'High',
            'message': (
                "Missing section: Work Experience. This is the most critical "
                "section for recruiters."
            ),
            'action': (
                "Add a Work Experience section with company names, job titles, "
                "dates of employment, and 2-4 bullet points of achievements "
                "per role, quantified with metrics where possible."
            )
        })
    elif section_completeness.get('has_experience') and candidate_years <= 0:
        recs.append({
            'category': 'Resume Quality',
            'priority': 'High',
            'message': (
                "Your Experience section is present but no date ranges were "
                "detected. Without timeframes, experience cannot be quantified."
            ),
            'action': (
                "Add start and end dates (e.g., 'Jan 2020 – Present') for "
                "each role. Use consistent formatting throughout."
            )
        })

    if not section_completeness.get('has_education', False):
        recs.append({
            'category': 'Resume Quality',
            'priority': 'High',
            'message': "Missing section: Education.",
            'action': (
                "Add an Education section listing your degree(s), institution "
                "name(s), and years of attendance."
            )
        })

    if not section_completeness.get('has_skills', False):
        recs.append({
            'category': 'Resume Quality',
            'priority': 'High',
            'message': "Missing section: Skills.",
            'action': (
                "Add a dedicated Skills section listing your technical "
                "competencies (languages, frameworks, tools, platforms). "
                "Group by category for readability."
            )
        })

    if not section_completeness.get('has_projects', False):
        recs.append({
            'category': 'Resume Quality',
            'priority': 'Medium',
            'message': (
                "Missing section: Projects. This is especially important for "
                "candidates with limited work experience."
            ),
            'action': (
                "Add 2-3 relevant projects with descriptions of technologies "
                "used, your specific contribution, and measurable outcomes."
            )
        })

    return recs


# =============================================================================
# MAIN MATCHING FUNCTION
# =============================================================================

def analyze_resume_job_fit(
        resume_result:             Dict[str, Any],
        job_result:                Dict[str, Any],
        weights:                   Optional[Dict[str, float]] = None,
        required_experience_years: Optional[float] = None,
        required_education_level:  Optional[str]   = None,
        required_skills:           Optional[set]   = None,
        preferred_skills:          Optional[set]   = None,
) -> Dict[str, Any]:
    w              = weights or DEFAULT_WEIGHTS
    total_w        = sum(w.values())
    norm_weights   = {k: v / total_w for k, v in w.items()}

    tfidf_resume = resume_result.get('tfidf_scores', {}) or {}
    tfidf_job    = job_result.get('tfidf_scores', {})    or {}
    text_sim     = cosine_similarity_tfidf(tfidf_resume, tfidf_job)

    if text_sim == 0.0:
        text_sim = cosine_similarity_tokens(
            resume_result.get('tokens', []) or [],
            job_result.get('tokens', [])    or []
        )

    candidate_skills = resume_result.get('extracted_skills', []) or []

    # ── Skill-match computation ────────────────────────────────────────────
    # Use required_skills from the real-world profile when provided;
    # otherwise fall back to job_result['extracted_skills'] so existing
    # callers (Streamlit UI, etc.) continue to work without changes.
    if required_skills is not None:
        _req_list = sorted(required_skills)
    else:
        _req_list = job_result.get('extracted_skills', []) or []

    _pref_set = set(preferred_skills) if preferred_skills else set()

    cand_set_lower = {s.lower().strip() for s in candidate_skills}
    req_set_lower  = {s.lower().strip() for s in _req_list}

    # Base score: fraction of required skills the candidate holds (0-100)
    if not req_set_lower:
        base_score = 100.0
    else:
        base_score = (len(cand_set_lower & req_set_lower) / len(req_set_lower)) * 100.0

    # Preferred-skill bonus: up to +20 percentage points
    if _pref_set and req_set_lower:
        pref_set_lower = {s.lower().strip() for s in _pref_set}
        bonus = (len(cand_set_lower & pref_set_lower) / len(pref_set_lower)) * 20.0
    else:
        bonus = 0.0

    skill_match_pct = min(base_score + bonus, 100.0)
    skill_score     = skill_match_pct / 100.0    # normalised 0-1 for weighting

    # matching / missing lists are always relative to required skills
    matching_skills = sorted(cand_set_lower & req_set_lower)
    missing_skills  = sorted(req_set_lower  - cand_set_lower)

    _total_required_skills = len(req_set_lower)

    candidate_years = float(resume_result.get('years_of_experience', 0.0) or 0.0)
    if required_experience_years is not None:
        job_years = float(required_experience_years)
    else:
        job_years = float(job_result.get('years_of_experience', 0.0) or 0.0)

    exp_score = experience_match_score(candidate_years, job_years)

    candidate_edu = resume_result.get('education_level', 'Unknown') or 'Unknown'
    if required_education_level is not None:
        job_edu = required_education_level
    else:
        job_edu = job_result.get('education_level', 'Unknown') or 'Unknown'

    edu_score = education_match_score(candidate_edu, job_edu)

    overall_score = (
        norm_weights['text_similarity']  * text_sim   +
        norm_weights['skill_match']      * skill_score +
        norm_weights['experience_match'] * exp_score   +
        norm_weights['education_match']  * edu_score
    ) * 100.0

    if overall_score >= 80.0:
        label    = 'Strong fit'
        priority = 'minor'
    elif overall_score >= 60.0:
        label    = 'Medium fit'
        priority = 'moderate'
    else:
        label    = 'Weak fit'
        priority = 'major'

    recommendations = generate_recommendations(
        skill_score        = skill_score,
        exp_score          = exp_score,
        edu_score          = edu_score,
        text_sim           = text_sim,
        missing_skills     = missing_skills,
        candidate_years    = candidate_years,
        required_years     = job_years,
        candidate_edu      = candidate_edu,
        required_edu       = job_edu,
        section_completeness = resume_result.get('section_completeness', {}),
        priority           = priority
    )

    return {
        'overall_score':       round(overall_score, 2),
        'label':               label,
        'component_scores': {
            'text_similarity':  round(text_sim,    3),
            'skill_match':      round(skill_score, 3),
            'experience_match': round(exp_score,   3),
            'education_match':  round(edu_score,   3),
        },
        'matching_skills':       matching_skills,
        'missing_skills':        missing_skills,
        'skill_match_percentage': round(skill_match_pct, 1),
        'recommendations':       recommendations,
        'metadata': {
            'candidate_years':      candidate_years,
            'required_years':       job_years,
            'candidate_education':  candidate_edu,
            'required_education':   job_edu,
            'total_candidate_skills': len(candidate_skills),
            'total_required_skills':  _total_required_skills,
            'date_ranges':          resume_result.get('date_ranges', []),
        }
    }


# =============================================================================
# BATCH RANKING
# =============================================================================

def rank_resumes_for_job(
        job_result:                Dict[str, Any],
        resume_results:            List[Dict[str, Any]],
        weights:                   Optional[Dict[str, float]] = None,
        required_experience_years: Optional[float] = None,
        required_education_level:  Optional[str]   = None,
        top_n:                     Optional[int]   = None,
        required_skills:           Optional[set]   = None,
        preferred_skills:          Optional[set]   = None,
) -> List[Dict[str, Any]]:
    ranked = []
    for idx, resume_result in enumerate(resume_results):
        if not resume_result or \
                resume_result.get('processing_status') == 'failed':
            continue
        analysis = analyze_resume_job_fit(
            resume_result,
            job_result,
            weights=weights,
            required_experience_years=required_experience_years,
            required_education_level=required_education_level,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
        )
        analysis['resume_index'] = idx
        analysis['resume_id']    = resume_result.get('resume_id', idx)
        ranked.append(analysis)
    ranked.sort(key=lambda x: x['overall_score'], reverse=True)
    return ranked[:top_n] if top_n is not None else ranked


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_score_interpretation(score: float) -> Dict[str, str]:
    if score >= 80:
        return {
            'level':          'Strong',
            'color':          'green',
            'description':    'Excellent match for this role.',
            'recommendation': 'Strong candidate — proceed to interview.'
        }
    if score >= 60:
        return {
            'level':          'Medium',
            'color':          'yellow',
            'description':    'Good potential with some gaps.',
            'recommendation': 'Review in detail — may be suitable with development.'
        }
    return {
        'level':          'Weak',
        'color':          'red',
        'description':    'Significant gaps in requirements.',
        'recommendation': 'Consider only if candidate shows exceptional other qualities.'
    }


def print_analysis_summary(analysis: Dict[str, Any],
                            resume_name: str = "Resume") -> None:
    sep = "─" * 70
    print(sep)
    print(f"  ANALYSIS: {resume_name}")
    print(sep)
    print(f"  Overall Score : {analysis['overall_score']:.1f}%  [{analysis['label']}]")

    print("\n  Component Scores:")
    for component, score in analysis['component_scores'].items():
        bar = '█' * int(score * 20) + '░' * (20 - int(score * 20))
        print(f"    {component:<20} {bar}  {score:.3f}")

    print(f"\n  Matching Skills ({len(analysis['matching_skills'])}):")
    if analysis['matching_skills']:
        for skill in analysis['matching_skills'][:10]:
            print(f"    ✓ {skill}")
        if len(analysis['matching_skills']) > 10:
            print(f"    ... and {len(analysis['matching_skills']) - 10} more")
    else:
        print("    None detected")

    print(f"\n  Missing Skills ({len(analysis['missing_skills'])}):")
    if analysis['missing_skills']:
        for skill in analysis['missing_skills'][:10]:
            print(f"    ✗ {skill}")
        if len(analysis['missing_skills']) > 10:
            print(f"    ... and {len(analysis['missing_skills']) - 10} more")
    else:
        print("    None")

    print(f"\n  Experience: {analysis['metadata']['candidate_years']:.1f} yrs"
          f" / Required: {analysis['metadata']['required_years']:.1f} yrs")

    if analysis['metadata'].get('date_ranges'):
        print("\n  Date Ranges (CRF extracted):")
        for dr in analysis['metadata']['date_ranges']:
            print(f"    {dr['start_str']} → {dr['end_str']}"
                  f"  ({dr['duration_years']} yrs)")

    print(f"\n  Recommendations ({len(analysis['recommendations'])}):")
    icons = {'High': '🔴', 'Medium': '🟡', 'Info': '🟢'}
    for rec in analysis['recommendations']:
        icon = icons.get(rec['priority'], '•')
        print(f"    {icon} [{rec['category']}] {rec['message']}")
        print(f"       → {rec['action']}")

    print(sep)