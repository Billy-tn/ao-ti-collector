import argparse
import csv
import sqlite3
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "ao.db"
CSV_PATH = ROOT_DIR / "v1_stable" / "ao_output_v1.csv"


def main(*, dry_run: bool = False, csv_path: Path | None = None, db_path: Path | None = None) -> None:
    csv_path = csv_path or CSV_PATH
    db_path = db_path or DB_PATH

    if not csv_path.exists():
        raise SystemExit(f"Fichier CSV introuvable: {csv_path}")

    if not db_path.exists():
        raise SystemExit(f"Base SQLite introuvable: {db_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    if not dry_run:
        # On repart propre sur la table tenders (les autres tables restent intactes)
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
    with csv_path.open("r", encoding="utf-8") as f:
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

    if rows and not dry_run:
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

    if not dry_run:
        conn.commit()
        conn.close()
        print(f"Importé {len(rows)} lignes depuis {csv_path.name} dans la table 'tenders'.")
    else:
        conn.close()
        print(f"[dry-run] {len(rows)} lignes prêtes à être importées depuis {csv_path.name}. Aucun changement appliqué.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Importer CSV dans la table tenders")
    parser.add_argument("--dry-run", action="store_true", help="Ne pas écrire dans la base (aucun DROP/INSERT/COMMIT)")
    parser.add_argument("--csv", type=str, help="Chemin vers le CSV (optionnel)")
    parser.add_argument("--db", type=str, help="Chemin vers la DB SQLite (optionnel)")
    args = parser.parse_args()

    main(
        dry_run=args.dry_run,
        csv_path=Path(args.csv) if args.csv else None,
        db_path=Path(args.db) if args.db else None,
    )
