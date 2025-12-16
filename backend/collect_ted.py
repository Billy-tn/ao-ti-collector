import json
import math
import re
import sqlite3
import urllib.request
from datetime import datetime, timezone, date, timedelta
from typing import Optional

DB_PATH = "ao.db"
TED_API = "https://api.ted.europa.eu/v3/notices/search"

DEFAULT_TERMS = 'software cloud cyber* ERP CRM "information technology" DevOps data'


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def yyyymmdd_days_ago(days: int) -> str:
    d = date.today() - timedelta(days=days)
    return d.strftime("%Y%m%d")


def ted_search(payload: dict, timeout: int = 60) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        TED_API,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ao-ti-collector/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", errors="replace")
        return json.loads(raw)


def pick_notice_url(notice: dict) -> str:
    links = notice.get("links") or {}
    pdf_links = links.get("pdf") or {}
    xml_links = links.get("xml") or {}

    # PDF préféré (ENG/FRA)
    if isinstance(pdf_links, dict):
        for k in ("ENG", "FRA"):
            if pdf_links.get(k):
                return str(pdf_links[k]).strip()
        if pdf_links:
            return str(next(iter(pdf_links.values()))).strip()

    # sinon XML
    if isinstance(xml_links, dict) and xml_links:
        return str(next(iter(xml_links.values()))).strip()

    return ""


def ensure_indexes(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_tenders_portal_ocid
        ON tenders (portal_name, ocid);
        """
    )
    con.commit()


def upsert_tender(con: sqlite3.Connection, notice: dict) -> bool:
    pub = (notice.get("publication-number") or "").strip()
    if not pub:
        return False

    url = pick_notice_url(notice)
    title = f"TED Notice {pub}"

    # On n'a pas demandé le champ date dans fields, donc on met now()
    published_at = now_iso()

    cur = con.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO tenders
        (source, title, url, published_at, country, region, portal_name,
         matched_keywords, raw_summary, source_domain, confidence, ocid,
         buyer, categorie_principale, score_pertinence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "ted_api",
            title,
            url,
            published_at,
            "EU",
            "EU",
            "TED_EU",
            "",
            json.dumps(notice, ensure_ascii=False)[:4000],
            "ted.europa.eu",
            0.80,
            pub,
            "",
            "",
            0.0,
        ),
    )
    return cur.rowcount == 1


def _build_query(pd_min: str, query: Optional[str], terms: Optional[str]) -> str:
    # Si l'utilisateur fournit une query TED "expert" complète, on la garde
    if query and query.strip():
        return query.strip()

    # Sinon on construit sur FT IN (...)
    t = (terms or DEFAULT_TERMS).strip()
    # petit nettoyage (optionnel)
    t = re.sub(r"\s+", " ", t)

    return f'FT IN ({t}) AND PD >= {pd_min}'


def run(
    total_limit: int = 300,
    per_page: int = 100,
    pd_days: int = 90,
    query: Optional[str] = None,
    limit: Optional[int] = None,          # compat: l'API envoie "limit"
    start_token: Optional[str] = None,    # permet de reprendre une itération TED
    terms: Optional[str] = None,          # override des termes si query n'est pas fournie
) -> dict:
    # compat: si limit est fourni, on le traite comme total_limit
    if limit is not None:
        total_limit = int(limit)

    total_limit = max(1, int(total_limit))
    per_page = max(1, int(per_page))
    per_page = min(100, per_page, total_limit)  # l’API accepte 100 max dans nos tests

    pages = int(math.ceil(total_limit / per_page))
    pd_min = yyyymmdd_days_ago(int(pd_days))

    final_query = _build_query(pd_min=pd_min, query=query, terms=terms)

    con = sqlite3.connect(DB_PATH)
    try:
        ensure_indexes(con)

        inserted = 0
        fetched = 0
        token = start_token
        total_notice_count = None

        for _ in range(pages):
            payload = {
                "query": final_query,
                "fields": ["publication-number", "links"],
                "limit": str(per_page),
                "scope": "ACTIVE",
                "checkQuerySyntax": False,
                "paginationMode": "ITERATION",
            }
            if token:
                payload["iterationNextToken"] = token

            data = ted_search(payload)

            notices = data.get("notices") or []
            total_notice_count = data.get("totalNoticeCount", total_notice_count)
            token = data.get("iterationNextToken")  # next token

            fetched += len(notices)
            for n in notices:
                if upsert_tender(con, n):
                    inserted += 1

            con.commit()

            # stop si plus de token / plus de notices
            if not token or not notices:
                break

        return {
            "portal": "TED_EU",
            "pd_min": pd_min,
            "query": final_query,
            "totalNoticeCount": total_notice_count,
            "fetched": fetched,
            "inserted": inserted,
            "iterationNextToken": token,  # utile si tu veux continuer plus tard
        }
    finally:
        con.close()


def main():
    r = run(total_limit=300, per_page=100, pd_days=90)
    print("TED import done:", json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
