"""
Resume Parser — World‑Class PDF / DOCX / TXT Extraction
AI‑Based Resume Analyzer for Sri Lankan IT Job Applicants

Design grounded in peer‑reviewed research:
  • Adhikari et al. (2024) — PDF parser benchmark (arXiv:2410.09871)
  • Zhu et al. (2025) — SmartResume layout‑aware pipeline (arXiv:2510.09722)
  • Yu, Zhang & Wang (2020) — PDFBoT multi‑column extraction
  • Textkernel (2023) — Visual‑gap column detection for CVs
  • Livathinos et al. (2025) — Docling document understanding toolkit (arXiv:2501.17887)

Key innovations over the previous parser:
  1. PyMuPDF block‑level extraction → XY‑cut reading‑order reconstruction
  2. Histogram‑based column detection for multi‑column / sidebar CVs
  3. Graceful fallback cascade: PyMuPDF → pdfplumber → Tesseract OCR
  4. Spaced‑letter repair ('S o f t w a r e' → 'Software')
  5. Full DOCX + TXT support retained

Authors: KIC‑HNDCSAI‑251F (002, 003, 006, 020)
Date: May 2026
"""

import io
import os
import re
from typing import List, Tuple, Optional

# ---------------------------------------------------------------------------
# Optional dependency helpers — degrade gracefully when a library is missing
# ---------------------------------------------------------------------------
_PYMUPDF_AVAILABLE = False
_PDFPLUMBER_AVAILABLE = False
_PYTESSERACT_AVAILABLE = False
_PDF2IMAGE_AVAILABLE = False
_DOCX_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    _PYMUPDF_AVAILABLE = True
except ImportError:
    pass

try:
    import pdfplumber
    _PDFPLUMBER_AVAILABLE = True
except ImportError:
    pass

try:
    import pytesseract
    _PYTESSERACT_AVAILABLE = True
except ImportError:
    pass

try:
    from pdf2image import convert_from_bytes
    _PDF2IMAGE_AVAILABLE = True
except ImportError:
    pass

try:
    import docx
    _DOCX_AVAILABLE = True
except ImportError:
    pass


# ======================================================================
# PUBLIC API
# ======================================================================

def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """
    Extract clean, reading‑order‑preserved text from a resume file.

    Args:
        file_bytes : raw file bytes (PDF, DOCX, or TXT)
        filename   : used only to detect extension

    Returns:
        Plain text string with columns merged in correct reading order.
    """
    ext = os.path.splitext(filename.lower())[1]

    if ext == ".pdf":
        return _extract_pdf(file_bytes)
    elif ext in (".docx", ".doc"):
        return _extract_docx(file_bytes)
    elif ext == ".txt":
        return _extract_txt(file_bytes)
    else:
        # Unknown extension — try PDF first, then raw text
        try:
            return _extract_pdf(file_bytes)
        except Exception:
            return file_bytes.decode("utf-8", errors="ignore")


# ======================================================================
# PDF EXTRACTION — multi‑engine cascade
# ======================================================================

def _extract_pdf(file_bytes: bytes) -> str:
    """
    Extract text from a PDF using the following cascade:

    1. PyMuPDF block‑level extraction + XY‑cut reading‑order (preferred)
    2. pdfplumber (handles complex tables / mixed layouts)
    3. pdf2image + Tesseract OCR (scanned / image‑only PDFs)
    """
    errors = []

    # ── Strategy 1: PyMuPDF + XY‑cut ──────────────────────────────────
    if _PYMUPDF_AVAILABLE:
        try:
            text = _extract_pdf_pymupdf(file_bytes)
            if _text_quality_ok(text):
                return _clean_extracted_text(text)
            errors.append("PyMuPDF produced insufficient text")
        except Exception as e:
            errors.append(f"PyMuPDF: {e}")
    else:
        errors.append("PyMuPDF not installed")

    # ── Strategy 2: pdfplumber ────────────────────────────────────────
    if _PDFPLUMBER_AVAILABLE:
        try:
            text = _extract_pdf_plumber(file_bytes)
            if _text_quality_ok(text):
                return _clean_extracted_text(text)
            errors.append("pdfplumber produced insufficient text")
        except Exception as e:
            errors.append(f"pdfplumber: {e}")
    else:
        errors.append("pdfplumber not installed")

    # ── Strategy 3: OCR ───────────────────────────────────────────────
    if _PYTESSERACT_AVAILABLE and _PDF2IMAGE_AVAILABLE:
        try:
            text = _extract_pdf_ocr(file_bytes)
            if _text_quality_ok(text, threshold=30):
                return _clean_extracted_text(text)
            errors.append("OCR produced insufficient text")
        except Exception as e:
            errors.append(f"OCR: {e}")
    else:
        errors.append("OCR (pytesseract + pdf2image) not available")

    # ── All strategies exhausted ──────────────────────────────────────
    raise ValueError(
        "Could not extract text from PDF. "
        "The file may be image‑based / scanned (install pytesseract + pdf2image) "
        "or password protected. Engine errors: " + "; ".join(errors)
    )


# ======================================================================
# STRATEGY 1: PyMuPDF + XY‑cut reading‑order reconstruction
# ======================================================================

def _extract_pdf_pymupdf(file_bytes: bytes) -> str:
    """
    PyMuPDF block‑level extraction with column‑aware XY‑cut sorting.

    Approach (inspired by PDFBoT + SmartResume):
      1. Get all text blocks with bbox coordinates from each page.
      2. Detect if the page has multiple columns via X‑gap histogram.
      3. If multi‑column: partition blocks into columns, then sort each
         column top‑down, and concatenate columns left‑to‑right.
      4. If single‑column: sort blocks top‑down.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    all_pages: List[str] = []

    for page in doc:
        # Extract blocks with bounding boxes
        blocks = page.get_text("blocks")  # list of (x0,y0,x1,y1, text, block_no, block_type)
        text_blocks = [
            b for b in blocks
            if b[6] == 0 and b[4].strip()  # type 0 = text, non‑empty
        ]

        if not text_blocks:
            continue

        # Detect column layout
        columns = _detect_columns(text_blocks, page_width=page.rect.width)

        if len(columns) > 1:
            # Multi‑column: sort blocks within each column, then merge columns L→R
            page_text_parts = []
            for col_x_range in sorted(columns, key=lambda r: r[0]):
                col_blocks = _blocks_in_x_range(text_blocks, *col_x_range)
                col_blocks = _sort_blocks_top_down(col_blocks)
                col_text = "\n".join(b[4].strip() for b in col_blocks)
                page_text_parts.append(col_text)
            all_pages.append("\n".join(page_text_parts))
        else:
            # Single column: simple top‑down sort
            sorted_blocks = _sort_blocks_top_down(text_blocks)
            page_text = "\n".join(b[4].strip() for b in sorted_blocks)
            all_pages.append(page_text)

    doc.close()
    return "\n\n".join(all_pages)


def _detect_columns(
    blocks: List[Tuple],
    page_width: float,
    min_gap_ratio: float = 0.08,
) -> List[Tuple[float, float]]:
    """
    Detect column boundaries by histogram of X‑coordinates.

    Algorithm (Textkernel 2023; PDFBoT 2020):
      1. Collect the x0 of every text block.
      2. Sort and scan for gaps ≥ min_gap_ratio * page_width.
      3. A large gap indicates a column separator.

    Returns a list of (x_min, x_max) ranges for each detected column.
    If no gap is large enough, returns a single range covering the page.
    """
    min_gap = page_width * min_gap_ratio
    x_starts = sorted(set(round(b[0], 1) for b in blocks))

    if len(x_starts) < 2:
        return [(0, page_width)]

    # Find natural column boundaries where gaps exceed threshold
    boundaries = [0.0]
    for i in range(len(x_starts) - 1):
        gap = x_starts[i + 1] - x_starts[i]
        if gap >= min_gap:
            boundaries.append((x_starts[i] + x_starts[i + 1]) / 2)

    boundaries.append(page_width)

    # Build column ranges
    columns = [(boundaries[i], boundaries[i + 1]) for i in range(len(boundaries) - 1)]

    # Filter out very narrow columns (< 15% of page width)
    columns = [(x0, x1) for x0, x1 in columns if (x1 - x0) >= page_width * 0.12]

    return columns if columns else [(0, page_width)]


def _blocks_in_x_range(
    blocks: List[Tuple],
    x_min: float,
    x_max: float,
) -> List[Tuple]:
    """Return blocks whose horizontal centre falls within [x_min, x_max)."""
    result = []
    for b in blocks:
        cx = (b[0] + b[2]) / 2  # centre x
        if x_min <= cx < x_max:
            result.append(b)
    return result


def _sort_blocks_top_down(blocks: List[Tuple]) -> List[Tuple]:
    """Sort blocks by ascending y0, then ascending x0 for same‑line blocks."""
    return sorted(blocks, key=lambda b: (round(b[1], 0), b[0]))


# ======================================================================
# STRATEGY 2: pdfplumber (fallback)
# ======================================================================

def _extract_pdf_plumber(file_bytes: bytes) -> str:
    """
    Extract text with pdfplumber.

    Uses layout‑preserving mode first; falls back to simple extract_text.
    """
    all_pages: List[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            # Try layout mode
            page_text = page.extract_text(
                x_tolerance=3,
                y_tolerance=3,
                layout=True,
                x_density=7.25,
                y_density=13,
            )
            if not page_text or len(page_text.strip()) < 20:
                page_text = page.extract_text()
            if page_text:
                all_pages.append(page_text)
    return "\n\n".join(all_pages)


# ======================================================================
# STRATEGY 3: OCR via Tesseract
# ======================================================================

def _extract_pdf_ocr(file_bytes: bytes) -> str:
    """
    Render PDF pages to images and OCR them with Tesseract.

    This is the last resort for scanned/image‑based PDFs.
    """
    images = convert_from_bytes(file_bytes, dpi=300)
    all_pages: List[str] = []
    for img in images:
        text = pytesseract.image_to_string(img, lang="eng")
        if text.strip():
            all_pages.append(text)
    return "\n\n".join(all_pages)


# ======================================================================
# DOCX EXTRACTION
# ======================================================================

def _extract_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX, including table content."""
    if not _DOCX_AVAILABLE:
        raise ValueError(
            "python-docx is not installed. Install it with: pip install python-docx"
        )
    doc = docx.Document(io.BytesIO(file_bytes))
    lines: List[str] = []

    for para in doc.paragraphs:
        if para.text.strip():
            lines.append(para.text)

    # Extract from tables (common in CVs for skills, timelines, etc.)
    for table in doc.tables:
        for row in table.rows:
            row_text = "  ".join(
                cell.text.strip() for cell in row.cells if cell.text.strip()
            )
            if row_text:
                lines.append(row_text)

    return _clean_extracted_text("\n".join(lines))


# ======================================================================
# TXT EXTRACTION
# ======================================================================

def _extract_txt(file_bytes: bytes) -> str:
    """Extract text from plain‑text file with encoding detection."""
    for encoding in ["utf-8", "utf-16", "latin-1", "cp1252"]:
        try:
            return _clean_extracted_text(file_bytes.decode(encoding))
        except (UnicodeDecodeError, LookupError):
            continue
    return file_bytes.decode("ascii", errors="ignore")


# ======================================================================
# TEXT CLEANING & NORMALISATION
# ======================================================================

def _clean_extracted_text(text: str) -> str:
    """
    Normalise extracted text for downstream processing.

    Steps:
      - Normalise Unicode dashes, bullets, non‑breaking spaces
      - Repair spaced‑letter artefacts ('S o f t w a r e' → 'Software')
      - Remove non‑printable characters
      - Collapse 3+ blank lines to 2
      - Trim trailing spaces per line
    """
    # Unicode punctuation normalisation
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u2022", "-").replace("\u2023", "-")
    text = text.replace("\u00a0", " ")
    text = text.replace("\uf0b7", "-")

    # Repair spaced‑letter artefacts from PDF extraction
    text = _repair_spaced_letters(text)

    # Remove non‑printable characters (keep newline and tab)
    text = re.sub(r'[^\x09\x0a\x0d\x20-\x7e\x80-\xff]', ' ', text)

    # Collapse 3+ blank lines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Trim trailing spaces on each line
    text = "\n".join(line.rstrip() for line in text.splitlines())

    return text.strip()


def _repair_spaced_letters(text: str) -> str:
    """
    Fix artefacts like 'S o f t w a r e' → 'Software'.

    Detects isolated single letters separated by spaces and merges them
    into candidate words. Only applies when the pattern is unambiguous.
    """
    # Pattern: (single letter + space) repeated 3+ times
    pattern = re.compile(
        r'(?<!\w)((?:[A-Za-z]\s){3,}(?:[A-Za-z]))(?!\w)'
    )

    def _merge(match: re.Match) -> str:
        return match.group().replace(" ", "")

    return pattern.sub(_merge, text)


# ======================================================================
# QUALITY CHECKS
# ======================================================================

def _text_quality_ok(text: str, threshold: int = 80) -> bool:
    """
    Heuristic: extracted text is "good enough" if it has ≥ threshold
    non‑whitespace characters (roughly 1‑2 sentences).
    """
    return text is not None and len(text.strip()) >= threshold


# ======================================================================
# MODULE SELF‑TEST
# ======================================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python resume_parser.py <path_to_resume.pdf|.docx|.txt>")
        sys.exit(1)

    filepath = sys.argv[1]
    with open(filepath, "rb") as fh:
        data = fh.read()

    result = extract_text_from_bytes(data, os.path.basename(filepath))
    print(result[:3000])
    print(f"\n--- Total characters extracted: {len(result)} ---")