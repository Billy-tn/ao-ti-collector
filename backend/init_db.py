from __future__ import annotations

import os
import csv
import sqlite3
from typing import List, Tuple

# Emplacement de la base SQLite
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "ao.db")

# Fichiers d'entrée
PORTALS_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "portals_sources.csv")
AO_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "v1_stable", "ao_output_v1.csv")


def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    return con


def create_tables(con: sqlite3.Connection) -> None:
    cur = con.cursor()

    # On repart propre
    cur.execute("DROP TABLE IF EXISTS tenders")
    cur.execute("DROP TABLE IF EXISTS source_portals")

    # Table des AO normalisés pour le frontend
    cur.execute(
        """
        CREATE TABLE tenders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plateforme TEXT,
            reference TEXT,
            acheteur TEXT,
            titre TEXT,
            type TEXT,
            statut TEXT,
            date_publication TEXT,
            date_cloture TEXT,
            fuseau_horaire TEXT,
            categories_unspsc TEXT,
            categorie_principale TEXT,
            budget TEXT,
            lien TEXT,
            mots_cles_detectes TEXT,
            score_pertinence REAL,
            extrait_recherche TEXT,
            est_ats INTEGER,
            resume_ao TEXT,
            pays TEXT,
            region TEXT,
            portail TEXT,
            source_portal_id INTEGER
        )
        """
    )

    # Table des portails (simple pour l'instant)
    cur.execute(
        """
        CREATE TABLE source_portals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            label TEXT,
            country TEXT,
            is_active INTEGER DEFAULT 1
        )
        """
    )

    con.commit()


def load_portals(con: sqlite3.Connection) -> None:
    if not os.path.exists(PORTALS_CSV_PATH):
        print(f"[WARN] Fichier portails non trouvé: {PORTALS_CSV_PATH}")
        return

    cur = con.cursor()
    items: List[Tuple[str, str, str, int]] = []

    with open(PORTALS_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = (row.get("code") or row.get("portal_code") or "").strip()
            label = (row.get("label") or row.get("portal_label") or "").strip()
            country = (row.get("country") or row.get("pays") or "").strip()
            is_active_raw = (row.get("is_active") or row.get("active") or "1").strip()
            try:
                is_active = int(is_active_raw)
            except ValueError:
                is_active = 1
            items.append((code, label, country, is_active))

    if items:
        cur.executemany(
            "INSERT INTO source_portals (code, label, country, is_active) VALUES (?, ?, ?, ?)",
            items,
        )
        con.commit()
        print(f"[OK] Portails importés: {len(items)}")
    else:
        print("[INFO] Aucun portail à importer.")


def load_tenders(con: sqlite3.Connection) -> None:
    if not os.path.exists(AO_CSV_PATH):
        print(f"[WARN] Fichier AO non trouvé: {AO_CSV_PATH}")
        return

    cur = con.cursor()
    items: List[Tuple] = []

    with open(AO_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        def g(row, *keys, default=""):
            for k in keys:
                if k in row and row[k] is not None:
                    v = str(row[k]).strip()
                    if v != "":
                        return v
            return default

        for row in reader:
            plateforme = g(row, "plateforme", "portal", "portal_label")
            reference = g(row, "reference", "ref", "reference_ao")
            acheteur = g(row, "acheteur", "buyer_name")
            titre = g(row, "titre", "title")
            type_ao = g(row, "type", "tender_type")
            statut = g(row, "statut", "status")
            date_publication = g(row, "date_publication", "publication_date")
            date_cloture = g(row, "date_cloture", "closing_date")
            fuseau_horaire = g(row, "fuseau_horaire", "timezone")
            categories_unspsc = g(row, "categories_unspsc", "unspsc_categories")
            categorie_principale = g(row, "categorie_principale", "main_category")
            budget = g(row, "budget", "estimated_budget")
            lien = g(row, "lien", "url", "link")
            mots_cles_detectes = g(row, "mots_cles_detectes", "matched_keywords")
            score_pertinence_raw = g(row, "score_pertinence", "relevance_score", default="")
            extrait_recherche = g(row, "extrait_recherche", "search_excerpt")
            est_ats_raw = g(row, "est_ats", "is_ats", "flag_ats", default="0")
            resume_ao = g(row, "resume_ao", "summary")
            pays = g(row, "pays", "country")
            region = g(row, "region")
            portail = g(row, "portail", "portal_label", "portal")
            source_portal_id_raw = g(row, "source_portal_id", "portal_id", default="")

            # casting "safe"
            try:
                score_pertinence = float(score_pertinence_raw.replace(",", ".")) if score_pertinence_raw else None
            except ValueError:
                score_pertinence = None

            try:
                est_ats = int(est_ats_raw)
            except ValueError:
                est_ats = 0

            try:
                source_portal_id = int(source_portal_id_raw) if source_portal_id_raw else None
            except ValueError:
                source_portal_id = None

            items.append(
                (
                    plateforme,
                    reference,
                    acheteur,
                    titre,
                    type_ao,
                    statut,
                    date_publication,
                    date_cloture,
                    fuseau_horaire,
                    categories_unspsc,
                    categorie_principale,
                    budget,
                    lien,
                    mots_cles_detectes,
                    score_pertinence,
                    extrait_recherche,
                    est_ats,
                    resume_ao,
                    pays,
                    region,
                    portail,
                    source_portal_id,
                )
            )

    if items:
        cur.executemany(
            """
            INSERT INTO tenders (
                plateforme,
                reference,
                acheteur,
                titre,
                type,
                statut,
                date_publication,
                date_cloture,
                fuseau_horaire,
                categories_unspsc,
                categorie_principale,
                budget,
                lien,
                mots_cles_detectes,
                score_pertinence,
                extrait_recherche,
                est_ats,
                resume_ao,
                pays,
                region,
                portail,
                source_portal_id
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            items,
        )
        con.commit()
        print(f"[OK] AO importés: {len(items)}")
    else:
        print("[INFO] Aucun AO à importer.")


def main() -> None:
    print(f"[INFO] Initialisation de la base SQLite: {DB_PATH}")
    con = get_connection()
    try:
        create_tables(con)
        print("[OK] Tables créées.")

        load_portals(con)
        load_tenders(con)

        # petit check de contrôle
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM tenders")
        nb_tenders = cur.fetchone()[0]
        print(f"[INFO] AO chargés en base: {nb_tenders}")
    finally:
        con.close()
        print("[OK] Base initialisée.")


if __name__ == "__main__":
    main()
