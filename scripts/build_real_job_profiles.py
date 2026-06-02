#!/usr/bin/env python3
"""
scripts/build_real_job_profiles.py
───────────────────────────────────
Version: 2.0.0
Offline profile builder. Reads raw JD text files, splits them into
individual ads, extracts canonical skills with JDSkillExtractor, aggregates
required / preferred skill lists, and writes data/real_job_profiles.json.

Run from the project root:
    python scripts/build_real_job_profiles.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO ADD A NEW ROLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Create a subfolder under data/raw_jds/ whose name is the role name:
       data/raw_jds/Data Scientist/
2. Place up to three level files inside it using these exact names:

   Level    Accepted filenames
   ───────  ──────────────────────────────
   Entry    entry_jobs.txt  OR  intern_jobs.txt
   Mid      mid_jobs.txt    OR  mid_level_jobs.txt
   Senior   senior_jobs.txt OR  senior_level_jobs.txt

3. Re-run this script — no other code changes needed.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

# ── project root on sys.path so `core` is importable ─────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.jd_skill_extractor import JDSkillExtractor

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION  (no CAREERS dict — roles are discovered automatically)
# ══════════════════════════════════════════════════════════════════════════════

JDS_ROOT   = PROJECT_ROOT / "data" / "raw_jds"
MODEL_PATH = PROJECT_ROOT / "models" / "crf_skills_v2.pkl"
OUTPUT_JSON = PROJECT_ROOT / "data" / "real_job_profiles.json"

# ── thresholds ────────────────────────────────────────────────────────────────
REQUIRED_THRESHOLD  = 0.40   # skill in ≥ 40% of JDs → required
PREFERRED_THRESHOLD = 0.25   # skill in 25–39% of JDs → preferred
MIN_JD_CHARS        = 200    # discard any block shorter than this

# ── canonical level name → accepted filename stems (order = priority) ─────────
LEVEL_FILENAMES: dict[str, list[str]] = {
    "Entry":  ["entry_jobs.txt",  "intern_jobs.txt"],
    "Mid":    ["mid_jobs.txt",    "mid_level_jobs.txt"],
    "Senior": ["senior_jobs.txt", "senior_level_jobs.txt"],
}

# ══════════════════════════════════════════════════════════════════════════════
# Auto-discovery
# ══════════════════════════════════════════════════════════════════════════════

def discover_careers(jds_root: Path) -> dict[str, dict[str, Path]]:
    """
    Walk *jds_root* and return a dict with the same shape as the old
    hand-written CAREERS constant::

        {
            "Software Engineer": {
                "Entry":  Path("data/raw_jds/Software Engineer/entry_jobs.txt"),
                "Mid":    Path("data/raw_jds/Software Engineer/mid_jobs.txt"),
                "Senior": Path("data/raw_jds/Software Engineer/senior_jobs.txt"),
            },
            ...
        }

    Rules
    -----
    * Each immediate subdirectory of *jds_root* is treated as a role.
    * For each level in ``LEVEL_FILENAMES`` the function tries each accepted
      filename in priority order and uses the first one that exists.
    * Levels whose file is not found are silently omitted (the main loop
      will print a SKIP warning, matching the existing behaviour).
    * Roles with no files at all are omitted entirely.
    * Results are sorted alphabetically by role name for reproducible output.
    """
    if not jds_root.exists():
        sys.exit(
            f"⛔ JD root folder not found: {jds_root}\n"
            f"   Create the folder and populate it as described in the docstring."
        )

    careers: dict[str, dict[str, Path]] = {}

    for role_dir in sorted(jds_root.iterdir()):
        if not role_dir.is_dir():
            continue  # skip stray files in the root

        role_name   = role_dir.name
        level_files: dict[str, Path] = {}

        for level_name, candidates in LEVEL_FILENAMES.items():
            for filename in candidates:
                candidate_path = role_dir / filename
                if candidate_path.exists():
                    level_files[level_name] = candidate_path
                    break  # first match wins

        if level_files:
            careers[role_name] = level_files

    return careers

# ══════════════════════════════════════════════════════════════════════════════
# JD Splitter  (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

def split_jds(text: str, src_name: str, min_chars: int = MIN_JD_CHARS) -> list[str]:
    """
    Split a raw multi-JD text file into individual ad strings using
    horizontal-rule separators only (lines of 3 or more = or - characters).

    Parameters
    ----------
    text     : full content of the raw JD file.
    src_name : filename shown in any error message.
    min_chars: minimum character count for a block to be kept.

    Raises
    ------
    ValueError
        If fewer than 2 valid blocks are found after splitting, which indicates
        the file does not use the expected horizontal-rule format.
    """
    raw_blocks = re.split(r"\n[=\-]{3,}\n", text)
    valid = [b.strip() for b in raw_blocks if len(b.strip()) >= min_chars]

    if len(valid) < 2:
        raise ValueError(
            f"\n⛔ File '{src_name}' produced only {len(valid)} valid block(s) "
            f"after horizontal-rule splitting.\n"
            f"  Expected format: individual job ads separated by lines of "
            f"three or more '=' or '-' characters.\n"
            f"  Please check the file format and ensure each job ad is "
            f"separated by a horizontal rule (e.g. '===' or '---').\n"
            f"  Found {len(raw_blocks)} raw split(s); "
            f"{len(raw_blocks) - len(valid)} block(s) discarded as too short "
            f"(< {min_chars} chars)."
        )

    return valid

# ══════════════════════════════════════════════════════════════════════════════
# Main  (unchanged except CAREERS replaced by discover_careers())
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    # ── guards ────────────────────────────────────────────────────────────────
    if not MODEL_PATH.exists():
        sys.exit(
            f"⛔ CRF model not found: {MODEL_PATH}\n"
            f"  Place crf_skills_v2.pkl in models/ and retry."
        )

    careers = discover_careers(JDS_ROOT)
    if not careers:
        sys.exit(
            f"⛔ No roles discovered under {JDS_ROOT}.\n"
            f"  Create at least one subfolder with the required .txt files."
        )

    print(f"Discovered {len(careers)} role(s) under {JDS_ROOT.relative_to(PROJECT_ROOT)}")
    print(f"Loading JDSkillExtractor from {MODEL_PATH.name} …")
    extractor = JDSkillExtractor(str(MODEL_PATH))
    print("  ✓ Model loaded\n")

    profiles: dict = {}

    for role_name, level_files in careers.items():
        print(f"{'━' * 60}")
        print(f"  Role: {role_name}")

        for level_name, src_path in level_files.items():
            # ── load & split ──────────────────────────────────────────────────
            if not src_path.exists():
                print(f"  [SKIP] {level_name}: file not found → {src_path}", file=sys.stderr)
                continue

            text = src_path.read_text(encoding="utf-8")
            try:
                blocks = split_jds(text, src_path.name)
            except ValueError as exc:
                sys.exit(str(exc))

            print(f"  {level_name:6s} — {len(blocks)} JDs from {src_path.name}")

            # ── extract skills ────────────────────────────────────────────────
            skill_counter: Counter = Counter()
            valid_texts:   list[str] = []

            for jd_text in blocks:
                skills = extractor.extract_skills(jd_text)
                valid_texts.append(jd_text)
                for skill in skills:
                    skill_counter[skill] += 1

            n = len(valid_texts)

            # ── compute frequencies and classify ─────────────────────────────
            freq: dict[str, float] = {
                skill: round(count / n, 4)
                for skill, count in skill_counter.items()
            }

            required = sorted(
                s for s, p in freq.items() if p >= REQUIRED_THRESHOLD
            )

            preferred = sorted(
                s for s, p in freq.items()
                if PREFERRED_THRESHOLD <= p < REQUIRED_THRESHOLD
            )

            skill_frequencies = dict(
                sorted(freq.items(), key=lambda kv: -kv[1])
            )

            print(
                f"    unique skills: {len(freq)}"
                f" | required (≥{int(REQUIRED_THRESHOLD*100)}%): {len(required)}"
                f" | preferred ({int(PREFERRED_THRESHOLD*100)}–{int(REQUIRED_THRESHOLD*100)-1}%): {len(preferred)}"
            )
            if required:
                print(f"    top required : {required[:6]}")

            # ── build profile ────────────────────────────────────────────────
            key = f"{role_name}_{level_name}"
            profiles[key] = {
                "role":             role_name,
                "level":            level_name,
                "num_jds":          n,
                "required_skills":  required,
                "preferred_skills": preferred,
                "skill_frequencies": skill_frequencies,
                "job_document":     "\n\n".join(valid_texts),
            }

    if not profiles:
        sys.exit("⛔ No profiles were built. Check that JD files exist and are non-empty.")

    # ── write output ──────────────────────────────────────────────────────────
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)

    size_kb = OUTPUT_JSON.stat().st_size / 1024
    print(f"\n{'━' * 60}")
    print(f"✓ Saved → {OUTPUT_JSON} ({size_kb:.1f} KB)")
    print(f"  Profile keys: {list(profiles.keys())}")


if __name__ == "__main__":
    main()
