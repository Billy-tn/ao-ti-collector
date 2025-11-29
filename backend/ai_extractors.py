# backend/ai_extractors.py
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple


# -----------------------------
# Helpers dates FR/EN
# -----------------------------

_FR_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}
_EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

DATE_RX_NUM = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
DATE_RX_SLASH = re.compile(r"\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})\b")
DATE_RX_TEXT_FR = re.compile(
    r"\b(\d{1,2})\s+(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s+(\d{4})\b",
    re.IGNORECASE,
)
DATE_RX_TEXT_EN = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),\s*(\d{4})\b",
    re.IGNORECASE,
)

TIME_RX = re.compile(r"\b([01]?\d|2[0-3])[:h]([0-5]\d)\b", re.IGNORECASE)

MONEY_RX = re.compile(
    r"\b(\d{1,3}(?:[ \u00a0.,]\d{3})*(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?)\s*(\$|cad|usd|eur)\b",
    re.IGNORECASE,
)

BULLET_RX = re.compile(r"^\s*(?:[-•\u2022]|\d+[.)])\s+(.+?)\s*$")


def _norm_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _to_iso(y: int, m: int, d: int) -> Optional[str]:
    try:
        return date(y, m, d).isoformat()
    except Exception:
        return None


def _parse_any_date(line: str) -> List[str]:
    """Retourne des dates ISO trouvées dans une ligne."""
    out: List[str] = []

    for m in DATE_RX_NUM.finditer(line):
        iso = _to_iso(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if iso:
            out.append(iso)

    for m in DATE_RX_SLASH.finditer(line):
        d = int(m.group(1))
        mo = int(m.group(2))
        y_raw = m.group(3)
        y = int(y_raw)
        if y < 100:
            y += 2000
        iso = _to_iso(y, mo, d)
        if iso:
            out.append(iso)

    for m in DATE_RX_TEXT_FR.finditer(line):
        d = int(m.group(1))
        mo = _FR_MONTHS.get(m.group(2).lower(), 0)
        y = int(m.group(3))
        iso = _to_iso(y, mo, d)
        if iso:
            out.append(iso)

    for m in DATE_RX_TEXT_EN.finditer(line):
        mo = _EN_MONTHS.get(m.group(1).lower(), 0)
        d = int(m.group(2))
        y = int(m.group(3))
        iso = _to_iso(y, mo, d)
        if iso:
            out.append(iso)

    # unique preserve order
    seen = set()
    uniq = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _guess_event_type(line: str) -> str:
    l = line.lower()
    # clôture / dépôt
    if any(k in l for k in ["clôture", "cloture", "date limite", "dépôt", "depot", "soumission", "remise"]):
        return "closing"
    # questions
    if any(k in l for k in ["question", "questions", "renseignements", "demande d'information", "clarification"]):
        return "questions_deadline"
    # visite
    if any(k in l for k in ["visite", "site", "inspection", "réunion", "reunion", "conférence", "conference", "briefing"]):
        return "visit_or_meeting"
    # ouverture
    if "ouverture" in l:
        return "opening"
    # addenda
    if any(k in l for k in ["addenda", "addendum", "modification", "mise à jour"]):
        return "addendum"
    return "other"


def extract_key_dates(text: str, max_items: int = 20) -> List[Dict[str, str]]:
    """
    Retourne une liste d'événements datés détectés:
    [{date:"YYYY-MM-DD", type:"closing|questions_deadline|...", context:"..."}]
    """
    lines = [ln.strip() for ln in (text or "").splitlines()]
    found: List[Dict[str, str]] = []

    for i, ln in enumerate(lines):
        if not ln:
            continue
        dates = _parse_any_date(ln)
        if not dates:
            continue

        # un peu de contexte : ligne actuelle + voisins
        ctx = _norm_spaces(" ".join([lines[j] for j in range(max(0, i - 1), min(len(lines), i + 2)) if lines[j]]))
        evt_type = _guess_event_type(ctx)

        # essaye de capter l'heure si dispo
        t = TIME_RX.search(ctx)
        time_str = ""
        if t:
            time_str = f"{t.group(1).zfill(2)}:{t.group(2)}"

        for d in dates:
            payload = {"date": d, "type": evt_type, "context": ctx}
            if time_str:
                payload["time"] = time_str
            found.append(payload)

    # de-dup par (date,type,context prefix)
    uniq: List[Dict[str, str]] = []
    seen = set()
    for it in found:
        key = (it.get("date"), it.get("type"), it.get("context", "")[:80])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)

    # Priorise : closing > questions_deadline > visit_or_meeting > opening > addendum > other
    priority = {"closing": 0, "questions_deadline": 1, "visit_or_meeting": 2, "opening": 3, "addendum": 4, "other": 5}
    uniq.sort(key=lambda x: (priority.get(x.get("type", "other"), 9), x.get("date", "9999-12-31")))
    return uniq[:max_items]


# -----------------------------
# Exigences obligatoires
# -----------------------------

MANDATORY_RX = re.compile(r"\b(obligatoire|essentiel|must|mandatory|requis|required|doit|shall)\b", re.IGNORECASE)
ESSENTIAL_CELL_RX = re.compile(r"\bEssentiel\s*\(obligatoire\)\b", re.IGNORECASE)


def extract_mandatory_requirements(text: str, max_items: int = 25) -> List[str]:
    """
    Heuristique :
    - si une ligne contient "Essentiel (obligatoire)" => on récupère la/des lignes juste avant comme texte d'exigence
    - sinon si une ligne contient des mots type "doit/must/obligatoire" => on prend la ligne (ou ses voisins) nettoyée
    """
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    out: List[str] = []

    def push(s: str):
        s = _norm_spaces(s)
        if len(s) < 18:
            return
        if s.lower().startswith("référence") or s.lower().startswith("reference"):
            return
        if s not in out:
            out.append(s)

    for i, ln in enumerate(lines):
        if not ln.strip():
            continue

        if ESSENTIAL_CELL_RX.search(ln):
            # souvent la description est 1-2 lignes avant
            cand = []
            for j in range(i - 1, max(i - 4, -1), -1):
                if lines[j].strip():
                    cand.append(lines[j].strip())
                if len(" ".join(cand)) > 120:
                    break
            cand = list(reversed(cand))
            push(" ".join(cand))
            continue

        if MANDATORY_RX.search(ln):
            # prend ligne + voisin si ça ressemble à une phrase coupée
            chunk = [ln.strip()]
            if i + 1 < len(lines) and lines[i + 1].strip() and len(lines[i + 1].strip()) < 140:
                chunk.append(lines[i + 1].strip())
            push(" ".join(chunk))

    return out[:max_items]


# -----------------------------
# Livrables / critères
# -----------------------------

HEAD_DELIV_RX = re.compile(r"\b(livrables|deliverables|produits livrables)\b", re.IGNORECASE)
HEAD_EVAL_RX = re.compile(r"\b(crit[eè]res d[’']?évaluation|evaluation criteria|pondération|ponderation|grille)\b", re.IGNORECASE)
POINTS_RX = re.compile(r"\b(\d{1,3})\s*(points|pt)\b", re.IGNORECASE)
PCT_RX = re.compile(r"\b(\d{1,3})\s*%\b")


def _collect_bullets(lines: List[str], start_idx: int, max_items: int = 25) -> Tuple[List[str], int]:
    items: List[str] = []
    i = start_idx
    while i < len(lines) and len(items) < max_items:
        ln = lines[i].strip()
        if not ln:
            # stop si on a déjà des items et on rencontre du vide
            if items:
                break
            i += 1
            continue

        # stop si nouveau titre probable
        if len(ln) < 70 and ln.isupper():
            break
        if re.match(r"^[A-Z][A-Za-zÀ-ÿ'’\-\s]{0,60}\s*:\s*$", ln):
            break

        m = BULLET_RX.match(ln)
        if m:
            items.append(_norm_spaces(m.group(1)))
        else:
            # parfois liste sans bullet: on prend si phrase courte
            if items and len(ln) < 140:
                items.append(_norm_spaces(ln))

        i += 1
    # unique
    uniq = []
    seen = set()
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        uniq.append(x)
    return uniq, i


def extract_deliverables(text: str, max_items: int = 20) -> List[str]:
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    # cherche un heading puis récupère les bullets dessous
    for i, ln in enumerate(lines):
        if HEAD_DELIV_RX.search(ln):
            items, _ = _collect_bullets(lines, i + 1, max_items=max_items)
            if items:
                return items
    # fallback : lignes qui contiennent "livrable" + bullet
    out: List[str] = []
    for ln in lines:
        if "livrable" in ln.lower():
            m = BULLET_RX.match(ln.strip())
            if m:
                out.append(_norm_spaces(m.group(1)))
    return out[:max_items]


def extract_evaluation_criteria(text: str, max_items: int = 25) -> List[str]:
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    for i, ln in enumerate(lines):
        if HEAD_EVAL_RX.search(ln):
            items, _ = _collect_bullets(lines, i + 1, max_items=max_items)
            # si pas de bullets, on prend lignes style "X% / Y points"
            if not items:
                items2 = []
                for j in range(i + 1, min(len(lines), i + 80)):
                    l2 = lines[j].strip()
                    if not l2:
                        if items2:
                            break
                        continue
                    if PCT_RX.search(l2) or POINTS_RX.search(l2):
                        items2.append(_norm_spaces(l2))
                items = items2
            if items:
                return items[:max_items]

    # fallback global : récupérer lignes avec % ou points mais qui parlent évaluation
    out: List[str] = []
    for ln in lines:
        l = ln.lower()
        if ("évaluation" in l or "evaluation" in l or "pondération" in l or "ponderation" in l) and (PCT_RX.search(ln) or POINTS_RX.search(ln)):
            out.append(_norm_spaces(ln))
    return out[:max_items]


# -----------------------------
# Budget / valeur estimée
# -----------------------------

BUDGET_CTX_RX = re.compile(r"\b(budget|valeur estim[ée]e|estimate[d]? value|plafond|maximum|enveloppe|montant)\b", re.IGNORECASE)


def extract_budget_candidates(text: str, max_items: int = 10) -> List[Dict[str, str]]:
    lines = [ln.strip() for ln in (text or "").splitlines()]
    out: List[Dict[str, str]] = []

    for i, ln in enumerate(lines):
        if not ln:
            continue
        if not (BUDGET_CTX_RX.search(ln) or MONEY_RX.search(ln)):
            continue
        monies = MONEY_RX.findall(ln)
        if not monies:
            # essaye aussi contexte 1 ligne avant / après
            ctx = " ".join([lines[j] for j in range(max(0, i - 1), min(len(lines), i + 2)) if lines[j]])
            monies = MONEY_RX.findall(ctx)
            if not monies:
                continue
            context = _norm_spaces(ctx)
        else:
            context = _norm_spaces(ln)

        for num, cur in monies[:3]:
            out.append({"amount": _norm_spaces(num), "currency": cur.upper().replace("$", "CAD"), "context": context})

    # uniq par amount+currency+context prefix
    uniq: List[Dict[str, str]] = []
    seen = set()
    for it in out:
        key = (it["amount"], it["currency"], it["context"][:80])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    return uniq[:max_items]


def build_structured_analysis(text: str) -> Dict[str, object]:
    """
    Bundle unique appelé par ai_tools.py
    """
    key_dates = extract_key_dates(text)
    mandatory = extract_mandatory_requirements(text)
    deliverables = extract_deliverables(text)
    eval_criteria = extract_evaluation_criteria(text)
    budget = extract_budget_candidates(text)

    return {
        "key_dates": key_dates,
        "mandatory_requirements": mandatory,
        "deliverables": deliverables,
        "evaluation_criteria": eval_criteria,
        "budget_candidates": budget,
    }
