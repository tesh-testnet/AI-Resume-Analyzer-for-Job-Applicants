# ResumeAI — AI-Powered Resume Analyzer

ResumeAI is a full-stack web application that helps IT job seekers evaluate how well their resume matches a target job role or custom job description.

The system uses a custom-trained **Conditional Random Fields (CRF) Named Entity Recognition (NER) model** for extracting skills and experience, **TF-IDF vectorization** and **cosine similarity** for content relevance analysis, and a weighted scoring mechanism to generate a detailed resume-job fit report.

> **No Large Language Models (LLMs). No black boxes.** Every component is built from scratch and fully explainable.

---

## ✨ Features

### Role-Based Analysis
Compare your resume against predefined job profiles:

- Software Engineer
- Data Scientist
- Software Quality Assurance Engineer

Each role supports:

- Entry Level
- Mid Level
- Senior Level

### Custom Job Description Analysis

- Paste any job description.
- Receive a similarity score.
- Identify missing skills and qualifications.
- Get personalized improvement suggestions.

### Advanced Job Description Extraction

Automatically extracts:

- Job title
- Required education level
- Required years of experience
- Required and preferred skills

### Smart Scoring System

Weighted evaluation based on:

| Component | Weight |
|------------|----------|
| Text Similarity | 30% |
| Skill Match | 40% |
| Experience Match | 20% |
| Education Match | 10% |

### Interactive Results Dashboard

- Circular score indicator
- Component-wise score breakdown
- Matching and missing skill chips
- Candidate level recommendation
- Resume completeness checklist
- Prioritized improvement recommendations

### User Authentication

Powered by Firebase Authentication and Firestore:

- Anonymous users: 2 free analyses
- Registered users: Unlimited analyses

### Responsive Design

Optimized for:

- Desktop
- Tablet
- Mobile devices

### Theme Support

- Light Mode
- Dark Mode
- System preference detection

---

## 🛠️ Technology Stack

| Layer | Technology |
|---------|-------------|
| Backend | FastAPI (Python) |
| Frontend | HTML, CSS, JavaScript |
| Machine Learning | scikit-learn, sklearn-crfsuite, NumPy |
| Resume Parsing | PyMuPDF, python-docx |
| Authentication | Firebase Authentication |
| Database | Firestore |
| Deployment | Render |

### Machine Learning Components

- CRF-based Resume NER Model
- CRF-based Skill Extraction Model
- Role Classification Model
- TF-IDF Vectorization
- Cosine Similarity Matching
- Rule-Based Experience Extraction
- Rule-Based Education Extraction

> All machine learning models were custom-trained using manually annotated Sri Lankan IT resumes.

---

## 📂 Project Structure

```text
resume-ai/
├── api/
│   └── main.py
│
├── core/
│   ├── resume_parser.py
│   ├── resume_preprocessing_pipeline.py
│   ├── resume_job_matching_engine.py
│   ├── job_role_database.py
│   ├── jd_parser.py
│   └── ...
│
├── models/
│   ├── crf_resume_ner.pkl
│   ├── crf_skills_v2.pkl
│   └── role_classifier.pkl
│
├── data/
│   └── real_job_profiles.json
│
├── static/
│   ├── index.html
│   ├── analyzer.html
│   ├── auth.html
│   ├── analyzer.css
│   ├── analyzer.js
│   ├── usage-limit.js
│   ├── style.css
│   ├── script.js
│   ├── auth.css
│   └── auth.js
│
├── requirements.txt
├── Procfile
└── README.md
```

---

## 🚀 Local Development Setup

### Prerequisites

- Python 3.10 or later
- Git
- Firebase Project (optional)

---

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/resume-ai.git
cd resume-ai
```

---

### 2. Create a Virtual Environment

#### Linux / macOS

```bash
python -m venv venv
source venv/bin/activate
```

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Start the Backend Server

```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Backend URL:

```text
http://127.0.0.1:8000
```

---

### 5. Serve the Frontend

```bash
cd static
python -m http.server 5500
```

Open:

```text
http://127.0.0.1:5500/analyzer.html
```

> The frontend expects the backend API at `http://127.0.0.1:8000`. Update the `API_BASE` variable in `analyzer.js` if required.

---

## ☁️ Deployment on Render

### Build Settings

| Field | Value |
|---------|---------|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` |

### Deployment Steps

1. Push the project to GitHub.
2. Create a new Web Service in Render.
3. Connect your repository.
4. Configure the build settings above.
5. Deploy.

Example URLs:

```text
https://resume-ai.onrender.com/static/index.html
https://resume-ai.onrender.com/static/analyzer.html
```

### Firebase Configuration

Add your Render domain to:

```text
Firebase Console
→ Authentication
→ Settings
→ Authorized Domains
```

---

## 🔐 Usage Limits

| User Type | Usage Limit |
|------------|-------------|
| Anonymous User | 2 Analyses |
| Registered User | Unlimited |

Anonymous usage is stored in browser `localStorage`.

When the limit is reached:

- A notification banner is displayed.
- Users are prompted to sign in.
- Unlimited access becomes available after authentication.

---

## 📝 Scoring Methodology

The final score is calculated using a weighted combination of four normalized metrics:

```text
overall_score =
    (0.30 × text_similarity)
  + (0.40 × skill_match)
  + (0.20 × experience_match)
  + (0.10 × education_match)
```

### 1. Text Similarity

Calculated using:

- TF-IDF Vectorization
- Cosine Similarity

The resume is compared against the role-specific job document.

### 2. Skill Match

Measures:

- Required skill coverage
- Preferred skill coverage

Preferred skills provide a bonus contribution, capped at 100%.

### 3. Experience Match

Compares:

```text
Candidate Years of Experience
vs
Required Years of Experience
```

Includes tolerance for near matches.

### 4. Education Match

Uses an ordinal ranking:

```text
Diploma
  ↓
Bachelor's Degree
  ↓
Master's Degree
  ↓
PhD
```

The final output includes:

- Overall Fit Score
- Matching Skills
- Missing Skills
- Experience Evaluation
- Education Evaluation
- Improvement Recommendations

---

## 📊 Research Foundation

The ResumeAI scoring framework is inspired by the following research:

1. Amin et al. (2019)
   - Weighted resume-job matching methodology

2. Roy et al. (2020)
   - TF-IDF and cosine similarity for relevance analysis

3. Weerasinghe et al. (2023)
   - Missing content detection and recommendation generation

---

## 🤝 Contributing

Contributions are welcome.

### Steps

```bash
# Fork the repository

# Create a feature branch
git checkout -b feature/new-feature

# Commit changes
git commit -m "Add new feature"

# Push changes
git push origin feature/new-feature
```

Then open a Pull Request.

---

## 📄 License

This project is licensed under the MIT License.

See the `LICENSE` file for details.

---

## 👨‍💻 Authors

KIC-HNDCSAI-251F

- 002
- 003
- 006
- 020

---

## 🙏 Acknowledgements

Special thanks to:

- scikit-learn
- sklearn-crfsuite
- NumPy
- FastAPI
- Firebase
- PyMuPDF
- python-docx

for providing the tools that made this project possible.# AI-Resume-Analyzer-for-Job-Applicants
