"""
core/jd_skill_extractor.py
───────────────────────────
Version: 1.1.0
Standalone, reusable skill extractor for job-description text.

Design rules (all enforced here):
  • ResumePreprocessor is NEVER modified – it is instantiated to access
    skill_surface_to_canonical AND to delegate rule-based extraction.
  • The CRF model is loaded and called ONLY inside this class.
  • canonical_tokenise and word_shape are replicated EXACTLY from training
    (crf_skill_ner_v2.ipynb cells 9 & 11) – no deviation allowed.
  • The CRF runs on the FULL token sequence in ONE predict call – no chunking,
    no sentence splitting.
  • Output contains ONLY keys that exist in skill_surface_to_canonical.
  • No custom skill dictionaries, no hard-coded aliases, no new canonical names.
"""

import re
import sys
from pathlib import Path

import joblib

# Import ResumePreprocessor to access its vocabulary – DO NOT modify the class
from core.resume_preprocessing_pipeline import ResumePreprocessor


# ══════════════════════════════════════════════════════════════════════════════
# Canonical tokeniser  – exact replica of crf_skill_ner_v2.ipynb Cell 9
# ══════════════════════════════════════════════════════════════════════════════

_INSEPARABLE   = {"A/L", "O/L", "W/L", "A/B"}
_URL_RE        = re.compile(r"https?://", re.I)
_PARTIAL_URL   = re.compile(
    r"^(www\.|github\.com|linkedin\.com|hackerrank\.com)", re.I
)
_NUMERIC_RATIO = re.compile(r"^[\d.,]+/[\d.,]+\.?$")


def word_shape(w: str) -> str:
    """
    Uncompressed character-shape mapping:
      uppercase → X,  lowercase → x,  digit → d,  other → literal.
    Must match the annotation tool and training pipeline exactly.
    """
    out: list[str] = []
    for ch in w:
        if ch.isupper():
            out.append("X")
        elif ch.islower():
            out.append("x")
        elif ch.isdigit():
            out.append("d")
        else:
            out.append(ch)
    return "".join(out)


def _split_slash_token(token: str) -> list[str]:
    """Split on / unless the token is a known exception."""
    if "/" not in token or token == "/":
        return [token]
    if _URL_RE.search(token) or _PARTIAL_URL.search(token):
        return [token]
    if token in _INSEPARABLE:
        return [token]
    if _NUMERIC_RATIO.match(token):
        return [token]
    parts = token.split("/")
    result: list[str] = []
    for i, p in enumerate(parts):
        if p:
            result.append(p)
        if i < len(parts) - 1:
            result.append("/")
    return result if result else [token]


def canonical_tokenise(text: str) -> list[str]:
    """
    Production tokeniser – must match training exactly:
      1. Split on whitespace.
      2. Peel leading punctuation into its own token.
      3. Peel trailing punctuation into its own token.
      4. Apply slash-splitting rules on the core token.
    """
    tokens: list[str] = []
    for raw in text.split():
        m = re.match(r"^([^\w]+)(.*)", raw)
        if m:
            tokens.append(m.group(1))
            raw = m.group(2)
        if not raw:
            continue
        m2    = re.match(r"^(.*\w)([^\w]+)$", raw)
        core  = m2.group(1) if m2 else raw
        trail = m2.group(2) if m2 else ""
        tokens.extend(_split_slash_token(core))
        if trail:
            tokens.append(trail)
    return [t for t in tokens if t.strip()]


# ══════════════════════════════════════════════════════════════════════════════
# Token feature function – exact replica of crf_skill_ner_v2.ipynb Cell 11
# prefix-1..4 / suffix-1..4 / BOS+EOS string sentinels / word.shape
# ══════════════════════════════════════════════════════════════════════════════

def _token_features(words: list[str], i: int) -> dict:
    """
    Feature dict for token at position i in the full sequence.
    Mirrors the training feature function line-for-line.
    Must not add, remove, or rename any feature key.
    """
    word = words[i]
    features: dict = {
        "word.lower()":   word.lower(),
        "word.isupper()": word.isupper(),
        "word.istitle()": word.istitle(),
        "word.isdigit()": word.isdigit(),
        "word.shape":     word_shape(word),
        "prefix-1": word[:1],
        "prefix-2": word[:2],
        "prefix-3": word[:3],
        "prefix-4": word[:4],
        "suffix-1": word[-1:],
        "suffix-2": word[-2:],
        "suffix-3": word[-3:],
        "suffix-4": word[-4:],
    }
    if i > 0:
        pw = words[i - 1]
        features["prev_word"]  = pw.lower()
        features["prev_shape"] = word_shape(pw)
    else:
        features["prev_word"]  = "BOS"
        features["prev_shape"] = "BOS"
    if i < len(words) - 1:
        nw = words[i + 1]
        features["next_word"]  = nw.lower()
        features["next_shape"] = word_shape(nw)
    else:
        features["next_word"]  = "EOS"
        features["next_shape"] = "EOS"
    return features


# ══════════════════════════════════════════════════════════════════════════════
# JDSkillExtractor
# ══════════════════════════════════════════════════════════════════════════════

class JDSkillExtractor:
    """
    Extracts canonical skill names from job-description text.

    Uses two complementary approaches whose outputs are unioned:
      1. CRF BIO tagger  – sequence model, high precision for technical spans.
      2. Rule-based scan – ensures high recall via direct vocabulary lookup.

    All output skill names are keys from ResumePreprocessor.skill_surface_to_canonical,
    guaranteeing alignment with the production matching engine vocabulary.
    """

    def __init__(self, model_path: str) -> None:
        """
        Parameters
        ----------
        model_path : str
            Path to the trained sklearn-crfsuite CRF model (joblib pickle).
        """
        _mp = Path(model_path)
        if not _mp.exists():
            raise FileNotFoundError(
                f"CRF model not found: {_mp.resolve()}\n"
                f"Place crf_skills_v2.pkl in models/ or adjust MODEL_PATH."
            )

        # Load the CRF model
        self._crf = joblib.load(str(_mp))

        # Instantiate ResumePreprocessor to access the production vocabulary
        # AND to delegate rule-based extraction.  The class is not modified.
        self._preprocessor = ResumePreprocessor()
        self._surface_map: dict[str, str] = self._preprocessor.skill_surface_to_canonical

    # ── private ───────────────────────────────────────────────────────────────

    def _rule_based_extract(self, text: str) -> set[str]:
        """
        Delegates to ResumePreprocessor.extract_skills() to run the production
        rule-based extractor (n-grams, variant generation, fuzzy matching).
        Returns the same set of canonical skill names as the production pipeline.
        """
        return set(self._preprocessor.extract_skills(text))

    def _crf_extract(self, text: str) -> set[str]:
        """
        CRF BIO extraction on the FULL token sequence – one predict call,
        no chunking, no sentence splitting.
        Returns a set of canonical skill names mapped from the extracted spans.
        """
        tokens = canonical_tokenise(text)
        if not tokens:
            return set()

        # Build ONE feature list for the entire sequence
        X = [_token_features(tokens, i) for i in range(len(tokens))]

        # Single predict call on the complete sequence
        tags: list[str] = self._crf.predict([X])[0]

        # Reconstruct BIO spans
        spans: list[str] = []
        current: list[str] = []
        for tok, tag in zip(tokens, tags):
            if tag == "B-SKILL":
                if current:
                    spans.append(" ".join(current))
                current = [tok]
            elif tag == "I-SKILL" and current:
                current.append(tok)
            else:
                if current:
                    spans.append(" ".join(current))
                current = []
        if current:
            spans.append(" ".join(current))

        # Map spans to canonical names; drop any that aren't in the vocabulary
        found: set[str] = set()
        for span in spans:
            key = span.lower().strip()
            if key in self._surface_map:
                found.add(self._surface_map[key])
        return found

    # ── public ────────────────────────────────────────────────────────────────

    def extract_skills(self, text: str) -> set[str]:
        """
        Extract canonical skill names from a single job-description text.

        Steps:
          1. Tokenise the FULL text (canonical_tokenise, no chunking).
          2. Build ONE feature list for the entire token sequence.
          3. Call model.predict([X])[0] once.
          4. Reconstruct BIO spans and map to canonical names.
          5. Also run rule-based keyword scan on the same text.
          6. Return UNION of CRF and rule-based results.

        Returns
        -------
        set[str]
            Set of canonical skill names (all are keys of skill_surface_to_canonical).
        """
        return self._crf_extract(text) | self._rule_based_extract(text)
