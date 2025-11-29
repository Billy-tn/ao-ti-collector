# backend/ai_tools.py
from __future__ import annotations

import os
import re
import sqlite3
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, Response

from .auth import AuthenticatedUser, get_current_user, get_current_user_optional

router = APIRouter(prefix="/ai", tags=["ai"])

# In-memory store (dev): analysis_id -> full payload
ANALYSES: Dict[str, Dict[str, Any]] = {}


# ============================================================
# PDF TEXT EXTRACTION (robust, multi-engines)
# ============================================================

def _extract_text_pymupdf(pdf_bytes: bytes) -> str:
    import fitz  # PyMuPDF
    text_parts: List[str] = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        text_parts.append(page.get_text("text") or "")
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
    Try engines in order:
      1) PyMuPDF (fitz)
      2) pdfplumber
      3) pypdf (fallback)
    """
    errors: List[str] = []
    for fn in (_extract_text_pymupdf, _extract_text_pdfplumber, _extract_text_pypdf):
        try:
            txt = fn(pdf_bytes)
            if txt and len(txt.strip()) > 20:
                return txt
        except Exception as e:
            errors.append(f"{fn.__name__}: {e}")

    raise HTTPException(
        status_code=422,
        detail=f"Impossible d'extraire le texte du PDF. Détails: {errors[:3]}",
    )


# ============================================================
# DB ENRICHMENT (fallback)
# ============================================================

def _db_path() -> str:
    # project root default: ao.db
    return os.getenv("AO_DB_PATH", "ao.db")


def _fetch_tender_from_db(tender_id: int) -> Optional[Dict[str, Any]]:
    path = _db_path()
    if not os.path.exists(path):
        return None

    con: Optional[sqlite3.Connection] = None
    try:
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            """
            SELECT
              id,
              title,
              url,
              published_at,
              portal_name,
              buyer,
              source,
              country,
              region
            FROM tenders
            WHERE id = ?
            LIMIT 1
            """,
            (tender_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        return {
            "id": d.get("id"),
            "title": d.get("title"),
            "url": d.get("url"),
            "published_at": d.get("published_at"),
            "portal_name": d.get("portal_name") or d.get("source"),
            "buyer": d.get("buyer"),
            "country": d.get("country"),
            "region": d.get("region"),
        }
    except Exception:
        return None
    finally:
        try:
            if con:
                con.close()
        except Exception:
            pass


# ============================================================
# FIELD PARSING (FR/EN) + anti-faux-positifs
# ============================================================

_FR_MONTHS = {
    "janvier": "01",
    "février": "02",
    "fevrier": "02",
    "mars": "03",
    "avril": "04",
    "mai": "05",
    "juin": "06",
    "juillet": "07",
    "août": "08",
    "aout": "08",
    "septembre": "09",
    "octobre": "10",
    "novembre": "11",
    "décembre": "12",
    "decembre": "12",
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


def _normalize_spaces(s: str) -> str:
    return re.sub(r"[ \t]+", " ", (s or "").strip())


def _to_iso_date(day: str, month: str, year: str) -> str:
    d = day.zfill(2)
    m = month.zfill(2)
    return f"{year}-{m}-{d}"


def _parse_ymd(s: str) -> Optional[date]:
    if not s:
        return None
    s = str(s).strip()
    if len(s) >= 10:
        s = s[:10]
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


def _looks_like_url_fragment(s: str) -> bool:
    low = (s or "").lower()
    return ("http" in low) or ("/" in s) or ("www." in low) or ("." in low and " " not in s)


def _find_date_candidates(text: str) -> List[str]:
    t = text.lower()
    out: List[str] = []

    # 1) YYYY-MM-DD
    for m in re.finditer(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", t):
        year, mm, dd = m.group(1), m.group(2), m.group(3)
        out.append(_to_iso_date(dd, mm, year))

    # 2) DD/MM/YYYY or DD-MM-YYYY
    for m in re.finditer(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", t):
        dd, mm, year = m.group(1), m.group(2), m.group(3)
        out.append(_to_iso_date(dd, mm, year))

    # 3) DD month YYYY (FR/EN)
    for m in re.finditer(r"\b(\d{1,2})\s+([a-zéûôàèîç]+)\s+(20\d{2})\b", t):
        dd, month_name, year = m.group(1), m.group(2), m.group(3)
        if month_name in _FR_MONTHS:
            out.append(_to_iso_date(dd, _FR_MONTHS[month_name], year))
        elif month_name in _EN_MONTHS:
            out.append(_to_iso_date(dd, _EN_MONTHS[month_name], year))

    seen = set()
    uniq: List[str] = []
    for d in out:
        if d not in seen:
            uniq.append(d)
            seen.add(d)
    return uniq


def _date_in_reasonable_range(iso_date: str) -> bool:
    try:
        y = int(iso_date[:4])
    except Exception:
        return False
    now_y = datetime.utcnow().year
    return (now_y - 2) <= y <= (now_y + 3)


# --- buyer filter ---
_BUYER_BAD_WORDS = {
    "complémentaire", "complementaire",
    "additionnel", "additionnelle",
    "essentiel", "obligatoire", "optionnel",
    "classification", "catégorie", "categorie",
    "référence", "reference", "description",
    "exigence", "exigences", "fonctionnelle", "fonctionnelles",
    "solution", "soumissionnaire", "propriétaire", "proprietaire",
}

# IMPORTANT: pas "service" ici (trop générique)
_BUYER_GOOD_HINTS = {
    "minist", "gouvernement", "ville", "municip",
    "centre de services scolaire", "commission scolaire",
    "universit", "cisss", "ciusss", "hôpital", "hopital",
    "société", "societe", "agence",
}

_BUYER_BAD_PHRASES = {
    "de chaque soumission",
    "en réponse à",
    "en reponse a",
    "relatif à",
    "relatif a",
    "relative à",
    "relative a",
}


def _clean_buyer_candidate(s: str) -> str:
    s = _normalize_spaces(s)
    return s.strip(" -–—:;|")


def _is_plausible_buyer(s: str) -> bool:
    if not s:
        return False
    low = s.lower().strip()

    if _looks_like_url_fragment(s):
        return False
    if len(low) < 10:
        return False
    if re.match(r"^(de|du|des|d’|d'|pour|afin)\b", low):
        return False
    if any(w in low for w in _BUYER_BAD_WORDS):
        return False
    if any(p in low for p in _BUYER_BAD_PHRASES):
        return False

    if any(h in low for h in _BUYER_GOOD_HINTS):
        return True
    if re.search(r"\b(ville\s+de|minist[èe]re\s+de|centre\s+de\s+services\s+scolaire)\b", low):
        return True

    return False


def _pick_closing_date(text: str) -> Optional[str]:
    low = text.lower()
    anchors = [
        "date limite",
        "date et heure limites",
        "date de clôture",
        "date de cloture",
        "clôture",
        "cloture",
        "réception des soumissions",
        "reception des soumissions",
        "deadline",
        "closing date",
        "submission deadline",
    ]

    for a in anchors:
        idx = low.find(a)
        if idx != -1:
            window = low[max(0, idx - 250) : min(len(low), idx + 700)]
            cands = _find_date_candidates(window)
            cands = [d for d in cands if _date_in_reasonable_range(d)]
            if cands:
                return cands[0]

    all_dates = _find_date_candidates(low)
    all_dates = [d for d in all_dates if _date_in_reasonable_range(d)]
    return all_dates[0] if all_dates else None


def _pick_buyer(text: str) -> Optional[str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    low_lines = [l.lower() for l in lines]

    keys = [
        "organisme",
        "organisme public",
        "acheteur",
        "client",
        "donneur d'ouvrage",
        "donneur d’ouvrage",
        "autorité contractante",
        "contracting authority",
        "organisation",
    ]

    for i, ll in enumerate(low_lines):
        for k in keys:
            if ll.startswith(k):
                if ":" in lines[i]:
                    val = _clean_buyer_candidate(lines[i].split(":", 1)[1])
                    if _is_plausible_buyer(val):
                        return val[:200]
                if i + 1 < len(lines):
                    nxt = _clean_buyer_candidate(lines[i + 1])
                    if _is_plausible_buyer(nxt):
                        return nxt[:200]

    strong_patterns = [
        r"\b(Minist[èe]re\s+de\s+[^,\n]{6,160})",
        r"\b(Centre\s+de\s+services\s+scolaire[^,\n]{6,160})",
        r"\b(Ville\s+de\s+[^,\n]{2,120})",
        r"\b(Gouvernement\s+du\s+Qu[ée]bec[^,\n]{0,80})",
    ]
    for p in strong_patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            val = _clean_buyer_candidate(m.group(1))
            if _is_plausible_buyer(val):
                return val[:200]

    return None


def _parse_money_candidates(text: str) -> List[str]:
    """
    Règles anti faux-positifs:
      - monnaie explicite ($/CAD/USD) près du nombre, OU
      - mot-clé budget + nombre (>= 1000) + marqueur monnaie dans la fenêtre
    """
    t = text.replace("\u00a0", " ").replace("\u202f", " ")
    low = t.lower()
    cands: List[str] = []

    money_with_cur = re.compile(
        r"\b(?P<num>\d{1,3}(?:[ ,.\u202f]\d{3})+(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?)\s*(?P<cur>\$|cad|c\$|usd)\b",
        flags=re.IGNORECASE,
    )
    for m in money_with_cur.finditer(t):
        cands.append(m.group("num"))

    keywords = [
        "valeur estim",
        "budget",
        "montant",
        "plafond",
        "enveloppe",
        "estimated value",
        "estimate",
    ]
    money_num = re.compile(r"\b(?P<num>\d{1,3}(?:[ ,.\u202f]\d{3})+|\d{4,})(?:[.,]\d{2})?\b")
    for m in money_num.finditer(t):
        start = max(0, m.start() - 80)
        end = min(len(low), m.end() + 80)
        window = low[start:end]
        if any(k in window for k in keywords) and re.search(r"(\$|\bcad\b|\bc\$\b|\busd\b)", window):
            cands.append(m.group("num"))

    out: List[str] = []
    seen = set()
    for x in cands:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def _normalize_money_value(raw: str) -> Optional[float]:
    s = (raw or "").strip()
    if not s:
        return None
    s = s.replace(" ", "").replace("\u202f", "").replace("\t", "")

    # If has ",xx" decimal => comma decimal
    if re.search(r",\d{2}\b", s):
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")

    # handle "12.345.678"
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")

    if s.count(".") > 1 and not re.search(r"\.\d{2}\b", s):
        s = s.replace(".", "")

    if not re.fullmatch(r"\d+(\.\d{1,2})?", s):
        return None

    try:
        return float(s)
    except Exception:
        return None


def _pick_estimated_value(text: str) -> Optional[str]:
    cands = _parse_money_candidates(text)
    if not cands:
        return None

    best: Tuple[float, str] | None = None
    for c in cands:
        val = _normalize_money_value(c)
        if val is None:
            continue
        if val < 1000:
            continue
        if (best is None) or (val > best[0]):
            best = (val, c)

    if not best:
        return None

    normalized = _normalize_money_value(best[1])
    if normalized is None:
        return None

    if float(normalized).is_integer():
        return f"{int(normalized)} CAD"
    return f"{normalized} CAD"


def parse_fields(text: str) -> Dict[str, Any]:
    closing_date = _pick_closing_date(text)
    buyer = _pick_buyer(text)
    estimated_value = _pick_estimated_value(text)

    if closing_date and not _date_in_reasonable_range(closing_date):
        closing_date = None
    if buyer and not _is_plausible_buyer(buyer):
        buyer = None

    return {
        "closing_date": closing_date,
        "buyer": buyer,
        "estimated_value": estimated_value,
    }


def compute_confidence(text_len: int, pdf_fields: Dict[str, Any], db_fields: Dict[str, Any]) -> float:
    c = 0.20
    if text_len >= 500:
        c += 0.25
    if text_len >= 2000:
        c += 0.10

    pdf_hits = sum(1 for k in ("closing_date", "buyer", "estimated_value") if pdf_fields.get(k))
    c += pdf_hits * 0.18

    db_hits = sum(1 for k in ("buyer", "portal_name", "published_at", "url", "title") if db_fields.get(k))
    c += min(0.15, db_hits * 0.03)

    if pdf_hits <= 1:
        c = min(c, 0.60 + min(0.10, db_hits * 0.02))

    return max(0.10, min(0.90, c))


def next_actions_from_fields(fields: Dict[str, Any]) -> List[str]:
    actions = [
        "Identifier les exigences obligatoires",
        "Lister les livrables + critères d’évaluation",
    ]
    if not fields.get("closing_date"):
        actions.insert(0, "Extraire les dates clés (clôture / visite / questions)")
    else:
        actions.insert(0, f"Valider la date de clôture ({fields['closing_date']}) dans le document")

    if not fields.get("buyer"):
        actions.append("Identifier l’organisme acheteur dans le cahier")
    if not fields.get("estimated_value"):
        actions.append("Chercher la valeur estimée / budget / plafond (si présent)")
    return actions


def build_summary(text_len: int, final_fields: Dict[str, Any], db_fields: Dict[str, Any]) -> str:
    found_pdf = [k for k in ("closing_date", "buyer", "estimated_value") if final_fields.get(k)]
    found_db = [k for k in ("title", "portal_name", "published_at", "url", "buyer") if db_fields.get(k)]

    if not found_pdf and not found_db:
        return f"Texte extrait ({text_len} caractères). Aucun champ clé détecté automatiquement."

    bits: List[str] = [f"Texte extrait ({text_len} caractères)."]
    if found_pdf:
        bits.append(f"PDF: {', '.join(found_pdf)}.")
    if found_db:
        bits.append(f"DB: {', '.join(sorted(set(found_db)))}.")
    return " ".join(bits)


def _escape_html(s: Any) -> str:
    s = "" if s is None else str(s)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = s.replace('"', "&quot;").replace("'", "&#39;")
    return s


def _render_report_html(payload: Dict[str, Any]) -> str:
    r = payload.get("result", {}) or {}
    f = (r.get("extracted_fields", {}) or {})
    warnings = r.get("warnings") or []
    next_actions = r.get("next_actions") or []
    inputs = payload.get("inputs", {}) or {}

    title = f.get("title") or f"Analyse {payload.get('analysis_id')}"
    url = f.get("url") or ""

    def row(label: str, val: Any) -> str:
        return f"""
          <div class="row">
            <div class="k">{_escape_html(label)}</div>
            <div class="v">{_escape_html(val) if val else '<span class="muted">—</span>'}</div>
          </div>
        """

    warnings_html = ""
    if warnings:
        warnings_html = "<div class='box warn'><h3>⚠️ Warnings</h3><ul>" + "".join(
            f"<li>{_escape_html(w)}</li>" for w in warnings
        ) + "</ul></div>"

    actions_html = "<ul class='ul'>" + "".join(f"<li>{_escape_html(a)}</li>" for a in next_actions) + "</ul>"

    files_html = "<ul class='ul'>" + "".join(
        f"<li>{_escape_html(x.get('filename'))} <span class='muted'>({x.get('size_bytes')} bytes)</span></li>"
        for x in (inputs.get("files") or [])
    ) + "</ul>"

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{_escape_html(title)}</title>
  <style>
    :root {{
      --bg: #0b1220;
      --card: rgba(255,255,255,.06);
      --border: rgba(255,255,255,.12);
      --text: rgba(255,255,255,.92);
      --muted: rgba(255,255,255,.65);
      --accent: #7dd3fc;
      --warn: #fbbf24;
      --ok: #34d399;
    }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
      background: radial-gradient(1200px 600px at 20% 0%, rgba(125,211,252,.18), transparent 55%),
                  radial-gradient(1200px 600px at 90% 40%, rgba(52,211,153,.12), transparent 55%),
                  var(--bg);
      color: var(--text);
    }}
    .wrap {{ max-width: 980px; margin: 32px auto; padding: 0 16px; }}
    .top {{
      display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center;
      gap: 12px; margin-bottom: 18px;
    }}
    .h1 {{ font-size: 22px; font-weight: 800; letter-spacing: .2px; }}
    .pill {{
      display:inline-flex; align-items:center; gap:8px; padding: 8px 12px;
      border: 1px solid var(--border); background: rgba(255,255,255,.04);
      border-radius: 999px; color: var(--muted); font-size: 13px;
    }}
    .grid {{ display:grid; grid-template-columns: 1.2fr .8fr; gap: 14px; }}
    @media (max-width: 860px) {{ .grid {{ grid-template-columns: 1fr; }} }}
    .card {{
      border: 1px solid var(--border);
      background: var(--card);
      border-radius: 18px;
      padding: 16px;
      box-shadow: 0 12px 30px rgba(0,0,0,.28);
    }}
    .card h2 {{ margin: 0 0 10px; font-size: 16px; }}
    .card h3 {{ margin: 0 0 8px; font-size: 14px; color: var(--muted); font-weight: 700; }}
    .muted {{ color: var(--muted); }}
    .row {{
      display:grid; grid-template-columns: 220px 1fr; gap: 10px;
      padding: 8px 0;
      border-top: 1px dashed rgba(255,255,255,.10);
    }}
    .row:first-of-type {{ border-top: 0; }}
    .k {{ color: var(--muted); font-size: 13px; }}
    .v {{ font-size: 14px; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .box {{
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 12px;
      background: rgba(255,255,255,.035);
      margin-top: 12px;
    }}
    .warn {{ border-color: rgba(251,191,36,.35); }}
    .warn h3 {{ color: var(--warn); }}
    .ul {{ margin: 8px 0 0; padding-left: 18px; }}
    .small {{ font-size: 12px; }}
    .footer {{ margin-top: 12px; color: var(--muted); font-size: 12px; }}
    .btns {{
      display:flex; gap:10px; flex-wrap:wrap; margin-top: 10px;
    }}
    .btn {{
      display:inline-flex; align-items:center; gap:8px;
      padding: 10px 12px; border-radius: 12px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,.05);
      color: var(--text);
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <div class="h1">{_escape_html(title)}</div>
        <div class="muted small">analysis_id: {_escape_html(payload.get("analysis_id"))}</div>
      </div>
      <div class="pill">confidence: <b style="color: var(--ok)">{_escape_html(r.get("confidence"))}</b></div>
    </div>

    <div class="grid">
      <div class="card">
        <h2>📌 Snapshot AO</h2>
        {row("Portail", f.get("portal_name"))}
        {row("Publié le", f.get("published_at"))}
        {row("Acheteur", f.get("buyer"))}
        {row("Date de clôture", f.get("closing_date"))}
        {row("Valeur estimée", f.get("estimated_value"))}
        {row("Tender ID", f.get("tender_id"))}
        <div class="box">
          <h3>Lien</h3>
          <div class="v">{f'<a href="{_escape_html(url)}" target="_blank" rel="noreferrer">{_escape_html(url)}</a>' if url else '<span class="muted">—</span>'}</div>
        </div>

        <div class="box">
          <h3>Résumé</h3>
          <div class="v">{_escape_html(r.get("summary"))}</div>
        </div>

        {warnings_html}

        <div class="box">
          <h3>Next actions</h3>
          {actions_html}
        </div>

        <div class="btns">
          <a class="btn" href="/api/ai/report/docx/{_escape_html(payload.get("analysis_id"))}">⬇️ Télécharger Word</a>
          <a class="btn" href="/api/ai/report/pdf/{_escape_html(payload.get("analysis_id"))}">⬇️ Télécharger PDF</a>
        </div>
      </div>

      <div class="card">
        <h2>📎 Fichiers & Debug</h2>
        <div class="box">
          <h3>Fichiers reçus</h3>
          {files_html}
        </div>

        <div class="box">
          <h3>Champs extraits (JSON)</h3>
          <pre style="white-space: pre-wrap; color: var(--text); margin: 0; font-size: 12px;">{_escape_html(f)}</pre>
        </div>

        <div class="box">
          <h3>Texte (sample)</h3>
          <pre style="white-space: pre-wrap; color: var(--muted); margin: 0; font-size: 12px;">{_escape_html((r.get("debug") or {}).get("text_sample"))}</pre>
        </div>

        <div class="footer">
          Note: rapport généré côté backend (dev). Si le backend redémarre, les rapports en mémoire disparaissent.
        </div>
      </div>
    </div>
  </div>
</body>
</html>"""


# ============================================================
# ROUTES
# ============================================================

@router.post("/analyze")
async def analyze_ao(
    tender_id: Optional[int] = Form(default=None),
    notes: Optional[str] = Form(default=None),
    files: List[UploadFile] = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
):
    analysis_id = f"ana_{uuid.uuid4().hex[:12]}"
    created_at = datetime.utcnow().isoformat() + "Z"

    file_infos: List[Dict[str, Any]] = []
    text_parts: List[str] = []

    for f in files:
        content = await f.read()
        file_infos.append(
            {
                "filename": f.filename,
                "content_type": f.content_type,
                "size_bytes": len(content),
            }
        )

        if (f.content_type != "application/pdf") and (not (f.filename or "").lower().endswith(".pdf")):
            raise HTTPException(status_code=422, detail=f"Fichier non-PDF: {f.filename}")

        text = extract_text_from_pdf(content)
        text_parts.append(text)

    combined_text = "\n\n".join([t for t in text_parts if t]).strip()
    text_len = len(combined_text)

    pdf_fields = parse_fields(combined_text)

    db_enriched: Dict[str, Any] = {}
    if tender_id is not None:
        row = _fetch_tender_from_db(int(tender_id))
        if row:
            db_enriched = {
                "title": row.get("title"),
                "url": row.get("url"),
                "portal_name": row.get("portal_name"),
                "published_at": row.get("published_at"),
                "buyer": row.get("buyer"),
                "country": row.get("country"),
                "region": row.get("region"),
            }

    warnings: List[str] = []

    buyer_final = pdf_fields.get("buyer") or db_enriched.get("buyer")
    closing_final = pdf_fields.get("closing_date")
    value_final = pdf_fields.get("estimated_value")

    # Sanity: closing >= published_at
    pub = _parse_ymd(db_enriched.get("published_at") or "")
    clo = _parse_ymd(closing_final or "")
    if clo and pub and clo < pub:
        warnings.append(
            f"closing_date rejetée ({closing_final}) car antérieure à published_at ({db_enriched.get('published_at')})."
        )
        closing_final = None

    # Sanity buyer
    if buyer_final and not _is_plausible_buyer(str(buyer_final)):
        warnings.append(f"buyer rejeté (faux positif): {str(buyer_final)[:140]}")
        buyer_final = db_enriched.get("buyer")

    extracted_fields: Dict[str, Any] = {
        "tender_id": tender_id,
        "closing_date": closing_final,
        "buyer": buyer_final,
        "estimated_value": value_final,
        # DB fields for display
        "title": db_enriched.get("title"),
        "url": db_enriched.get("url"),
        "portal_name": db_enriched.get("portal_name"),
        "published_at": db_enriched.get("published_at"),
        "country": db_enriched.get("country"),
        "region": db_enriched.get("region"),
    }

    confidence = compute_confidence(text_len=text_len, pdf_fields=pdf_fields, db_fields=db_enriched)

    # ✅ summary basé sur les champs FINALS (et pas le parsed brut)
    final_for_summary = {
        "closing_date": closing_final,
        "buyer": buyer_final,
        "estimated_value": value_final,
    }
    summary = build_summary(text_len=text_len, final_fields=final_for_summary, db_fields=db_enriched)

    result: Dict[str, Any] = {
        "summary": summary,
        "extracted_fields": extracted_fields,
        "next_actions": next_actions_from_fields(extracted_fields),
        "confidence": confidence,
        "warnings": warnings,
        "debug": {
            "text_chars": text_len,
            "text_sample": combined_text[:900],
            "db_enriched": {k: v for k, v in db_enriched.items() if v is not None},
        },
    }

    payload = {
        "status": "ok",
        "analysis_id": analysis_id,
        "created_at": created_at,
        "inputs": {
            "tender_id": tender_id,
            "notes": notes,
            "file_count": len(files),
            "files": file_infos,
        },
        "result": result,
        "user": user.profile.model_dump(),
    }

    # Store for report endpoints (dev)
    ANALYSES[analysis_id] = payload
    return payload


@router.get("/report/html/{analysis_id}", response_class=HTMLResponse)
def report_html(
    analysis_id: str,
    _user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
):
    payload = ANALYSES.get(analysis_id)
    if not payload:
        raise HTTPException(status_code=404, detail="analysis_id introuvable (mémoire vidée ? serveur redémarré ?)")
    html = _render_report_html(payload)
    return HTMLResponse(content=html)


@router.get("/report/docx/{analysis_id}")
def report_docx(
    analysis_id: str,
    _user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
):
    payload = ANALYSES.get(analysis_id)
    if not payload:
        raise HTTPException(status_code=404, detail="analysis_id introuvable (mémoire vidée ? serveur redémarré ? serveur redémarré ?)")
    try:
        from docx import Document
    except Exception:
        raise HTTPException(status_code=500, detail="Dépendance manquante: pip install python-docx")

    r = payload["result"]
    f = r["extracted_fields"]

    doc = Document()
    doc.add_heading(f.get("title") or "Rapport d’analyse AO", level=1)
    doc.add_paragraph(f"analysis_id: {payload.get('analysis_id')}")
    doc.add_paragraph(f"created_at: {payload.get('created_at')}")
    doc.add_paragraph("")

    doc.add_heading("Résumé", level=2)
    doc.add_paragraph(r.get("summary") or "")

    doc.add_heading("Snapshot", level=2)
    for k in ("portal_name", "published_at", "buyer", "closing_date", "estimated_value", "url", "tender_id"):
        doc.add_paragraph(f"{k}: {f.get(k)}")

    warnings = r.get("warnings") or []
    if warnings:
        doc.add_heading("Warnings", level=2)
        for w in warnings:
            doc.add_paragraph(f"- {w}")

    doc.add_heading("Next actions", level=2)
    for a in (r.get("next_actions") or []):
        doc.add_paragraph(f"- {a}")

    # Save to temp file
    tmpdir = tempfile.mkdtemp(prefix="ao_report_")
    path = os.path.join(tmpdir, f"{analysis_id}.docx")
    doc.save(path)

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"ao-report-{analysis_id}.docx",
    )


@router.get("/report/pdf/{analysis_id}")
def report_pdf(
    analysis_id: str,
    _user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
):
    """
    PDF simple via reportlab (pas de rendu CSS complet comme HTML).
    """
    payload = ANALYSES.get(analysis_id)
    if not payload:
        raise HTTPException(status_code=404, detail="analysis_id introuvable (mémoire vidée ? serveur redémarré ?)")
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception:
        raise HTTPException(status_code=500, detail="Dépendance manquante: pip install reportlab")

    r = payload["result"]
    f = r["extracted_fields"]

    tmpdir = tempfile.mkdtemp(prefix="ao_report_pdf_")
    path = os.path.join(tmpdir, f"{analysis_id}.pdf")

    c = canvas.Canvas(path, pagesize=letter)
    width, height = letter

    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, (f.get("title") or "Rapport d’analyse AO")[:95])
    y -= 18

    c.setFont("Helvetica", 9)
    c.drawString(50, y, f"analysis_id: {analysis_id}   created_at: {payload.get('created_at')}")
    y -= 18

    def draw_block(title: str, lines: List[str]) -> None:
        nonlocal y
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, title)
        y -= 14
        c.setFont("Helvetica", 9)
        for ln in lines:
            for chunk in _wrap(ln, 95):
                if y < 60:
                    c.showPage()
                    y = height - 50
                    c.setFont("Helvetica", 9)
                c.drawString(50, y, chunk)
                y -= 12
        y -= 8

    def _wrap(s: str, maxlen: int) -> List[str]:
        s = s or ""
        words = s.split()
        out = []
        cur = ""
        for w in words:
            if len(cur) + len(w) + 1 <= maxlen:
                cur = (cur + " " + w).strip()
            else:
                if cur:
                    out.append(cur)
                cur = w
        if cur:
            out.append(cur)
        return out or [""]

    draw_block("Résumé", [r.get("summary") or ""])
    draw_block(
        "Snapshot",
        [
            f"Portail: {f.get('portal_name')}",
            f"Publié le: {f.get('published_at')}",
            f"Acheteur: {f.get('buyer')}",
            f"Clôture: {f.get('closing_date')}",
            f"Valeur estimée: {f.get('estimated_value')}",
            f"URL: {f.get('url')}",
            f"Tender ID: {f.get('tender_id')}",
        ],
    )

    warnings = r.get("warnings") or []
    if warnings:
        draw_block("Warnings", [f"- {w}" for w in warnings])

    draw_block("Next actions", [f"- {a}" for a in (r.get("next_actions") or [])])

    c.save()

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"ao-report-{analysis_id}.pdf",
    )
