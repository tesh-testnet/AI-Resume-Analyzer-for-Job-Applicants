"""
Resume Suitability Classifier
AI-Based Resume Analyzer — KIC-HNDCSAI-251F (002, 003, 006, 020)

Implements the ML pipeline from Roy et al. (2020):
    TF-IDF (unigrams + bigrams) + LinearSVC for role classification

Also provides:
    - Level detection  (Amin et al. 2019 weighted scoring)
    - analyze_resume_for_role() — full pipeline integration function
"""

import os
import pickle
import sys
import numpy as np
from typing import Dict, Any, List, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import classification_report, accuracy_score
from sklearn.preprocessing import LabelEncoder

# ── Add core/ to path so imports work from any working directory ──────────
_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from resume_preprocessing_pipeline import ResumePreprocessor
from resume_job_matching_engine import (
    analyze_resume_job_fit,
    experience_match_score,
    education_match_score,
)
from job_role_database import (
    get_job_role_profile,
    get_job_description_text,
    JOB_LEVELS,
)

# ── Default absolute path for CRF model ───────────────────────────────────
_BASE_DIR = os.path.dirname(_CORE_DIR)
_DEFAULT_CRF_PATH = os.path.join(_BASE_DIR, "models", "crf_resume_ner.pkl")  # updated


# ============================================================
# 1.  PIPELINE BUILDERS  (unchanged)
# ============================================================

def build_svm_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            sublinear_tf=True, ngram_range=(1, 2), norm="l2",
            min_df=2, stop_words="english", max_features=15000,
        )),
        ("clf", LinearSVC(C=1.0, max_iter=3000, random_state=42)),
    ])


def build_logreg_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            sublinear_tf=True, ngram_range=(1, 2), norm="l2",
            min_df=2, stop_words="english", max_features=15000,
        )),
        ("clf", LogisticRegression(
            C=5.0, max_iter=1000, solver="saga",
            multi_class="multinomial", random_state=42,
        )),
    ])


# ============================================================
# 2.  ROLE CLASSIFIER  (unchanged)
# ============================================================

class RoleClassifier:
    def __init__(self, model_path: str = "models/role_classifier.pkl"):
        self.model_path    = model_path
        self.pipeline: Optional[Pipeline] = None
        self.label_encoder = LabelEncoder()
        self.is_trained    = False

    def train(
        self, resume_texts: List[str], labels: List[str],
        test_size: float = 0.2, use_logreg: bool = False,
    ) -> Dict[str, Any]:
        y = self.label_encoder.fit_transform(labels)
        X_train, X_test, y_train, y_test = train_test_split(
            resume_texts, y, test_size=test_size, random_state=42, stratify=y,
        )
        self.pipeline = build_logreg_pipeline() if use_logreg else build_svm_pipeline()
        self.pipeline.fit(X_train, y_train)
        self.is_trained = True
        y_pred = self.pipeline.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        report = classification_report(
            y_test, y_pred,
            target_names=self.label_encoder.classes_,
            output_dict=True,
        )
        cv = cross_val_score(self.pipeline, resume_texts, y, cv=10, scoring="accuracy")
        model_name = "Logistic Regression" if use_logreg else "Linear SVC"
        print(f"\n{'='*55}")
        print(f"  Role Classifier Training Complete")
        print(f"{'='*55}")
        print(f"  Model        : {model_name}")
        print(f"  Test Accuracy: {accuracy*100:.2f}%")
        print(f"  10-Fold CV   : {cv.mean()*100:.2f}% +/- {cv.std()*100:.2f}%")
        print(f"{'='*55}")
        print(classification_report(y_test, y_pred, target_names=self.label_encoder.classes_))
        self._save()
        return {
            "accuracy": float(accuracy),
            "cv_mean": float(cv.mean()),
            "cv_std": float(cv.std()),
            "classification_report": report,
        }

    def predict_role(self, resume_text: str) -> Dict[str, Any]:
        if not self.is_trained:
            raise RuntimeError("Classifier not trained. Call train() or load() first.")
        encoded = self.pipeline.predict([resume_text])[0]
        predicted_role = self.label_encoder.inverse_transform([encoded])[0]
        scores = self.pipeline.decision_function([resume_text])[0]
        exp_s = np.exp(scores - scores.max())
        proba = exp_s / exp_s.sum()
        top3 = [
            {
                "role": self.label_encoder.inverse_transform([i])[0],
                "confidence": round(float(proba[i]), 4),
            }
            for i in np.argsort(proba)[::-1][:3]
        ]
        return {
            "predicted_role": predicted_role,
            "confidence": round(float(proba[encoded]), 4),
            "top_3_predictions": top3,
            "matches_selected_role": None,
        }

    def _save(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.model_path)), exist_ok=True)
        with open(self.model_path, "wb") as f:
            pickle.dump({"pipeline": self.pipeline, "label_encoder": self.label_encoder}, f)
        print(f"  Model saved -> {self.model_path}")

    def load(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"No trained model found at '{self.model_path}'.\n"
                "Run scripts/train_classifier.py first."
            )
        with open(self.model_path, "rb") as f:
            saved = pickle.load(f)
        self.pipeline = saved["pipeline"]
        self.label_encoder = saved["label_encoder"]
        self.is_trained = True
        print(f"  Model loaded <- {self.model_path}")


# ============================================================
# 3.  LEVEL DETECTOR  (UPDATED – Amin et al. 2019 weights)
# ============================================================

def detect_suitable_level(
    years_experience: float,
    education_level:  str,
    job_role:         str,
    candidate_skills: List[str] = None,
) -> Dict[str, Any]:
    """
    Level recommendation using Amin et al. (2019) evidence‑based weights:
        Score = 0.50*Skills + 0.20*Education + 0.20*Experience + 0.10*Stability
    """
    if candidate_skills is None:
        candidate_skills = []

    candidate_skills_set = set(s.lower().strip() for s in candidate_skills)

    EDU_MAP = {"Unknown": 0, "Diploma": 1, "Bachelors": 2, "Masters": 3, "PhD": 4}
    cand_edu_val = EDU_MAP.get(education_level, 0)

    level_scores: Dict[str, float] = {}

    for level in JOB_LEVELS:
        lp = get_job_role_profile(job_role, level)

        # ── 1. Skills fit (50%) ────────────────────────────────
        required = [s.lower().strip() for s in lp.get("required_skills", [])]
        if required:
            skill_fit = len(candidate_skills_set & set(required)) / len(required)
        else:
            skill_fit = 1.0

        # ── 2. Experience fit (20%) ────────────────────────────
        required_years = lp.get("min_experience_years", 0)
        exp_fit = experience_match_score(years_experience, required_years)

        # ── 3. Education fit (20%) ─────────────────────────────
        required_edu = lp.get("required_education", "Bachelors")
        edu_fit = education_match_score(education_level, required_edu)

        # ── 4. Stability (10%) – placeholder ────────────────────
        stability_fit = 1.0   # to be replaced when companies are extracted

        level_score = (0.50 * skill_fit +
                       0.20 * exp_fit +
                       0.20 * edu_fit +
                       0.10 * stability_fit)

        level_scores[level] = round(level_score, 3)

    best_level = max(level_scores, key=lambda k: level_scores[k])

    return {
        "recommended_level":          best_level,
        "level_fit_scores":           level_scores,
        "candidate_experience_years": years_experience,
        "candidate_education":        education_level,
    }


# ============================================================
# 4.  MAIN ANALYSIS FUNCTION  (updated – CRF integration, no external extractor)
# ============================================================

def analyze_resume_for_role(
    resume_text:     str,
    selected_role:   str,
    selected_level:  str,
    role_classifier: Optional[RoleClassifier] = None,
    crf_model_path:  Optional[str]            = None,
) -> Dict[str, Any]:
    """
    Full pipeline: preprocess, classify, quantify fit, level recommendation.
    - `crf_model_path` is passed directly to ResumePreprocessor for
      CRF‑backed experience extraction.
    """
    resolved_crf_path = crf_model_path or _DEFAULT_CRF_PATH

    # ── Step 1 — preprocess resume WITH CRF model ─────────────────
    # Corrected: use crf_model_path keyword argument
    preprocessor  = ResumePreprocessor(crf_model_path=resolved_crf_path)
    resume_result = preprocessor.process(resume_text)

    # ── Step 2 & 3 — build + preprocess job description ───────────
    job_profile  = get_job_role_profile(selected_role, selected_level)
    job_doc_text = get_job_description_text(selected_role, selected_level)
    job_result   = preprocessor.process(job_doc_text)

    # ── Step 4 — ML role prediction (optional) ────────────────────
    role_prediction = None
    if role_classifier and role_classifier.is_trained:
        try:
            role_prediction = role_classifier.predict_role(resume_text)
            role_prediction["matches_selected_role"] = (
                role_prediction["predicted_role"].strip().lower()
                == selected_role.strip().lower()
            )
        except Exception:
            role_prediction = None

    # ── Step 5 — suitability scoring ──────────────────────────────
    fit_analysis = analyze_resume_job_fit(
        resume_result=resume_result,
        job_result=job_result,
        required_experience_years=float(job_profile["min_experience_years"]),
        required_education_level=job_profile["required_education"],
    )

    # ── Step 6 — resolve candidate experience (already computed by preprocessor) ──
    candidate_exp = float(resume_result.get("years_of_experience") or 0)
    candidate_edu = resume_result.get("education_level") or "Unknown"
    candidate_skills = resume_result.get("extracted_skills", [])

    # The preprocessor already used the CRF internally (if loaded) to extract
    # the experience block and sum years. No need for a separate fallback.
    # If the CRF was not loaded, the preprocessor's regex fallback was used.

    # ── Step 7 — level recommendation (now with skills) ───────────
    level_analysis = detect_suitable_level(
        years_experience=candidate_exp,
        education_level=candidate_edu,
        job_role=selected_role,
        candidate_skills=candidate_skills,
    )

    # ── Step 8 — compile final report ─────────────────────────────
    return {
        "selected_role":          selected_role,
        "selected_level":         selected_level,
        "overall_score":          fit_analysis["overall_score"],
        "fit_label":              fit_analysis["label"],
        "component_scores":       fit_analysis["component_scores"],
        "matching_skills":        fit_analysis["matching_skills"],
        "missing_skills":         fit_analysis["missing_skills"],
        "skill_match_percentage": fit_analysis["skill_match_percentage"],
        "recommendations":        fit_analysis["recommendations"],
        "role_prediction":        role_prediction,
        "level_recommendation":   level_analysis,
        "candidate_profile": {
            "education":            candidate_edu,
            "experience_years":     candidate_exp,
            "detected_skills":      candidate_skills,
            "contact_info":         resume_result.get("contact_info") or {},
            "section_completeness": resume_result.get("section_completeness") or {},
        },
        "job_requirements": {
            "required_skills":      job_profile["required_skills"],
            "preferred_skills":     job_profile["preferred_skills"],
            "min_experience_years": job_profile["min_experience_years"],
            "required_education":   job_profile["required_education"],
            "role_description":     job_profile["role_description"],
        },
    }


# ============================================================
# 5.  KAGGLE DATASET LOADER  (unchanged)
# ============================================================

def load_kaggle_dataset(csv_path: str) -> Tuple[List[str], List[str]]:
    import pandas as pd
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Dataset not found at: {csv_path}\n"
            "Download 'UpdatedResumeDataSet.csv' and place it in data/"
        )
    df = pd.read_csv(csv_path)
    col_lower = {c.lower(): c for c in df.columns}
    print(f"\nColumns : {list(df.columns)}")
    print(f"Shape   : {df.shape}")
    text_col = None
    for key in ["resume_str", "resume", "text", "resume_text", "cv", "content"]:
        if key in col_lower:
            text_col = col_lower[key]
            break
    label_col = None
    for key in ["category", "label", "role", "domain", "job_title", "job_category"]:
        if key in col_lower:
            label_col = col_lower[key]
            break
    if text_col is None or label_col is None:
        raise ValueError(
            f"Could not detect required columns.\n"
            f"Found: {list(df.columns)}\n"
            f"text_col: {text_col}  label_col: {label_col}"
        )
    print(f"\n  Text column  -> '{text_col}'")
    print(f"  Label column -> '{label_col}'")
    df = df.dropna(subset=[text_col, label_col])
    df[text_col]  = df[text_col].astype(str).str.strip()
    df[label_col] = df[label_col].astype(str).str.strip()
    df = df[df[text_col].str.len() > 50]
    print(f"\nDataset ready : {len(df)} resumes | {df[label_col].nunique()} categories")
    print(df[label_col].value_counts().to_string())
    return df[text_col].tolist(), df[label_col].tolist()