"""
Resume Preprocessing Pipeline
AI-Based Resume Analyzer for Job Applicants

This module implements the preprocessing pipeline as specified in the project presentation:
1. Text Preprocessing (Tokenization, Stop-word Removal, Text Normalization)
2. Feature Extraction (Keyword Extraction, TF-IDF)
3. Section Parsing and Skill Extraction
4. Experience extraction powered by a CRF‑NER model (B‑EXP / I‑EXP)
5. Skill extraction powered by a CRF skills model (B‑SKILL / I‑SKILL)
"""

import os
import re
import sys
import difflib
import joblib
import numpy as np
from collections import Counter
from typing import Dict, List, Tuple, Any, Optional


class ResumePreprocessor:
    

    def __init__(
        self,
        custom_skills: Optional[List[str]] = None,
        crf_model_path: Optional[str] = None,        # path to trained CRF section model
        crf_skills_model_path: Optional[str] = None, # path to trained CRF skills model
    ):
        self.stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'been', 'by', 'for',
            'from', 'has', 'have', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
            'that', 'the', 'to', 'was', 'were', 'will', 'with', 'this',
            'but', 'they', 'can', 'had', 'or', 'which', 'who', 'their', 'them'
        }

        self.technical_skills = {
            'python', 'java', 'javascript', 'c++', 'c#', 'ruby', 'php', 'swift',
            'kotlin', 'go', 'rust', 'scala', 'r', 'matlab', 'typescript', 'perl',
            'django', 'flask', 'react', 'angular', 'vue', 'node', 'express',
            'spring', 'laravel', 'rails', 'fastapi', 'nextjs', 'gatsby',
            'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'pandas',
            'numpy', 'opencv', 'nltk', 'spacy', 'transformers', 'hugging face',
            'mysql', 'postgresql', 'mongodb', 'oracle', 'redis', 'cassandra',
            'dynamodb', 'elasticsearch', 'sqlite', 'mariadb', 'neo4j',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'git',
            'terraform', 'ansible', 'ci/cd', 'linux', 'unix', 'gitlab', 'circleci',
            'machine learning', 'deep learning', 'nlp', 'computer vision',
            'data science', 'data analysis', 'big data', 'hadoop', 'spark',
            'tableau', 'power bi', 'statistics', 'data mining',
            'agile', 'scrum', 'kanban', 'devops', 'microservices', 'rest api',
            'graphql', 'tdd', 'blockchain', 'api', 'oauth',
        }

        if custom_skills:
            self.technical_skills.update(skill.lower() for skill in custom_skills)

        # Build skill vocabulary (aliases, multi-word forms)
        self._build_skill_vocabulary()

        # ─── CRF section model loading ─────────────────────────────────────
        self.crf_model = None
        if crf_model_path and os.path.exists(crf_model_path):
            try:
                self.crf_model = joblib.load(crf_model_path)
                print(f"CRF section model loaded from {crf_model_path}")
            except Exception as e:
                print(f"Warning: Could not load CRF model ({e})")
        elif crf_model_path:
            print(f"Warning: CRF model file not found: {crf_model_path}")

        # ─── CRF skills model loading ──────────────────────────────────────
        self.crf_skills_model = None
        if crf_skills_model_path and os.path.exists(crf_skills_model_path):
            try:
                self.crf_skills_model = joblib.load(crf_skills_model_path)
                print(f"CRF skills model loaded from {crf_skills_model_path}")
            except Exception as e:
                print(f"Warning: Could not load CRF skills model ({e})")
        elif crf_skills_model_path:
            print(f"Warning: CRF skills model file not found: {crf_skills_model_path}")

        # Section detection patterns (used for section extraction and fallback)
        self.section_patterns = {
            'summary':        r'(professional\s+summary|career\s+summary|summary|objective|profile|about\s+me)',
            'experience':     r'(work\s+experience|professional\s+experience|employment\s+history|work\s+history|experience)',
            'education':      r'(education|academic\s+background|qualifications|academic\s+qualifications)',
            'skills':         r'(technical\s+skills|key\s+skills|core\s+skills|skills|competencies|expertise|proficiencies)',
            'projects':       r'(academic\s+projects|personal\s+projects|key\s+projects|project\s+experience|projects)',
            'certifications': r'(certifications|certificates|professional\s+development|licenses)',
            'achievements':   r'(achievements|awards|accomplishments|honors|recognition)',
            'publications':   r'(publications|research\s+papers|papers|articles)',
            'interests':      r'(research\s+interests|interests|hobbies)',
            'languages':      r'(languages|language\s+skills)',
            'references':     r'(references|referees|referrals)',
        }

        self._section_order = [
            'publications', 'projects', 'certifications', 'achievements',
            'interests', 'languages', 'references', 'experience',
            'skills', 'summary', 'education',
        ]

        self.document_frequency = {}
        self.total_documents = 0

    # ──────────────────────── Skill vocabulary builder ────────────────────────

    def _build_skill_vocabulary(self):
        """
        Build a canonical skill map including original technical_skills,
        all skills from job_role_database (if importable), and manual aliases.
        JOB_ROLES_DB removed — uses get_job_role_profile-based DB only if available.
        """
        canonical_skills = set(self.technical_skills)

        # Try to load skills from the job role database (new API, no JOB_ROLES_DB)
        try:
            from job_role_database import JOB_LEVELS, get_job_role_profile
            import job_role_database as _jrdb
            for role in getattr(_jrdb, '_ROLE_NAMES', []):
                for level in JOB_LEVELS:
                    try:
                        profile = get_job_role_profile(role, level)
                        for skill in profile.get('required_skills', []):
                            canonical_skills.add(skill.lower().strip())
                        for skill in profile.get('preferred_skills', []):
                            canonical_skills.add(skill.lower().strip())
                    except Exception:
                        pass
        except ImportError:
            pass

        self.skill_surface_to_canonical = {}
        for skill in canonical_skills:
            canon = skill.lower().strip().rstrip('.')
            base_forms = self._generate_skill_variants(canon)
            for form in base_forms:
                self.skill_surface_to_canonical[form] = canon

        manual_aliases = {
            # ── Standard surface-form aliases ────────────────────────────────
            # Placeholder tokens are appended here so each canonical skill has
            # exactly one entry; _rule_based_extract_skills injects these tokens
            # before the regex runs, allowing the n-gram loop to find them.
            "nodejs":     ["node.js", "node js", "node", "nodejsholder"],
            "reactjs":    ["react.js", "react js", "react", "reactjsholder"],
            "angular":    ["angular.js", "angularjs", "angularjsholder"],
            "vue":        ["vuejsholder"],
            "express":    ["expressjsholder"],
            "nextjs":     ["nextjsholder"],
            "javascript": ["js"],
            "amazon web services":  ["aws"],
            "google cloud platform": ["gcp", "gcp cloud"],
            "machine learning":          ["ml"],
            "natural language processing": ["nlp"],
            "rest api": ["restful api", "rest"],
            "ci cd":    ["ci/cd", "cicd"],
            # Explicit entries ensure html and css are always in the mapping
            # regardless of how _generate_skill_variants processes them.
            "html": ["html5", "html 5"],
            "css":  ["css3", "css 3"],
            # ── Special-character skill placeholders ─────────────────────────
            "c#":      ["csharpholder"],
            "c++":     ["cplusplusholder"],
            "f#":      ["fsharpholder"],
            ".net":    ["dotnetholder"],
            "asp.net": ["aspdotnetholder"],
            "vb.net":  ["vbdotnetholder"],
        }

        for canon, aliases in manual_aliases.items():
            self.skill_surface_to_canonical[canon] = canon
            for alias in aliases:
                self.skill_surface_to_canonical[alias] = canon

        self.single_word_skills = {s for s in canonical_skills if ' ' not in s}

    @staticmethod
    def _generate_skill_variants(canon):
        """Generate common typographic variations of a skill name."""
        variants = set()
        clean = re.sub(r'[.\-]', ' ', canon).strip()
        variants.add(canon)
        variants.add(clean)
        variants.add(clean.replace(' ', ''))
        if ' ' in clean:
            variants.add(clean.replace(' ', '-'))
        return variants

    # ──────────────────────── Skill placeholder table ─────────────────────────

    # Ordered list of (regex-pattern, placeholder) pairs used by
    # _rule_based_extract_skills to protect special-character skill tokens
    # before the regex tokeniser runs. Longer/more-specific patterns must
    # come first so that e.g. "ASP.NET" is replaced before ".NET".
    _SKILL_PLACEHOLDERS = [
        # pattern (case-insensitive)                  placeholder token
        (r'(?<![\w])ASP\.NET(?![\w])',             'aspdotnetholder'),
        (r'(?<![\w])VB\.NET(?![\w])',              'vbdotnetholder'),
        (r'(?<![\w])\.NET(?![\w])',               'dotnetholder'),
        (r'(?<![\w])C\+\+(?![\w])',              'cplusplusholder'),
        (r'(?<![\w])C#(?![\w])',                   'csharpholder'),
        (r'(?<![\w])F#(?![\w])',                   'fsharpholder'),
        (r'(?i)Node\.js(?![\w])',                  'nodejsholder'),
        (r'(?i)React\.js(?![\w])',                 'reactjsholder'),
        (r'(?i)Angular\.js(?![\w])',               'angularjsholder'),
        (r'(?i)Vue\.js(?![\w])',                   'vuejsholder'),
        (r'(?i)Express\.js(?![\w])',               'expressjsholder'),
        (r'(?i)Next\.js(?![\w])',                  'nextjsholder'),
    ]

    # ──────────────────────── Rule-based skill extraction ─────────────────────

    def _rule_based_extract_skills(self, text: str) -> List[str]:
        """
        Rule-based skill extraction using n-grams, expanded vocabulary,
        and fuzzy matching for typos. Called internally by extract_skills().

        Special-character skills (C#, .NET, Node.js, etc.) are replaced with
        alphanumeric placeholder tokens before lowercasing/regex processing so
        the n-gram loop can match them via manual_aliases in skill_surface_to_canonical.
        The canonical_tokenise path (used by both CRF models) is NOT modified.
        """
        # ── Step 0: replace special-character skill tokens with placeholders ──
        working = text
        for pattern, placeholder in self._SKILL_PLACEHOLDERS:
            working = re.sub(pattern, placeholder, working, flags=re.IGNORECASE)

        text_lower = working.lower()
        words    = re.findall(r'\b[a-z0-9+#]+\b', text_lower)
        bigrams  = [' '.join(words[i:i+2]) for i in range(len(words)-1)]
        trigrams = [' '.join(words[i:i+3]) for i in range(len(words)-2)]

        found_canonical = set()

        # 1. Exact match of n-grams against surface forms
        for ngram in words + bigrams + trigrams:
            if ngram in self.skill_surface_to_canonical:
                found_canonical.add(self.skill_surface_to_canonical[ngram])

        # 2. Fuzzy fallback for single words not yet matched
        for word in words:
            if word in self.skill_surface_to_canonical or len(word) < 3:
                continue
            best_score = 0.0
            best_skill = None
            for skill in self.single_word_skills:
                if abs(len(word) - len(skill)) > 2:
                    continue
                ratio = difflib.SequenceMatcher(None, word, skill).ratio()
                if ratio > best_score:
                    best_score = ratio
                    best_skill = skill
            if best_skill and best_score >= 0.88:
                found_canonical.add(best_skill)

        return sorted(list(found_canonical))

    # ──────────────────────── CRF skill extraction ────────────────────────────

    def _extract_skills_crf(self, text: str) -> List[str]:
        """
        CRF-based skill extraction.

        Tokenises the full text with canonical_tokenise(), builds token
        features with _token_features(), runs the skills CRF model, then
        reconstructs B-SKILL / I-SKILL spans and maps them to canonical
        names via skill_surface_to_canonical. Spans with no canonical
        mapping are silently discarded.

        Returns a list of canonical skill strings.
        """
        if self.crf_skills_model is None:
            return []

        try:
            words = self.canonical_tokenise(text)
            if not words:
                return []

            X_seq = [self._token_features(words, i) for i in range(len(words))]
            tags  = self.crf_skills_model.predict([X_seq])[0]

            # Reconstruct contiguous B-SKILL / I-SKILL spans
            spans: List[str] = []
            current_span: List[str] = []
            for token, tag in zip(words, tags):
                if tag == "B-SKILL":
                    if current_span:
                        spans.append(" ".join(current_span))
                    current_span = [token]
                elif tag == "I-SKILL" and current_span:
                    current_span.append(token)
                else:
                    if current_span:
                        spans.append(" ".join(current_span))
                    current_span = []
            if current_span:
                spans.append(" ".join(current_span))

            # Map spans to canonical names
            canonical: List[str] = []
            for span in spans:
                key = span.lower().strip()
                if key in self.skill_surface_to_canonical:
                    canonical.append(self.skill_surface_to_canonical[key])

            return canonical

        except Exception as e:
            print(f"CRF skills extraction failed: {e}")
            return []

    # ──────────────────────── Public extract_skills entry point ───────────────

    def extract_skills(self, text: str) -> List[str]:
        """
        Primary skill extraction entry point.

        Always runs the rule-based extractor. When a CRF skills model is
        loaded (self.crf_skills_model is not None), it also runs the CRF
        extractor and merges the results (union). No extra flags needed —
        loading the model is sufficient to activate it.

        Returns a sorted list of unique canonical skill names.
        """
        found: set = set(self._rule_based_extract_skills(text))

        if self.crf_skills_model is not None:
            found |= set(self._extract_skills_crf(text))

        return sorted(found)

    # ==================== CORE PROCESSING STEPS ==============================

    def validate_resume_text(self, text: str) -> str:
        if not text or not isinstance(text, str):
            raise ValueError("Resume text must be a non-empty string")
        text = text.strip()
        if len(text) < 50:
            raise ValueError("Resume text is too short (minimum 50 characters)")
        return text

    def normalize_text(self, text: str) -> str:
        text = re.sub(r'http\S+|www\.\S+', '', text)
        text = re.sub(r'\S+@\S+', '', text)
        text = re.sub(r'\+?[\d\s\-\(\)]{10,}', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.lower().strip()

    def tokenize(self, text: str) -> List[str]:
        return re.findall(r'\b[a-zA-Z]+\b', text)

    def remove_stopwords(self, tokens: List[str]) -> List[str]:
        return [t for t in tokens if t.lower() not in self.stop_words]

    def extract_keywords(self, tokens: List[str], top_n: int = 20) -> List[Tuple[str, int]]:
        return Counter(tokens).most_common(top_n)

    def calculate_tf(self, tokens: List[str]) -> Dict[str, float]:
        token_counts = Counter(tokens)
        total = len(tokens)
        if total == 0:
            return {}
        return {t: c / total for t, c in token_counts.items()}

    def update_document_frequency(self, tokens: List[str]) -> None:
        for token in set(tokens):
            self.document_frequency[token] = self.document_frequency.get(token, 0) + 1
        self.total_documents += 1

    def calculate_idf(self, token: str) -> float:
        if self.total_documents == 0:
            return 0.0
        df = self.document_frequency.get(token, 0)
        return np.log((self.total_documents + 1) / (df + 1)) + 1

    def calculate_tfidf(self, tokens: List[str]) -> Dict[str, float]:
        self.update_document_frequency(tokens)
        tf = self.calculate_tf(tokens)
        return {t: tf[t] * self.calculate_idf(t) for t in tf}

    # ==================== SECTION EXTRACTION =================================

    def extract_sections(self, text: str) -> Dict[str, str]:
        sections = {}
        lines = text.split('\n')
        current_section = 'header'
        current_content = []

        for line in lines:
            line_stripped = line.strip()
            line_lower    = line_stripped.lower()
            section_found = False

            if 0 < len(line_stripped) < 120:
                for section_name in self._section_order:
                    pattern = self.section_patterns[section_name]
                    if re.search(pattern, line_lower):
                        if current_content:
                            sections[current_section] = '\n'.join(current_content).strip()
                        current_section = section_name
                        current_content = []
                        section_found   = True
                        break

            if not section_found and line_stripped:
                current_content.append(line)

        if current_content:
            sections[current_section] = '\n'.join(current_content).strip()

        return sections

    # ==================== METADATA EXTRACTION ================================

    def extract_contact_info(self, text: str) -> Dict[str, str]:
        contact_info = {}
        email_match = re.search(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text
        )
        if email_match:
            contact_info['email'] = email_match.group()
        phone_match = re.search(r'[\+\d][\d\s\-\(\)]{8,}', text)
        if phone_match:
            contact_info['phone'] = phone_match.group().strip()
        linkedin_match = re.search(r'linkedin\.com/in/[\w\-]+', text.lower())
        if linkedin_match:
            contact_info['linkedin'] = linkedin_match.group()
        github_match = re.search(r'github\.com/[\w\-]+', text.lower())
        if github_match:
            contact_info['github'] = github_match.group()
        return contact_info

    def _get_section_line_ranges(self, text: str) -> Dict[str, Tuple[int, int]]:
        lines = text.split('\n')
        section_ranges: Dict[str, Tuple[int, int]] = {}
        current_section = 'header'
        start_line = 0
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            line_lower    = line_stripped.lower()
            if 0 < len(line_stripped) < 120:
                for section_name in self._section_order:
                    pattern = self.section_patterns[section_name]
                    if re.search(pattern, line_lower):
                        section_ranges[current_section] = (start_line, i)
                        current_section = section_name
                        start_line = i
                        break
        section_ranges[current_section] = (start_line, len(lines))
        return section_ranges

    # ==================== CRF TOKENISATION & FEATURES ========================

    @staticmethod
    def _word_shape(w: str) -> str:
        """Word shape: X for uppercase, x for lowercase, d for digit."""
        out = []
        for ch in w:
            if ch.isupper():
                out.append('X')
            elif ch.islower():
                out.append('x')
            elif ch.isdigit():
                out.append('d')
            else:
                out.append(ch)
        return ''.join(out)

    INSEPARABLE_SLASH = {'A/L', 'O/L', 'W/L', 'A/B'}
    _URL_RE       = re.compile(r'https?://', re.IGNORECASE)
    _PARTIAL_URL  = re.compile(r'^(www\.|github\.com|linkedin\.com|hackerrank\.com)', re.IGNORECASE)
    _NUMERIC_RATIO = re.compile(r'^[\d.,]+/[\d.,]+\.?$')

    @classmethod
    def _split_slash_token(cls, token: str) -> List[str]:
        """Split token on slashes unless it's a known exception."""
        if '/' not in token or token == '/':
            return [token]
        if cls._URL_RE.search(token) or cls._PARTIAL_URL.search(token):
            return [token]
        if token in cls.INSEPARABLE_SLASH:
            return [token]
        if cls._NUMERIC_RATIO.match(token):
            return [token]
        parts = token.split('/')
        result = []
        for i, p in enumerate(parts):
            if p:
                result.append(p)
            if i < len(parts) - 1:
                result.append('/')
        return result if result else [token]

    @classmethod
    def canonical_tokenise(cls, text: str) -> List[str]:
        """
        Tokenise raw resume text EXACTLY as the CRF was trained.
        Splits on whitespace, peels leading/trailing punctuation,
        then handles slash tokens using the same rules.

        NOTE: This must match the tokenisation used during CRF training.
        Do NOT add special-casing for C#, .NET, Node.js etc. here —
        both CRF models were trained with those tokens split naturally.
        Special-character skills are handled by _rule_based_extract_skills
        via placeholder substitution before regex processing.
        """
        tokens = []
        for raw in text.split():
            # Peel leading punctuation
            m = re.match(r'^([^\w]+)(.*)', raw)
            if m:
                tokens.append(m.group(1))
                raw = m.group(2)
            if not raw:
                continue
            # Peel trailing punctuation
            m2   = re.match(r'^(.*\w)([^\w]+)$', raw)
            core  = m2.group(1) if m2 else raw
            trail = m2.group(2) if m2 else ''

            tokens.extend(cls._split_slash_token(core))
            if trail:
                tokens.append(trail)

        return [t for t in tokens if t.strip()]

    @classmethod
    def _token_features(cls, words: List[str], i: int) -> Dict[str, Any]:
        """Feature dict for token at position i (same as notebook)."""
        w = words[i]

        feats = {
            'word.lower()':  w.lower(),
            'word.isupper()': w.isupper(),
            'word.istitle()': w.istitle(),
            'word.isdigit()': w.isdigit(),
            'word.shape':    cls._word_shape(w),
            'prefix-1': w[:1],
            'prefix-2': w[:2],
            'prefix-3': w[:3],
            'prefix-4': w[:4],
            'suffix-1': w[-1:],
            'suffix-2': w[-2:],
            'suffix-3': w[-3:],
            'suffix-4': w[-4:],
            'BOS': (i == 0),
            'EOS': (i == len(words) - 1),
        }

        if i > 0:
            pw = words[i - 1]
            feats['prev_word']  = pw.lower()
            feats['prev_shape'] = cls._word_shape(pw)
        else:
            feats['prev_word']  = 'BOS'
            feats['prev_shape'] = 'BOS'

        if i < len(words) - 1:
            nw = words[i + 1]
            feats['next_word']  = nw.lower()
            feats['next_shape'] = cls._word_shape(nw)
        else:
            feats['next_word']  = 'EOS'
            feats['next_shape'] = 'EOS'

        return feats

    # ==================== EXPERIENCE EXTRACTION ==============================

    # ── Keywords used to validate the CRF experience block ───────────────────
    _PROJECT_KEYWORDS = re.compile(
        r'\b(project|research|academic|final\s+year|undergraduate|capstone|'
        r'university\s+project|thesis|dissertation)\b',
        re.IGNORECASE,
    )
    _WORK_KEYWORDS = re.compile(
        r'\b(intern|worked|full[\s-]?time|employed|pvt|ltd|inc|corp|'
        r'professional\s+experience|work\s+history|employment)\b',
        re.IGNORECASE,
    )

    def _extract_experience_text_crf(self, text: str) -> Optional[str]:
        """
        Use the trained CRF to extract tokens labelled B-EXP / I-EXP.
        Returns the concatenated experience block (space-separated),
        or None if the CRF is unavailable, fails, or if the returned
        block looks like project/academic content rather than real
        professional experience.

        Validation rule
        ---------------
        If the extracted block contains strong project-related keywords
        (project, research, academic, final year, undergraduate, capstone,
        university project, thesis, dissertation) AND does NOT contain any
        work-experience cues (intern, worked, full-time, employed, Pvt, Ltd,
        Inc, Corp, professional experience, work history, employment), the
        block is treated as a false positive and None is returned so the
        fallback can handle it.
        """
        if self.crf_model is None:
            return None

        try:
            words = self.canonical_tokenise(text)
            if not words:
                return None
            X_seq = [self._token_features(words, i) for i in range(len(words))]
            tags  = self.crf_model.predict([X_seq])[0]

            exp_tokens = [
                w for w, tag in zip(words, tags)
                if tag in ('B-EXP', 'I-EXP')
            ]
            if not exp_tokens:
                return None

            exp_block = ' '.join(exp_tokens)

            # ── Validate: reject blocks that look like project sections ───────
            has_project_signal = bool(self._PROJECT_KEYWORDS.search(exp_block))
            has_work_signal    = bool(self._WORK_KEYWORDS.search(exp_block))

            if has_project_signal and not has_work_signal:
                # The CRF mis-classified a project/academic block as experience.
                # Return None so the section-filtered fallback is used instead.
                return None

            return exp_block

        except Exception as e:
            print(f"CRF experience extraction failed: {e}")
            return None

    def extract_years_of_experience(self, text: str) -> float:
        """
        Estimate years of professional experience.
        Uses CRF-isolated experience block (primary) with fallback to
        section-filtered regex, then phrase matching.
        """
        # ── Shared date-range regex pieces ───────────────────────────────────
        _month_word     = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)' 
        _month_word_dot = r'(?:' + _month_word + r'\.?)' 
        _month_num  = r'\d{1,2}'
        _year       = r'\d{4}'
        _sep_my     = r'[\s,\-/]*'
        _start_date = rf'(?:{_month_word_dot}{_sep_my}{_year}|{_month_num}{_sep_my}{_year})'
        _end_date   = rf'(?:{_month_word_dot}{_sep_my}{_year}|{_month_num}{_sep_my}{_year}|present|current|now|ongoing)'
        _range_sep  = r'\s*[-\u2013to]+\s*'
        _range_re   = re.compile(_start_date + _range_sep + _end_date, re.IGNORECASE | re.DOTALL)

        def _normalise_matches(matches):
            out = []
            for r in matches:
                r = re.sub(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.', r'\1', r, flags=re.IGNORECASE)
                r = re.sub(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(\d{4})\b', r'\1 \2', r, flags=re.IGNORECASE)
                r = re.sub(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)(\d{4})\b', r'\1 \2', r, flags=re.IGNORECASE)
                r = re.sub(r'\s+', ' ', r).strip()
                out.append(r)
            return out

        def _call_explainer(normalized):
            try:
                from experience_explainer import explain_experience
                ev = explain_experience(resume_text='\n'.join(normalized), crf_model_path=None)
                if ev["total_years"] > 0:
                    return round(ev["total_years"], 2)
            except Exception:
                pass
            return None

        # ── 1. CRF-based extraction (primary) ────────────────────────────────
        exp_block = self._extract_experience_text_crf(text)
        if exp_block:
            matches = _range_re.findall(exp_block)
            if matches:
                result = _call_explainer(_normalise_matches(matches))
                if result is not None:
                    return result

        # ── 2. Section-filtered fallback ──────────────────────────────────────
        section_ranges = self._get_section_line_ranges(text)
        edu_start,  edu_end  = section_ranges.get('education', (None, None))
        proj_start, proj_end = section_ranges.get('projects',  (None, None))

        lines = text.split('\n')
        filtered_lines = [
            line for i, line in enumerate(lines)
            if not ((edu_start  is not None and edu_start  <= i < edu_end) or
                    (proj_start is not None and proj_start <= i < proj_end))
        ]
        filtered_text = '\n'.join(filtered_lines)

        # Extra guard: neutralise filtered_text when it still looks project-heavy
        # but has no work cues, so project year references cannot inflate the score.
        _has_work_cue = bool(self._WORK_KEYWORDS.search(filtered_text))
        _has_proj_cue = bool(self._PROJECT_KEYWORDS.search(filtered_text))
        if _has_proj_cue and not _has_work_cue:
            filtered_text = ""

        if filtered_text.strip():
            matches = _range_re.findall(filtered_text)
            if matches:
                result = _call_explainer(_normalise_matches(matches))
                if result is not None:
                    return result

        # ── 3. Phrase-match fallback (scoped to filtered text) ─────────────
        # Run on filtered_text only (edu + project sections stripped) so that
        # phrases like "2 years of research" cannot match.
        phrase_text  = filtered_text if filtered_text.strip() else text
        phrase_lower = phrase_text.lower()
        phrase_patterns = [
            r'(\d+)\+?\s*years?\s+(?:of\s+)?(?:professional\s+|work\s+)?experience',
            r'experience[:\s]+(\d+)\+?\s*years?',
            r'(\d+)\+?\s*years?\s+(?:in|as)\s+(?!(?:a\s+)?(?:project|course|research|university|school|college))',
        ]
        years_found = []
        for pattern in phrase_patterns:
            years_found.extend([int(m) for m in re.findall(pattern, phrase_lower)])
        return float(max(years_found)) if years_found else 0.0

    # ==================== EDUCATION LEVEL =====================================

    def extract_education_level(self, text: str) -> str:
        sections  = self.extract_sections(text)
        exp_text  = sections.get("experience", "")
        edu_section = (
            sections.get("education", "")
            or sections.get("academic", "")
            or sections.get("qualifications", "")
        )
        if edu_section and len(edu_section.strip()) > 30:
            result = self._classify_education(edu_section)
            if result != "Unknown":
                return result
        full_minus_exp = text.replace(exp_text, " ") if exp_text else text
        result = self._classify_education(full_minus_exp)
        if result != "Unknown":
            return result
        return self._classify_education(text)

    def _classify_education(self, text: str) -> str:
        t = re.sub(r'\S+@\S+', ' ', text.lower())
        t = re.sub(r'http\S+|www\.\S+', ' ', t)
        if any(term in t for term in ['phd', 'ph.d', 'ph.d.', 'doctorate', 'doctoral', 'd.phil']):
            return 'PhD'
        if re.search(r'\bhnd\b', t) or 'higher national diploma' in t:
            return 'HND'
        if any(term in t for term in [
            'bachelor of science', 'bachelor of arts', 'bachelor of engineering',
            'bachelor of technology', 'bachelor of business', 'bachelor of computing',
            'bachelor of information', 'bachelors of', 'bachelor in', 'bachelors in',
            'b.eng', 'beng', 'b.sc', 'bsc', 'b.tech', 'btech', 'b.e.', 'b.e ',
            'b.a.', 'undergraduate', '(hons)', '(honours)', 'honours degree',
            'first year', '1st year', 'second year', '2nd year',
            'third year', '3rd year', 'fourth year', '4th year',
        ]):
            return 'Bachelors'
        if any(term in t for term in [
            'master of science', 'master of arts', 'master of engineering',
            'master of technology', 'master of business', 'master of computing',
            'master of information', 'master of philosophy', 'masters of', 'masters in',
            'master in', 'msc', 'm.sc', 'msc.', 'mba', 'm.b.a', 'meng', 'm.eng',
            'mtech', 'm.tech', 'postgraduate diploma', 'postgraduate degree',
            'post-graduate', 'post graduate', 'pgdip', 'pg diploma',
        ]):
            return 'Masters'
        if any(term in t for term in [
            'diploma in', 'diploma of', 'hnc', 'higher national certificate',
            'associate degree', 'associate of', 'foundation degree',
            'certificate in', 'certificate of',
        ]):
            return 'Diploma'
        if any(term in t for term in ['sliate', 'sri lanka institute of advanced technological education']):
            return 'HND'
        if re.search(r'\bnibm\b', t) or 'national institute of business management' in t:
            return 'HND'
        return 'Unknown'

    # ==================== FEATURE ENGINEERING ================================

    def extract_structured_features(
        self, original_text: str, tokens: List[str]
    ) -> Dict[str, Any]:
        features = {}
        features['total_words']         = len(tokens)
        features['unique_words']        = len(set(tokens))
        features['vocabulary_richness'] = len(set(tokens)) / len(tokens) if tokens else 0
        features['total_characters']    = len(original_text)
        features['avg_word_length']     = np.mean([len(w) for w in tokens]) if tokens else 0

        section_keywords = ['summary', 'objective', 'experience', 'education', 'skills', 'projects']
        features['has_sections']   = any(kw in original_text.lower() for kw in section_keywords)
        features['section_count']  = sum(1 for kw in section_keywords if kw in original_text.lower())
        features['numeric_count']  = len(re.findall(r'\d+', original_text))
        features['has_email']      = bool(re.search(r'\S+@\S+', original_text))
        features['has_phone']      = bool(re.search(r'\+?[\d\s\-\(\)]{10,}', original_text))

        experience_keywords = ['experience', 'worked', 'developed', 'managed', 'led', 'created', 'built']
        features['experience_keyword_count'] = sum(1 for kw in experience_keywords if kw in original_text.lower())

        education_keywords = ['degree', 'bachelor', 'master', 'phd', 'university', 'college']
        features['education_keyword_count'] = sum(1 for kw in education_keywords if kw in original_text.lower())

        return features

    # ==================== MAIN PROCESSING METHOD ==============================

    def process(self, resume_text: str) -> Dict[str, Any]:
        original_text    = self.validate_resume_text(resume_text)
        normalized_text  = self.normalize_text(original_text)
        tokens           = self.tokenize(normalized_text)
        filtered_tokens  = self.remove_stopwords(tokens)
        keywords         = self.extract_keywords(filtered_tokens, top_n=20)
        tfidf_scores     = self.calculate_tfidf(filtered_tokens)
        top_tfidf        = sorted(tfidf_scores.items(), key=lambda x: x[1], reverse=True)[:20]
        sections         = self.extract_sections(original_text)
        skills           = self.extract_skills(original_text)
        contact_info     = self.extract_contact_info(original_text)
        years_experience = self.extract_years_of_experience(original_text)
        education_level  = self.extract_education_level(original_text)
        structured_features = self.extract_structured_features(original_text, filtered_tokens)

        return {
            'original_text':    original_text,
            'normalized_text':  normalized_text,
            'tokens':           filtered_tokens,
            'token_count':      len(filtered_tokens),
            'keywords':         keywords,
            'tfidf_scores':     tfidf_scores,
            'top_tfidf_terms':  top_tfidf,
            'sections':         sections,
            'extracted_skills': skills,
            'skill_count':      len(skills),
            'years_of_experience': years_experience,
            'education_level':  education_level,
            'contact_info':     contact_info,
            'structured_features': structured_features,
            'section_completeness': {
                'has_summary':    any(k in sections for k in ['summary', 'objective']),
                'has_experience': 'experience' in sections,
                'has_education':  'education' in sections,
                'has_skills':     'skills' in sections,
                'has_projects':   'projects' in sections,
            },
        }

    # ==================== BATCH PROCESSING ====================================

    def batch_process(self, resume_texts: List[str]) -> List[Dict[str, Any]]:
        results = []
        for i, resume_text in enumerate(resume_texts):
            try:
                result = self.process(resume_text)
                result['resume_id']          = i
                result['processing_status']  = 'success'
                results.append(result)
            except Exception as e:
                results.append({
                    'resume_id':         i,
                    'processing_status': 'failed',
                    'error':             str(e),
                })
        return results


# ==================== UTILITY FUNCTIONS ======================================

def create_feature_vector(
    processed_resume: Dict[str, Any],
    feature_names: List[str],
) -> np.ndarray:
    features = processed_resume['structured_features']
    return np.array([features.get(name, 0) for name in feature_names])


def compare_resumes_similarity(
    resume1_tokens: List[str],
    resume2_tokens: List[str],
) -> float:
    vocab = list(set(resume1_tokens + resume2_tokens))
    vec1  = np.array([resume1_tokens.count(w) for w in vocab])
    vec2  = np.array([resume2_tokens.count(w) for w in vocab])
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))
