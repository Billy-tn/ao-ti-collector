import csv
import sqlite3
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "ao.db"
CSV_PATH = ROOT_DIR / "v1_stable" / "ao_output_v1.csv"


def main() -> None:
    if not CSV_PATH.exists():
        raise SystemExit(f"Fichier CSV introuvable: {CSV_PATH}")

    if not DB_PATH.exists():
        raise SystemExit(f"Base SQLite introuvable: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # On repart propre sur la table tenders
    # (les autres tables restent intactes)
    cur.execute("DROP TABLE IF EXISTS tenders;")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tenders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            title TEXT,
            url TEXT,
            published_at TEXT,
            country TEXT,
            region TEXT,
            portal_name TEXT,
            matched_keywords TEXT,
            raw_summary TEXT,
            source_domain TEXT,
            confidence REAL,
            ocid TEXT,
            buyer TEXT
        );
        """
    )

    rows = []
    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            confidence = None
            if r.get("confidence") not in (None, "", "NULL", "null"):
                try:
                    confidence = float(r["confidence"])
                except ValueError:
                    confidence = None

            rows.append(
                (
                    r.get("source", ""),
                    r.get("title", ""),
                    r.get("url", ""),
                    r.get("published_at", ""),
                    r.get("country", ""),
                    r.get("region", ""),
                    r.get("portal_name", ""),
                    r.get("matched_keywords", ""),
                    r.get("raw_summary", ""),
                    r.get("source_domain", ""),
                    confidence,
                    r.get("ocid", ""),
                    r.get("buyer", ""),
                )
            )

    if rows:
        cur.executemany(
            """
            INSERT INTO tenders (
                source,
                title,
                url,
                published_at,
                country,
                region,
                portal_name,
                matched_keywords,
                raw_summary,
                source_domain,
                confidence,
                ocid,
                buyer
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    conn.commit()
    conn.close()

    print(f"Importé {len(rows)} lignes depuis {CSV_PATH.name} dans la table 'tenders'.")


if __name__ == "__main__":
    main()
