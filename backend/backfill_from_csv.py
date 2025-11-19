# backend/backfill_from_csv.py
import csv, sqlite3, pathlib, datetime as dt

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "ao.db"
CSV = ROOT / "v1_stable" / "ao_output_v1.csv"

EXPECTED_HEADERS = {
    # CSV -> DB
    "source": "source",
    "portal_name": "portal_name",
    "buyer": "buyer",
    "title": "title",
    "url": "url",
    "published_at": "published_at",
    "country": "country",
    "region": "region",
}

def parse_date(s: str) -> str:
    """
    Normalise published_at en ISO (YYYY-MM-DD).
    Accepte ISO, ou formats yyyy-mm-dd hh:mm:ss, etc.
    """
    s = (s or "").strip()
    if not s:
        return ""
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    # Dernier ressort: si déjà ISO-like, renvoyer tel quel
    return s[:10]

def main():
    if not CSV.exists():
        raise SystemExit(f"CSV introuvable: {CSV}")

    con = sqlite3.connect(DB)
    cur = con.cursor()

    # Vérifier colonnes de tenders
    cur.execute("PRAGMA table_info(tenders)")
    cols = [r[1] for r in cur.fetchall()]
    needed = ["id","source","portal_name","buyer","title","url","published_at","country","region"]
    missing = [c for c in needed if c not in cols]
    if missing:
        raise SystemExit(f"Colonnes manquantes dans tenders: {missing}")

    # Purge légère: on remplit proprement (garde les id auto)
    cur.execute("DELETE FROM tenders")
    con.commit()

    inserted = 0
    with CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = [h.strip() for h in reader.fieldnames or []]

        # Mapping CSV réel -> DB (tolérant si l’ordre change)
        # On sait que le CSV v1 contient au moins:
        # source, title, url, published_at, country, region, portal_name, matched_keywords, raw_summary, source_domain, confidence
        def get(row, key):
            return (row.get(key) or "").strip()

        rows = []
        for row in reader:
            db_row = {
                "source":       get(row, "source"),
                "portal_name":  get(row, "portal_name"),
                "buyer":        get(row, "buyer"),
                "title":        get(row, "title"),
                "url":          get(row, "url"),
                "published_at": parse_date(get(row, "published_at")),
                "country":      get(row, "country"),
                "region":       get(row, "region"),
            }
            # On ignore les lignes sans titre OU sans url
            if not db_row["title"] or not db_row["url"]:
                continue
            rows.append(db_row)

        cur.executemany(
            """
            INSERT INTO tenders (source, portal_name, buyer, title, url, published_at, country, region)
            VALUES (:source, :portal_name, :buyer, :title, :url, :published_at, :country, :region)
            """,
            rows,
        )
        inserted = cur.rowcount
        con.commit()

    print(f"Backfill terminé → {inserted} lignes insérées depuis {CSV.name}")

if __name__ == "__main__":
    main()
