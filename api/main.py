"""
FastAPI backend for the AI Resume Analyzer.
Reuses the existing core pipeline without modification.
Serves static frontend files from /static and root.
"""

import os
import sys
import subprocess
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Ensure the project root is on sys.path so that "core" is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.resume_parser import extract_text_from_bytes
from core.resume_suitability_classifier import (
    RoleClassifier,
    analyze_resume_for_role,
)
from core.job_role_database import list_roles, JOB_LEVELS
from core.resume_preprocessing_pipeline import (
    ResumePreprocessor,
    compare_resumes_similarity,
)

# Import the JD parser for advanced field extraction
from core.jd_parser import extract_job_requirements

# ── configurable model paths ────────────────────────────────────────────
SECTION_CRF_PATH = PROJECT_ROOT / "models" / "crf_resume_ner.pkl"
SKILLS_CRF_PATH  = PROJECT_ROOT / "models" / "crf_skills_v2.pkl"
CLASSIFIER_PATH  = PROJECT_ROOT / "models" / "role_classifier.pkl"

# ── FastAPI app ─────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Resume Analyzer API",
    version="1.0.0",
    description="Analyse resumes against real‑world job profiles",
)

# ── CORS (allow any origin for development; restrict in production) ─────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Serve static frontend files ─────────────────────────────────────────
STATIC_DIR = PROJECT_ROOT / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    # Also support being served under a subpath (e.g. /ai-resume-analyzer/static)
    app.mount("/ai-resume-analyzer/static", StaticFiles(directory=str(STATIC_DIR)), name="static_subpath")
else:
    print("⚠️  Warning: static/ folder not found. Frontend files will not be served.")

@app.get("/", response_class=FileResponse)
async def serve_index():
    """Serve the main homepage (index.html)."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found in static/")
    return FileResponse(index_path)

@app.get("/login", response_class=FileResponse)
async def serve_login():
    login_path = STATIC_DIR / "login.html"
    if not login_path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(login_path)

@app.get("/analyzer", response_class=FileResponse)
async def serve_analyzer():
    analyzer_path = STATIC_DIR / "analyzer.html"
    if not analyzer_path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(analyzer_path)


# Support analyzer page when app is served under a subpath (e.g. /ai-resume-analyzer/analyzer)
@app.get("/ai-resume-analyzer/analyzer", response_class=FileResponse)
async def serve_analyzer_subpath():
    analyzer_path = STATIC_DIR / "analyzer.html"
    if not analyzer_path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(analyzer_path)


# Serve analyzer.html for common static link names so buttons work from any base path
@app.get("/analyzer.html", response_class=FileResponse)
async def serve_analyzer_html():
    analyzer_path = STATIC_DIR / "analyzer.html"
    if not analyzer_path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(analyzer_path)


@app.get("/resume-analyzer-final.html", response_class=FileResponse)
async def serve_resume_analyzer_final_html():
    analyzer_path = STATIC_DIR / "analyzer.html"
    if not analyzer_path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(analyzer_path)


@app.get("/ai-resume-analyzer/resume-analyzer-final.html", response_class=FileResponse)
async def serve_resume_analyzer_final_subpath():
    analyzer_path = STATIC_DIR / "analyzer.html"
    if not analyzer_path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(analyzer_path)

# ── load the role classifier once at startup ─────────────────────────────
classifier = RoleClassifier(model_path=str(CLASSIFIER_PATH))
try:
    classifier.load()
except FileNotFoundError:
    print("⚠️  Role classifier not found – role prediction will be skipped.")

@app.on_event("startup")
async def startup_event():
    print("🚀 FastAPI server started.")
    print(f"   Serving static files from: {STATIC_DIR}")
    print(f"   Frontend available at: http://localhost:8000/")

# ── Helper to rebuild profiles (optional) ─────────────────────────────────
@app.post("/rebuild-profiles", tags=["admin"])
async def rebuild_profiles():
    """Rebuild data/real_job_profiles.json from raw JD files."""
    try:
        result = subprocess.run(
            ["python", str(PROJECT_ROOT / "scripts" / "build_real_job_profiles.py")],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=300,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr)
        return JSONResponse(
            content={"message": "Profiles rebuilt successfully", "output": result.stdout}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Main analysis endpoint ───────────────────────────────────────────────
@app.post("/analyze", tags=["analysis"])
async def analyze_resume(
    file: UploadFile = File(..., description="Resume file (PDF, DOCX, or TXT)"),
    role: str = Form(..., description="Target job role"),
    level: str = Form(..., description="Experience level (Entry / Mid / Senior)"),
):
    """
    Upload a resume and get a full suitability analysis.
    Returns the same result dictionary that the Streamlit UI consumes.
    """
    if role not in list_roles():
        raise HTTPException(status_code=400, detail=f"Unknown role: {role}")
    if level not in JOB_LEVELS:
        raise HTTPException(status_code=400, detail=f"Invalid level: {level}")

    try:
        contents = await file.read()
        resume_text = extract_text_from_bytes(contents, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not extract text: {e}")

    if len(resume_text.strip()) < 50:
        raise HTTPException(status_code=400, detail="Extracted text is too short.")

    try:
        result = analyze_resume_for_role(
            resume_text=resume_text,
            selected_role=role,
            selected_level=level,
            role_classifier=classifier,
            crf_model_path=str(SECTION_CRF_PATH),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    return JSONResponse(content=result)

# ── NEW: Resume vs Custom Job Description comparison (ADVANCED) ─────────
@app.post("/compare-job-description", tags=["analysis"])
async def compare_job_description(
    file: UploadFile = File(..., description="Resume file (PDF, DOCX, or TXT)"),
    jd_text: str = Form(..., description="Full text of the job description to compare against"),
):
    """
    Compare a resume directly against a free‑text job description.
    Returns similarity score, skill comparison, and extracted JD requirements.
    """
    # 1. Extract resume text
    try:
        contents = await file.read()
        resume_text = extract_text_from_bytes(contents, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not extract resume text: {e}")

    if len(resume_text.strip()) < 50:
        raise HTTPException(status_code=400, detail="Extracted resume text is too short.")

    if len(jd_text.strip()) < 20:
        raise HTTPException(status_code=400, detail="Job description text is too short.")

    # 2. Instantiate preprocessor with skills CRF for consistent skill extraction
    preprocessor = ResumePreprocessor(
        crf_skills_model_path=str(SKILLS_CRF_PATH)
    )

    # 3. Tokenise both texts for cosine similarity
    resume_tokens = preprocessor.tokenize(preprocessor.normalize_text(resume_text))
    resume_tokens_filtered = preprocessor.remove_stopwords(resume_tokens)

    jd_tokens = preprocessor.tokenize(preprocessor.normalize_text(jd_text))
    jd_tokens_filtered = preprocessor.remove_stopwords(jd_tokens)

    # 4. Cosine similarity (token vectors) -> percentage
    similarity_score = compare_resumes_similarity(
        resume_tokens_filtered, jd_tokens_filtered
    ) * 100

    # 5. Skill extraction (rule‑based + CRF)
    resume_skills = set(preprocessor.extract_skills(resume_text))
    jd_skills = set(preprocessor.extract_skills(jd_text))

    matching_skills = resume_skills & jd_skills
    missing_in_resume = jd_skills - resume_skills
    extra_in_resume = resume_skills - jd_skills

    # 6. Extract advanced job requirements from JD
    jd_requirements = extract_job_requirements(jd_text)

    # 7. Build response with all fields
    return JSONResponse(content={
        "similarity_score": round(similarity_score, 1),
        "matching_skills": sorted(list(matching_skills)),
        "missing_in_resume": sorted(list(missing_in_resume)),
        "extra_in_resume": sorted(list(extra_in_resume)),
        "total_resume_skills": len(resume_skills),
        "total_jd_skills": len(jd_skills),
        # Advanced fields extracted from JD
        "job_title": jd_requirements["job_title"],
        "required_education": jd_requirements["required_education"],
        "required_experience_years": jd_requirements["required_experience_years"],
        "salary_range": jd_requirements["salary_range"],
    })

# ── NEW: Endpoint to list all available job roles (for dynamic frontend) ──
@app.get("/roles", tags=["info"])
async def get_available_roles():
    """
    Return the list of all job roles that have profile data.
    This is used by the frontend to populate the role dropdown dynamically.
    """
    return list_roles()

# ── Health check ─────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}

# ── Run with: uvicorn api.main:app --reload ──────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)