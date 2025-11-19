#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, csv, sqlite3
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "ao.db")
CSV_PATH = os.path.join(ROOT, "v1_stable", "ao_output_v1.csv")

# === ALIAS mis à jour (FR + EN) ===
COL_ALIAS = {
    "source": ["source", "source_domain", "domain"],  # si dispo
    "portal_name": ["portal_name", "portal", "source_name", "plateforme", "plateforme "],
    "buyer": ["buyer", "acheteur", "acheteur_nom"],
    "title": ["title", "titre", "ao_title"],
    "url": ["url", "link", "href", "lien"],
    "published_at": [
        "published_at", "date", "pub_date", "published", "date de publication", "date de publication "
    ],
    "country": ["country", "pays"],
    "region": ["region", "province", "state"],
}

NEEDED_FOR_ROW = ["title", "url"]

def sniff_dialect(fp, sample_size=4096):
    sample = fp.read(sample_size); fp.seek(0)
    try:
        return csv.Sniffer().sniff(sample, delimiters=[",",";","\t","|"])
    except csv.Error:
        class Simple(csv.Dialect):
            delimiter = ","; quotechar = '"'; doublequote=True
            skipinitialspace=True; lineterminator="\n"; quoting=csv.QUOTE_MINIMAL
        return Simple

def norm_header(h:str) -> str:
    return (h or "").strip().lower().replace("\ufeff","")

def build_header_map(headers):
    norm = [norm_header(h) for h in headers]
    hmap = {}
    for target, aliases in COL_ALIAS.items():
        for i, h in enumerate(norm):
            if h in aliases:
                hmap[target] = i; break
    return hmap

def normalize_date(s):
    s = (s or "").strip()
    if not s: return ""
    for fmt in ("%Y-%m-%d","%Y/%m/%d","%d/%m/%Y","%m/%d/%Y",
                "%Y-%m-%dT%H:%M:%S","%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s

def ensure_indexes(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tenders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            portal_name TEXT,
            buyer TEXT,
            title TEXT,
            url TEXT UNIQUE,
            published_at TEXT,
            country TEXT,
            region TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tenders_url ON tenders(url)")

def upsert_row(cur, row):
    cur.execute("""
        UPDATE tenders
           SET source=?, portal_name=?, buyer=?, title=?, published_at=?, country=?, region=?
         WHERE url=?
    """, (row.get("source",""), row.get("portal_name",""), row.get("buyer",""),
          row.get("title",""), row.get("published_at",""), row.get("country",""),
          row.get("region",""), row.get("url","")))
    if cur.rowcount == 0:
        cur.execute("""
            INSERT INTO tenders (source, portal_name, buyer, title, url, published_at, country, region)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (row.get("source",""), row.get("portal_name",""), row.get("buyer",""),
              row.get("title",""), row.get("url",""), row.get("published_at",""),
              row.get("country",""), row.get("region","")))
        return "insert"
    return "update"

def main():
    if not os.path.exists(CSV_PATH):
        print(f"[sync] Fichier introuvable: {CSV_PATH}"); return

    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    ensure_indexes(cur)

    total=ins=upd=skipped=0

    with open(CSV_PATH, "r", encoding="utf-8", newline="") as fp:
        dialect = sniff_dialect(fp)
        reader = csv.reader(fp, dialect)
        try:
            headers = next(reader)
        except StopIteration:
            print("[sync] CSV vide"); return

        hmap = build_header_map(headers)
        missing = [k for k in NEEDED_FOR_ROW if k not in hmap]
        if missing:
            print(f"[sync] Colonnes essentielles manquantes dans le CSV: {missing}")
            print(f"[sync] En-têtes détectés: {headers}")
            return

        for raw in reader:
            total += 1
            row = {}
            for key in COL_ALIAS.keys():
                if key in hmap and hmap[key] < len(raw):
                    row[key] = (raw[hmap[key]] or "").strip()
                else:
                    row[key] = ""

            # Si 'source' vide, reprendre la plateforme
            if not row.get("source") and row.get("portal_name"):
                row["source"] = row["portal_name"]

            row["published_at"] = normalize_date(row.get("published_at",""))

            if any(not row.get(k) for k in NEEDED_FOR_ROW):
                skipped += 1; continue

            try:
                kind = upsert_row(cur, row)
                ins += (kind == "insert"); upd += (kind == "update")
            except sqlite3.IntegrityError:
                upd += 1
            except Exception:
                skipped += 1

    conn.commit(); conn.close()
    print(f"[sync] Traité: {total} | insérés: {ins} | mis à jour: {upd} | ignorés: {skipped}")

if __name__ == "__main__":
    main()
