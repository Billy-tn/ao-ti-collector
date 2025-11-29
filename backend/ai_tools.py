# backend/ai_tools.py
from __future__ import annotations

import io
import os
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse

from .auth import AuthenticatedUser, get_current_user
from . import file_extractors
from .ai_extractors import build_structured_analysis

router = APIRouter(prefix="/ai", tags=["ai"])

# ============================================================
# FILE TEXT EXTRACTION (PDF/DOCX/XLSX/TXT) + multi-files
# ============================================================

MAX_FILES = 40
MAX_TOTAL_BYTES = 30 * 1024 * 1024   # 30 MB total
MAX_SINGLE_BYTES = 12 * 1024 * 1024  # 12 MB / file


def extract_text_from_any(filename: str, content_type: str, data: bytes) -> str:
    return file_extractors.extract_text_from_any(filename, content_type, data)

# ------------------------------------------------------------
# In-memory store for generated analyses
# (If uvicorn restarts, these are lost; that's OK for v4)
# ------------------------------------------------------------
ANALYSES: Dict[str, Dict[str, Any]] = {}

# Where is the SQLite DB?
REPO_ROOT = Path(__file__).resolve().parents[1]
AO_DB_PATH = REPO_ROOT / "ao.db"

# ------------------------------------------------------------
# Small utilities
# ------------------------------------------------------------

def _utc_iso() -> str:
    return datetime.utcnow().isoformat(timespec="microseconds") + "Z"


def _normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _safe_filename(name: str) -> str:
    name = (name or "report").strip()
    name = re.sub(r"[^\w\-.() \[\]]+", "", name, flags=re.UNICODE).strip()
    return name or "report"


def _strip_non_textual_noise(s: str) -> str:
    # helps reduce garbage when extracted from tables
    s = s.replace("\x00", " ")
    s = re.sub(r"[ \t]+\n", "\n", s)
    return s


# ------------------------------------------------------------
# PDF TEXT EXTRACTION (multi-engines)
# ------------------------------------------------------------

def _extract_text_pymupdf(pdf_bytes: bytes) -> str:
    import fitz  # PyMuPDF
    text_parts: List[str] = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page in doc:
            text_parts.append(page.get_text("text") or "")
    finally:
        doc.close()
    return "\n".join(text_parts).strip()


def _extract_text_pdfplumber(pdf_bytes: bytes) -> str:
    import pdfplumber
    from io import BytesIO

    text_parts: List[str] = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for p in pdf.pages:
            text_parts.append(p.extract_text() or "")
    return "\n".join(text_parts).strip()


def _extract_text_pypdf(pdf_bytes: bytes) -> str:
    from io import BytesIO
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_bytes))
    text_parts: List[str] = []
    for page in reader.pages:
        text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts).strip()


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Try extraction engines in order:
      1) PyMuPDF (fitz)
      2) pdfplumber
      3) pypdf (fallback)
    """
    errors: List[str] = []
    for fn in (_extract_text_pymupdf, _extract_text_pdfplumber, _extract_text_pypdf):
        try:
            txt = fn(pdf_bytes)
            txt = _strip_non_textual_noise(txt)
            if txt and len(txt.strip()) > 50:
                return txt
        except Exception as e:
            errors.append(f"{fn.__name__}: {e}")

    raise HTTPException(
        status_code=422,
        detail=f"Impossible d'extraire le texte du PDF. Détails: {errors[:3]}",
    )


# ------------------------------------------------------------
# Date parsing helpers (FR/EN)
# ------------------------------------------------------------

_FR_MONTHS = {
    "janvier": "01",
    "février": "02", "fevrier": "02",
    "mars": "03",
    "avril": "04",
    "mai": "05",
    "juin": "06",
    "juillet": "07",
    "août": "08", "aout": "08",
    "septembre": "09",
    "octobre": "10",
    "novembre": "11",
    "décembre": "12", "decembre": "12",
}

_EN_MONTHS = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}

def _date_in_reasonable_range(iso: str) -> bool:
    # Keep wide enough to not discard older reference docs,
    # but blocks crazy false positives.
    try:
        y = int(iso[:4])
        return 2010 <= y <= 2035
    except Exception:
        return False


def _to_iso(y: int, m: int, d: int) -> Optional[str]:
    try:
        date(y, m, d)
        return f"{y:04d}-{m:02d}-{d:02d}"
    except Exception:
        return None


def _find_date_candidates(text: str) -> List[str]:
    """
    Finds candidates in the given text chunk and returns ISO dates.
    Supports:
      - yyyy-mm-dd
      - dd/mm/yyyy or dd-mm-yyyy
      - "2 février 2024" / "February 2, 2024"
    """
    out: List[str] = []
    t = text

    # yyyy-mm-dd
    for m in re.finditer(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", t):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        iso = _to_iso(y, mo, d)
        if iso:
            out.append(iso)

    # dd/mm/yyyy or dd-mm-yyyy
    for m in re.finditer(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", t):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        iso = _to_iso(y, mo, d)
        if iso:
            out.append(iso)

    low = t.lower()

    # FR: "2 février 2024"
    for m in re.finditer(r"\b(\d{1,2})\s+([a-zéèêàùâîôûç]+)\s+(20\d{2})\b", low):
        d = int(m.group(1))
        mon = m.group(2)
        y = int(m.group(3))
        if mon in _FR_MONTHS:
            iso = _to_iso(y, int(_FR_MONTHS[mon]), d)
            if iso:
                out.append(iso)

    # EN: "february 2, 2024" or "february 2 2024"
    for m in re.finditer(r"\b([a-z]+)\s+(\d{1,2})(?:,)?\s+(20\d{2})\b", low):
        mon = m.group(1)
        d = int(m.group(2))
        y = int(m.group(3))
        if mon in _EN_MONTHS:
            iso = _to_iso(y, int(_EN_MONTHS[mon]), d)
            if iso:
                out.append(iso)

    # de-dup while preserving order
    seen = set()
    uniq = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _pick_date_by_anchors(text: str, anchors: List[str]) -> Optional[str]:
    low = text.lower()
    for a in anchors:
        idx = low.find(a)
        if idx != -1:
            window = low[max(0, idx - 250): min(len(low), idx + 1200)]
            cands = _find_date_candidates(window)
            cands = [d for d in cands if _date_in_reasonable_range(d)]
            if cands:
                return cands[0]
    return None


def _pick_closing_date(text: str) -> Optional[str]:
    # Anchor-based extraction is usually more reliable than global scan
    anchors = [
        "date de clôture", "date cloture", "clôture", "cloture",
        "date limite", "date et heure limite", "soumissions doivent être reçues",
        "closing date", "closing time", "tenders must be received", "deadline",
    ]
    dt = _pick_date_by_anchors(text, anchors)
    if dt:
        return dt

    # fallback: first reasonable date found in doc
    cands = _find_date_candidates(text[:20000])
    cands = [d for d in cands if _date_in_reasonable_range(d)]
    return cands[0] if cands else None


def extract_key_dates(text: str) -> Dict[str, Optional[str]]:
    return {
        "closing_date": _pick_closing_date(text),
        "questions_deadline": _pick_date_by_anchors(text, [
            "date limite de questions", "date limite des questions", "questions jusqu", "questions au plus tard",
            "question deadline", "questions must be received by", "questions doivent être reçues",
        ]),
        "site_visit_date": _pick_date_by_anchors(text, [
            "visite", "visite des lieux", "visite obligatoire", "réunion d'information", "reunion d'information",
            "site visit", "mandatory site visit",
        ]),
        "addenda_deadline": _pick_date_by_anchors(text, [
            "addenda", "date limite addenda", "dernier addenda", "end of addendum",
        ]),
        "opening_date": _pick_date_by_anchors(text, [
            "ouverture des soumissions", "opening of tenders", "ouverture publique",
        ]),
    }


# ------------------------------------------------------------
# Buyer and estimated value heuristics (anti-false-positives)
# ------------------------------------------------------------

BUYER_LINE_PATTERNS = [
    r"\b(minist[eè]re\s+de\s+[^.\n]{3,120})",
    r"\b(ville\s+de\s+[^.\n]{3,120})",
    r"\b(centre\s+de\s+services\s+scolaire\s+[^.\n]{3,120})",
    r"\b(commission\s+scolaire\s+[^.\n]{3,120})",
    r"\b(agence\s+[^.\n]{3,120})",
    r"\b(universit[eé]\s+[^.\n]{3,120})",
    r"\b(cisss\s+[^.\n]{3,120})",
    r"\b(ciuss\s+[^.\n]{3,120})",
]

BAD_BUYER_SNIPPETS = {
    "complémentaire (additionnel)",
    "complementaire (additionnel)",
    "essentiel (obligatoire)",
    "obligatoire",
    "additionnel",
    "ministeres-organismes/",
    "cybersecurite-",
}


def _pick_buyer(text: str) -> Optional[str]:
    low = text.lower()

    # Priority 1: look for explicit labelled blocks
    anchors = ["organisme", "client", "propriétaire", "donneur d'ouvrage", "acheteur", "buyer"]
    for a in anchors:
        idx = low.find(a)
        if idx != -1:
            window = text[max(0, idx - 200): min(len(text), idx + 800)]
            # try to find a good looking line near anchor
            for line in window.splitlines():
                l = _normalize_spaces(line)
                ll = l.lower()
                if len(l) < 6 or len(l) > 140:
                    continue
                if any(b in ll for b in BAD_BUYER_SNIPPETS):
                    continue
                if re.search(r"https?://", ll):
                    continue
                # pick lines that resemble org names
                if re.search(r"(minist[eè]re|ville|centre|commission|gouvernement|universit[eé]|agence|direction)", ll):
                    return l

    # Priority 2: pattern-based global scan (first ~40k chars)
    sample = text[:40000]
    low_sample = sample.lower()

    for pat in BUYER_LINE_PATTERNS:
        m = re.search(pat, low_sample, flags=re.IGNORECASE)
        if m:
            cand = _normalize_spaces(m.group(1))
            if cand and len(cand) <= 140 and cand.lower() not in BAD_BUYER_SNIPPETS:
                return cand

    return None


def _pick_estimated_value(text: str) -> Optional[str]:
    """
    Attempts to find budget/estimated value by searching around money anchors.
    """
    low = text.lower()
    anchors = [
        "valeur estim", "valeur approximative", "budget", "montant", "plafond",
        "estimated value", "budgetary", "maximum amount", "ceiling",
    ]
    for a in anchors:
        idx = low.find(a)
        if idx != -1:
            window = text[max(0, idx - 200): min(len(text), idx + 1200)]
            # Try $ 12,345.67 or 12 345,67 $ or 12 345 CAD
            money = re.findall(
                r"(?i)\b(\$?\s*\d[\d\s.,]{1,18}\s*(?:\$|cad|c\$|dollars)?)\b",
                window,
            )
            for m in money:
                s = _normalize_spaces(m)
                # must have a currency hint
                if not re.search(r"(?i)\$|cad|c\$|dollar", s):
                    continue

                # Extract numeric
                num = re.sub(r"(?i)[^\d.,]", "", s)
                num = num.replace(" ", "")
                # heuristics for separators
                if num.count(",") > 0 and num.count(".") == 0:
                    # could be decimal comma OR thousands commas; assume thousands commas if 3-digit groups
                    pass
                # keep only digits
                digits = re.sub(r"[^\d]", "", num)
                if not digits:
                    continue
                try:
                    val = int(digits)
                except Exception:
                    continue

                # sanity (avoid nonsense extremely small amounts and crazy huge)
                if val < 500:  # 92 CAD false positives etc.
                    continue
                if val > 5_000_000_000:
                    continue

                # keep currency format
                if "cad" in s.lower() or "c$" in s.lower():
                    return f"{val} CAD"
                if "$" in s:
                    return f"{val} CAD"
                return f"{val} CAD"

    return None


# ------------------------------------------------------------
# Extract lists in sections: mandatory req / deliverables / criteria
# ------------------------------------------------------------

def _extract_list_under_heading(text: str, headings: List[str], max_lines: int = 80) -> List[str]:
    lines = [l.rstrip() for l in text.splitlines()]
    low = [l.lower().strip() for l in lines]

    start = -1
    for i, ll in enumerate(low):
        if any(h in ll for h in headings):
            start = i
            break
    if start == -1:
        return []

    items: List[str] = []
    for j in range(start + 1, min(len(lines), start + 1 + max_lines)):
        raw = lines[j].strip()
        if not raw:
            if items:
                break
            continue

        # Stop if another big heading starts
        if re.match(r"^[A-ZÉÈÀÙÂÊÎÔÛ0-9][A-ZÉÈÀÙÂÊÎÔÛ\s\-]{10,}$", raw):
            break

        # bullet / numbering
        if re.match(r"^(\-|\•|\*|\d+[\.\)])\s+", raw):
            items.append(_normalize_spaces(re.sub(r"^(\-|\•|\*|\d+[\.\)])\s+", "", raw))[:350])
        elif items and len(raw) < 220:
            # continuation line
            items[-1] = _normalize_spaces(items[-1] + " " + raw)[:420]
        else:
            # try to capture short meaningful lines anyway (common in PDFs)
            if 30 <= len(raw) <= 220 and any(k in raw.lower() for k in ["%", "points", "pond", "poids", "crit", "livr"]):
                items.append(_normalize_spaces(raw)[:350])

    # de-dup
    out, seen = [], set()
    for x in items:
        k = x.lower()
        if k not in seen:
            out.append(x)
            seen.add(k)
    return out[:30]


def extract_deliverables(text: str) -> List[str]:
    return _extract_list_under_heading(
        text,
        ["livrables", "produits livrables", "deliverables", "rapports", "documentation", "matériel livré", "materiel livre"],
    )


def extract_evaluation_criteria(text: str) -> List[str]:
    crit = _extract_list_under_heading(
        text,
        ["critères d’évaluation", "criteres d'evaluation", "critères d'évaluation", "évaluation", "evaluation", "grille d’évaluation", "grille d'évaluation", "pondération", "ponderation", "weighting"],
    )

    # prioritize entries with weights/%
    pct = [c for c in crit if re.search(r"\b\d{1,3}\s*%|\bpond|\bpoids|\bpoints\b", c.lower())]
    rest = [c for c in crit if c not in pct]
    return (pct + rest)[:30]


def extract_mandatory_requirements(text: str) -> List[str]:
    """
    For table-like docs where a row ends with "Essentiel (obligatoire)",
    capture the likely description line(s) right before it.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out: List[str] = []

    for i, l in enumerate(lines):
        low = l.lower()
        if "essentiel" in low and "oblig" in low:
            prev = lines[i - 1] if i - 1 >= 0 else ""
            prev2 = lines[i - 2] if i - 2 >= 0 else ""
            cand = prev
            if len(prev) < 50 and prev2 and len(prev2) < 250:
                cand = prev2 + " " + prev
            cand = _normalize_spaces(cand)
            if cand and 20 <= len(cand) <= 450:
                out.append(cand[:450])

    # fallback: common requirement lines with "doit/must/shall" and "obligatoire"
    if not out:
        for l in lines:
            low = l.lower()
            if ("obligatoire" in low or "must" in low or "shall" in low) and ("doit" in low or "must" in low or "shall" in low):
                if 30 <= len(l) <= 280:
                    out.append(_normalize_spaces(l)[:450])

    uniq, seen = [], set()
    for x in out:
        k = x.lower()
        if k not in seen:
            uniq.append(x)
            seen.add(k)
    return uniq[:40]


# ------------------------------------------------------------
# Core parse_fields
# ------------------------------------------------------------

def parse_fields(text: str) -> Dict[str, Any]:
    """
    Returns fields extracted from PDF text only.
    """
    closing_date = _pick_closing_date(text)
    buyer = _pick_buyer(text)
    estimated_value = _pick_estimated_value(text)

    return {
        "closing_date": closing_date,
        "buyer": buyer,
        "estimated_value": estimated_value,
    }


# ------------------------------------------------------------
# DB enrichment (ao.db)
# ------------------------------------------------------------

def _db_get_tender_by_id(tender_id: int) -> Dict[str, Any]:
    """
    Best-effort: tries to read tender fields from SQLite ao.db.
    Returns {} if db not available or no table/record.
    """
    if tender_id is None:
        return {}
    if not AO_DB_PATH.exists():
        return {}

    # We don't want hard coupling to schema changes. We'll attempt common column names.
    possible_tables = ["tenders", "ao", "ao_tenders", "tender"]
    possible_cols = [
        "id", "title", "url", "portal_name", "published_at", "buyer", "country", "region"
    ]

    try:
        con = sqlite3.connect(str(AO_DB_PATH))
        con.row_factory = sqlite3.Row
    except Exception:
        return {}

    try:
        cur = con.cursor()
        tables = [r["name"] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        table = next((t for t in possible_tables if t in tables), None)
        if not table:
            return {}

        # Determine which columns exist
        cols = [r["name"] for r in cur.execute(f"PRAGMA table_info({table});").fetchall()]
        wanted = [c for c in possible_cols if c in cols]
        if "id" not in cols:
            return {}

        sel = ", ".join(wanted) if wanted else "*"
        row = cur.execute(f"SELECT {sel} FROM {table} WHERE id = ?", (tender_id,)).fetchone()
        if not row:
            return {}

        d = dict(row)
        # normalize keys we rely on
        out = {
            "title": d.get("title"),
            "url": d.get("url"),
            "portal_name": d.get("portal_name") or d.get("source"),
            "published_at": d.get("published_at"),
            "buyer": d.get("buyer"),
            "country": d.get("country"),
            "region": d.get("region"),
        }
        return {k: v for k, v in out.items() if v not in (None, "", "null")}
    except Exception:
        return {}
    finally:
        try:
            con.close()
        except Exception:
            pass


# ------------------------------------------------------------
# Summary, confidence, next actions
# ------------------------------------------------------------

def build_summary(text_len: int, pdf_fields: Dict[str, Any], db_fields: Dict[str, Any]) -> str:
    pdf_keys = [k for k, v in pdf_fields.items() if v not in (None, "", [], {}) and k not in ("mandatory_requirements", "deliverables", "evaluation_criteria", "key_dates")]
    db_keys = [k for k, v in db_fields.items() if v not in (None, "", [], {})]

    parts = [f"Texte extrait ({text_len} caractères)."]
    parts.append("PDF: " + (", ".join(pdf_keys) if pdf_keys else "aucun champ fiable détecté"))
    if db_keys:
        parts.append("DB: " + ", ".join(sorted(set(db_keys))))
    return " ".join(parts)


def compute_confidence(text_len: int, extracted_fields: Dict[str, Any]) -> float:
    score = 0.25
    if text_len > 20_000:
        score += 0.20
    if text_len > 80_000:
        score += 0.15

    # core fields
    if extracted_fields.get("closing_date"):
        score += 0.12
    if extracted_fields.get("buyer"):
        score += 0.12
    if extracted_fields.get("estimated_value"):
        score += 0.10

    # structure fields
    if extracted_fields.get("mandatory_requirements"):
        score += 0.08
    if extracted_fields.get("deliverables"):
        score += 0.06
    if extracted_fields.get("evaluation_criteria"):
        score += 0.06

    return float(max(0.2, min(score, 0.95)))


def build_next_actions(extracted_fields: Dict[str, Any]) -> List[str]:
    actions: List[str] = []

    kd = extracted_fields.get("key_dates") or {}
    if kd.get("closing_date"):
        actions.append(f"Valider la date de clôture ({kd.get('closing_date')}) dans le document")
    else:
        actions.append("Extraire les dates clés (clôture / visite / questions)")

    if not extracted_fields.get("mandatory_requirements"):
        actions.append("Identifier les exigences obligatoires")

    if not extracted_fields.get("deliverables"):
        actions.append("Lister les livrables + critères d’évaluation")
    else:
        # even if deliverables exist, criteria may not
        if not extracted_fields.get("evaluation_criteria"):
            actions.append("Lister les critères d’évaluation et la pondération")

    if not extracted_fields.get("buyer"):
        actions.append("Identifier l’organisme acheteur dans le cahier")

    if not extracted_fields.get("estimated_value"):
        actions.append("Chercher la valeur estimée / budget / plafond (si présent)")

    # de-dup
    out, seen = [], set()
    for a in actions:
        if a not in seen:
            out.append(a)
            seen.add(a)
    return out


# ------------------------------------------------------------
# HTML Report rendering
# ------------------------------------------------------------

def _html_escape(s: Any) -> str:
    s = "" if s is None else str(s)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_report_html(analysis: Dict[str, Any]) -> str:
    result = analysis.get("result", {})
    fields = result.get("extracted_fields", {}) or {}
    title = fields.get("title") or analysis.get("db_enriched", {}).get("title") or "Rapport d’analyse AO"

    key_dates = fields.get("key_dates") or {}
    mandatory = fields.get("mandatory_requirements") or []
    deliverables = fields.get("deliverables") or []
    criteria = fields.get("evaluation_criteria") or []

    def li(items: List[str]) -> str:
        if not items:
            return '<div class="muted">Non détecté.</div>'
        return "<ul>" + "".join(f"<li>{_html_escape(x)}</li>" for x in items) + "</ul>"

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{_html_escape(title)}</title>
  <style>
    :root {{
      --bg: #0b1220;
      --card: rgba(255,255,255,.06);
      --border: rgba(255,255,255,.12);
      --text: rgba(255,255,255,.92);
      --muted: rgba(255,255,255,.65);
      --accent: #7dd3fc;
      --good: #86efac;
      --warn: #fde68a;
    }}
    *{{box-sizing:border-box}}
    body {{
      margin:0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
      background: radial-gradient(1200px 700px at 20% -10%, rgba(125,211,252,.20), transparent 60%),
                  radial-gradient(900px 600px at 110% 0%, rgba(134,239,172,.12), transparent 55%),
                  var(--bg);
      color: var(--text);
      padding: 28px;
    }}
    .wrap {{ max-width: 980px; margin: 0 auto; }}
    .top {{
      display:flex; gap:16px; align-items:flex-start; justify-content:space-between; flex-wrap:wrap;
      margin-bottom: 18px;
    }}
    .h1 {{ font-size: 22px; font-weight: 800; letter-spacing: .2px; margin: 0; }}
    .badge {{
      display:inline-flex; align-items:center; gap:8px;
      padding: 8px 12px; border: 1px solid var(--border); border-radius: 999px;
      background: rgba(255,255,255,.04);
      font-size: 13px; color: var(--muted);
    }}
    .grid {{
      display:grid; grid-template-columns: 1fr 1fr;
      gap: 14px;
    }}
    @media (max-width: 880px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px 14px;
      box-shadow: 0 10px 30px rgba(0,0,0,.25);
      backdrop-filter: blur(10px);
    }}
    .card h2 {{
      margin: 0 0 10px 0;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: .12em;
      color: rgba(255,255,255,.80);
    }}
    .kv {{ display:grid; grid-template-columns: 180px 1fr; gap: 8px 14px; }}
    .k {{ color: var(--muted); font-size: 13px; }}
    .v {{ font-size: 13px; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    ul {{ margin: 8px 0 0 18px; padding: 0; }}
    li {{ margin: 6px 0; color: rgba(255,255,255,.85); font-size: 13px; line-height: 1.35; }}
    .muted {{ color: var(--muted); font-size: 13px; }}
    .bar {{
      height: 8px; background: rgba(255,255,255,.08);
      border: 1px solid var(--border); border-radius: 999px;
      overflow: hidden; margin-top: 8px;
    }}
    .fill {{
      height: 100%;
      width: {int((result.get("confidence") or 0.0) * 100)}%;
      background: linear-gradient(90deg, rgba(125,211,252,.85), rgba(134,239,172,.85));
    }}
    .row {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
    .pill {{
      padding: 6px 10px; border: 1px solid var(--border);
      border-radius: 999px; background: rgba(255,255,255,.04);
      font-size: 12px; color: rgba(255,255,255,.8);
    }}
    .actions a {{
      display:inline-block; margin-right: 10px; margin-top: 8px;
      padding: 8px 12px; border-radius: 12px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,.04);
      font-size: 13px;
    }}
  </style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div>
      <h1 class="h1">{_html_escape(title)}</h1>
      <div class="muted" style="margin-top:6px;">Analysis ID: {_html_escape(analysis.get("analysis_id"))} · {_html_escape(analysis.get("created_at"))}</div>
    </div>
    <div class="badge">
      <span>Confiance</span>
      <strong style="color: var(--good);">{_html_escape(result.get("confidence"))}</strong>
      <div class="bar" style="width:120px;"><div class="fill"></div></div>
    </div>
  </div>

  <div class="card" style="margin-bottom:14px;">
    <h2>Résumé</h2>
    <div class="muted">{_html_escape(result.get("summary"))}</div>
    <div class="actions">
      <a href="/api/ai/report/docx/{_html_escape(analysis.get("analysis_id"))}">Télécharger Word (DOCX)</a>
      <a href="/api/ai/report/pdf/{_html_escape(analysis.get("analysis_id"))}">Télécharger PDF</a>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <h2>Informations</h2>
      <div class="kv">
        <div class="k">Portail</div><div class="v">{_html_escape(fields.get("portal_name"))}</div>
        <div class="k">Publication</div><div class="v">{_html_escape(fields.get("published_at"))}</div>
        <div class="k">Acheteur</div><div class="v">{_html_escape(fields.get("buyer"))}</div>
        <div class="k">Valeur estimée</div><div class="v">{_html_escape(fields.get("estimated_value"))}</div>
        <div class="k">URL</div><div class="v"><a href="{_html_escape(fields.get("url") or "")}">{_html_escape(fields.get("url") or "")}</a></div>
      </div>
    </div>

    <div class="card">
      <h2>Dates clés</h2>
      <div class="kv">
        <div class="k">Clôture</div><div class="v">{_html_escape(key_dates.get("closing_date"))}</div>
        <div class="k">Questions</div><div class="v">{_html_escape(key_dates.get("questions_deadline"))}</div>
        <div class="k">Visite</div><div class="v">{_html_escape(key_dates.get("site_visit_date"))}</div>
        <div class="k">Addenda</div><div class="v">{_html_escape(key_dates.get("addenda_deadline"))}</div>
        <div class="k">Ouverture</div><div class="v">{_html_escape(key_dates.get("opening_date"))}</div>
      </div>
    </div>

    <div class="card">
      <h2>Exigences obligatoires (détectées)</h2>
      {li(mandatory)}
    </div>

    <div class="card">
      <h2>Livrables</h2>
      {li(deliverables)}

      <h2 style="margin-top:14px;">Critères d’évaluation</h2>
      {li(criteria)}
    </div>

    <div class="card" style="grid-column: 1 / -1;">
      <h2>Prochaines actions</h2>
      {li(result.get("next_actions") or [])}
    </div>
  </div>
</div>
</body>
</html>
"""


# ------------------------------------------------------------
# DOCX / PDF generation
# ------------------------------------------------------------

def _analysis_to_plain_sections(analysis: Dict[str, Any]) -> Dict[str, Any]:
    result = analysis.get("result", {}) or {}
    fields = result.get("extracted_fields", {}) or {}

    return {
        "title": fields.get("title") or "Rapport d’analyse AO",
        "summary": result.get("summary"),
        "confidence": result.get("confidence"),
        "fields": fields,
        "next_actions": result.get("next_actions") or [],
    }


def render_docx_bytes(analysis: Dict[str, Any]) -> bytes:
    try:
        from docx import Document  # python-docx
    except Exception as e:
        raise HTTPException(
            status_code=501,
            detail=f"Export DOCX indisponible (python-docx non installé). Installe: pip install python-docx. Détails: {e}",
        )

    s = _analysis_to_plain_sections(analysis)
    fields = s["fields"]
    kd = fields.get("key_dates") or {}

    doc = Document()
    doc.add_heading(str(s["title"]), level=0)

    doc.add_paragraph(f"Confiance: {s['confidence']}")
    doc.add_paragraph(str(s["summary"] or ""))

    doc.add_heading("Informations", level=1)
    for k in ["portal_name", "published_at", "buyer", "estimated_value", "url"]:
        if fields.get(k) not in (None, "", [], {}):
            doc.add_paragraph(f"{k}: {fields.get(k)}")

    doc.add_heading("Dates clés", level=1)
    for k in ["closing_date", "questions_deadline", "site_visit_date", "addenda_deadline", "opening_date"]:
        v = kd.get(k)
        doc.add_paragraph(f"{k}: {v}")

    doc.add_heading("Exigences obligatoires", level=1)
    for x in (fields.get("mandatory_requirements") or []):
        doc.add_paragraph(str(x), style="List Bullet")

    doc.add_heading("Livrables", level=1)
    for x in (fields.get("deliverables") or []):
        doc.add_paragraph(str(x), style="List Bullet")

    doc.add_heading("Critères d’évaluation", level=1)
    for x in (fields.get("evaluation_criteria") or []):
        doc.add_paragraph(str(x), style="List Bullet")

    doc.add_heading("Prochaines actions", level=1)
    for x in (s["next_actions"] or []):
        doc.add_paragraph(str(x), style="List Bullet")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def render_pdf_bytes(analysis: Dict[str, Any]) -> bytes:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas
    except Exception as e:
        raise HTTPException(
            status_code=501,
            detail=f"Export PDF indisponible (reportlab non installé). Installe: pip install reportlab. Détails: {e}",
        )

    s = _analysis_to_plain_sections(analysis)
    fields = s["fields"]
    kd = fields.get("key_dates") or {}

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    width, height = LETTER

    def draw_line(txt: str, y: float) -> float:
        txt = str(txt or "")
        # basic wrap
        max_chars = 100
        parts = [txt[i:i+max_chars] for i in range(0, len(txt), max_chars)] or [""]
        for p in parts:
            c.drawString(0.75 * inch, y, p)
            y -= 12
        return y

    y = height - 0.9 * inch
    c.setFont("Helvetica-Bold", 14)
    y = draw_line(s["title"], y)
    c.setFont("Helvetica", 10)
    y = draw_line(f"Confiance: {s['confidence']}", y)
    y = draw_line(s["summary"] or "", y)
    y -= 8

    c.setFont("Helvetica-Bold", 11)
    y = draw_line("Informations", y)
    c.setFont("Helvetica", 10)
    for k in ["portal_name", "published_at", "buyer", "estimated_value", "url"]:
        if fields.get(k) not in (None, "", [], {}):
            y = draw_line(f"{k}: {fields.get(k)}", y)
    y -= 8

    c.setFont("Helvetica-Bold", 11)
    y = draw_line("Dates clés", y)
    c.setFont("Helvetica", 10)
    for k in ["closing_date", "questions_deadline", "site_visit_date", "addenda_deadline", "opening_date"]:
        y = draw_line(f"{k}: {kd.get(k)}", y)
    y -= 8

    def list_block(title: str, items: List[str]) -> None:
        nonlocal y
        c.setFont("Helvetica-Bold", 11)
        y = draw_line(title, y)
        c.setFont("Helvetica", 10)
        if not items:
            y = draw_line("Non détecté.", y)
            y -= 6
            return
        for it in items[:25]:
            y = draw_line(f"- {it}", y)
            if y < 1.0 * inch:
                c.showPage()
                y = height - 0.9 * inch
                c.setFont("Helvetica", 10)
        y -= 8

    list_block("Exigences obligatoires", fields.get("mandatory_requirements") or [])
    list_block("Livrables", fields.get("deliverables") or [])
    list_block("Critères d’évaluation", fields.get("evaluation_criteria") or [])
    list_block("Prochaines actions", s.get("next_actions") or [])

    c.showPage()
    c.save()
    return buf.getvalue()


# ------------------------------------------------------------
# API routes
# ------------------------------------------------------------

@router.post("/analyze")
async def analyze_ao(
    user: AuthenticatedUser = Depends(get_current_user),
    tender_id: Optional[int] = Form(default=None),
    notes: Optional[str] = Form(default=None),
    files: List[UploadFile] = File(...),
) -> Dict[str, Any]:
    if not files:
        raise HTTPException(status_code=422, detail="Aucun fichier reçu.")

    # 1) Extract text for each PDF
    combined_parts: List[str] = []
    file_meta: List[Dict[str, Any]] = []

    for f in files:
        content = await f.read()
        file_meta.append(
            {
                "filename": f.filename,
                "content_type": f.content_type,
                "size_bytes": len(content),
            }
        )

        if (f.content_type or "").lower() != "application/pdf" and not (f.filename or "").lower().endswith(".pdf"):
            raise HTTPException(status_code=422, detail=f"Fichier non-PDF: {f.filename}")

        txt = extract_text_from_pdf(content)
        combined_parts.append(f"\n\n===== FILE: {f.filename} =====\n\n{txt}")

    combined_text = "\n".join(combined_parts).strip()
    text_len = len(combined_text)

    # 2) PDF parsing
    pdf_fields = parse_fields(combined_text)

    # 3) Structured extraction
    key_dates = extract_key_dates(combined_text)
    pdf_fields["closing_date"] = key_dates.get("closing_date") or pdf_fields.get("closing_date")
    mandatory_requirements = extract_mandatory_requirements(combined_text)
    deliverables = extract_deliverables(combined_text)
    evaluation_criteria = extract_evaluation_criteria(combined_text)

    # 4) DB enrichment
    db_enriched = _db_get_tender_by_id(int(tender_id)) if tender_id is not None else {}

    # 5) Decide final extracted fields (prefer DB for stable metadata; prefer PDF for dates/budget/requirements)
    extracted_fields: Dict[str, Any] = {
        "tender_id": tender_id,
        "closing_date": pdf_fields.get("closing_date"),
        "buyer": pdf_fields.get("buyer") or db_enriched.get("buyer"),
        "estimated_value": pdf_fields.get("estimated_value"),
        "title": db_enriched.get("title"),
        "url": db_enriched.get("url"),
        "portal_name": db_enriched.get("portal_name"),
        "published_at": db_enriched.get("published_at"),
        "country": db_enriched.get("country"),
        "region": db_enriched.get("region"),
        "key_dates": key_dates,
        "mandatory_requirements": mandatory_requirements,
        "deliverables": deliverables,
        "evaluation_criteria": evaluation_criteria,
    }
    extracted_fields = {k: v for k, v in extracted_fields.items() if v not in ("", None)}

    # 6) Summary + actions + confidence
    summary = build_summary(text_len=text_len, pdf_fields=pdf_fields, db_fields=db_enriched)
    confidence = compute_confidence(text_len=text_len, extracted_fields=extracted_fields)
    next_actions = build_next_actions(extracted_fields)

    analysis_id = f"ana_{uuid.uuid4().hex[:12]}"
    created_at = _utc_iso()

    payload: Dict[str, Any] = {
        "status": "ok",
        "analysis_id": analysis_id,
        "created_at": created_at,
        "inputs": {
            "tender_id": tender_id,
            "notes": notes,
            "file_count": len(files),
            "files": file_meta,
        },
        "result": {
            "summary": summary,
            "extracted_fields": extracted_fields,
            "next_actions": next_actions,
            "confidence": round(confidence, 2),
            "debug": {
                "text_chars": text_len,
                "text_sample": combined_text[:1200],
            },
        },
        "user": user.profile.model_dump(),
        "report_urls": {
            "html": f"/api/ai/report/html/{analysis_id}",
            "docx": f"/api/ai/report/docx/{analysis_id}",
            "pdf": f"/api/ai/report/pdf/{analysis_id}",
        },
        # internal cache
        "db_enriched": db_enriched,
    }

    ANALYSES[analysis_id] = payload
    return payload


@router.get("/report/html/{analysis_id}", response_class=HTMLResponse)
def report_html(analysis_id: str, user: AuthenticatedUser = Depends(get_current_user)) -> HTMLResponse:
    analysis = ANALYSES.get(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis introuvable (serveur redémarré ?). Relance l'analyse.")
    html = render_report_html(analysis)
    return HTMLResponse(content=html, status_code=200)


@router.get("/report/docx/{analysis_id}")
def report_docx(analysis_id: str, user: AuthenticatedUser = Depends(get_current_user)) -> StreamingResponse:
    analysis = ANALYSES.get(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis introuvable (serveur redémarré ?). Relance l'analyse.")

    b = render_docx_bytes(analysis)
    title = _safe_filename((analysis.get("result", {}).get("extracted_fields", {}) or {}).get("title") or analysis_id)
    filename = f"{title}__{analysis_id}.docx"
    return StreamingResponse(
        io.BytesIO(b),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/report/pdf/{analysis_id}")
def report_pdf(analysis_id: str, user: AuthenticatedUser = Depends(get_current_user)) -> StreamingResponse:
    analysis = ANALYSES.get(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis introuvable (serveur redémarré ?). Relance l'analyse.")

    b = render_pdf_bytes(analysis)
    title = _safe_filename((analysis.get("result", {}).get("extracted_fields", {}) or {}).get("title") or analysis_id)
    filename = f"{title}__{analysis_id}.pdf"
    return StreamingResponse(
        io.BytesIO(b),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
