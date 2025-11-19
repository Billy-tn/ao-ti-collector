import csv
import os
from typing import List, Optional

from sqlalchemy.orm import Session

from .database import Base, engine, SessionLocal
from .models import Tender, KeywordProfile, KeywordTerm, SourcePortal

AO_CSV_PATH = "./v1_stable/ao_output_v1.csv"
PORTALS_CSV_PATH = "./config/portals_sources.csv"


def bool_from_oui_non(value: str) -> bool:
    if not value:
        return False
    v = value.strip().lower()
    return v in ("oui", "yes", "true", "1")


def extract_domain(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url:
        return ""
    if "://" in url:
        url = url.split("://", 1)[1]
    return url.split("/", 1)[0].lower()


def load_portals(db: Session) -> List[SourcePortal]:
    if not os.path.exists(PORTALS_CSV_PATH):
        print(f"[WARN] Fichier portails non trouvé: {PORTALS_CSV_PATH}")
        return []

    portals = []
    with open(PORTALS_CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Nom de la source") or "").strip()
            if not name:
                continue

            sp = SourcePortal(
                name=name,
                country=(row.get("Pays/Province") or "").strip(),
                level=(row.get("Niveau") or "").strip(),
                platform=(row.get("Plateforme") or "").strip(),
                main_url=(row.get("URL principale") or "").strip(),
                api_official=bool_from_oui_non(row.get("API officielle") or ""),
                api_url=(row.get("Lien API / Données") or "").strip(),
                formats=(row.get("Formats") or "").strip(),
                access_notes=(row.get("Notes") or "").strip(),
                scraping_allowed=(row.get("Scraping autorisé (selon CGU)") or "").strip(),
                recommended_method=(row.get("Méthode conseillée (API/CSV/RSS/alertes)") or "").strip(),
                ti_keywords=(row.get("Mots-clés TI (OR)") or "").strip(),
                search_url=(row.get("Lien recherche AO (filtre)") or "").strip(),
                pipeline_status=(row.get("Statut pipeline") or "").strip(),
            )
            db.add(sp)
            portals.append(sp)

    db.commit()
    print(f"[OK] Portails chargés: {len(portals)}")
    return portals


def normalize_country(raw: str) -> str:
    if not raw:
        return ""
    txt = raw.lower()
    if "québec" in txt or "quebec" in txt:
        return "CA-QC"
    if "canada" in txt and "québec" not in txt:
        return "CA-FED"
    if "états" in txt or "us" in txt or "usa" in txt:
        return "US"
    if "royaume" in txt or "uk" in txt:
        return "UK"
    if "union européenne" in txt or "eu" in txt:
        return "EU"
    return raw.strip()


def match_portal_for_tender(row: dict, portals: List[SourcePortal]) -> (str, str, Optional[int]):
    plateforme = (row.get("Plateforme") or "").strip()
    lien = (row.get("Lien") or "").strip()
    domain = extract_domain(lien)

    for sp in portals:
        if plateforme and (
            plateforme.lower() == (sp.platform or "").lower()
            or plateforme.lower() == (sp.name or "").lower()
        ):
            return normalize_country(sp.country), sp.name, sp.id

    for sp in portals:
        main_domain = extract_domain(sp.main_url or "")
        if main_domain and main_domain in domain:
            return normalize_country(sp.country), sp.name, sp.id

    if "seao.gouv.qc.ca" in domain:
        return "CA-QC", "SEAO", None
    if "canadabuys.canada.ca" in domain:
        return "CA-FED", "CanadaBuys", None

    return "", plateforme or "", None


def init_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()

    portals = load_portals(db)

    if os.path.exists(AO_CSV_PATH):
        with open(AO_CSV_PATH, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                pays, portail, portal_id = match_portal_for_tender(row, portals)

                est_ats = (row.get("Est ATS ?") or "").strip().lower() == "oui"
                budget_raw = (row.get("Budget (si publié)") or row.get("Budget (si publi\u00e9)") or "").strip()
                try:
                    budget = float(str(budget_raw).replace(",", ".")) if budget_raw else None
                except Exception:
                    budget = None

                tender = Tender(
                    plateforme=row.get("Plateforme") or "",
                    reference=row.get("Référence") or row.get("Reference") or "",
                    acheteur=row.get("Acheteur") or "",
                    titre=row.get("Titre") or "",
                    type=row.get("Type") or "",
                    statut=row.get("Statut") or "",
                    date_publication=row.get("Date de publication") or "",
                    date_cloture=row.get("Date de clôture") or "",
                    fuseau_horaire=row.get("Fuseau horaire") or "",
                    categories_unspsc=row.get("Catégories/UNSPSC") or "",
                    lien=row.get("Lien") or "",
                    budget=budget,
                    mots_cles_detectes=row.get("Mots-clés détectés ?") or "",
                    extrait_recherche=row.get("Extrait recherche") or "",
                    est_ats=est_ats,
                    resume_ao=row.get("Résumé AO") or "",
                    pays=pays,
                    portail=portail,
                    source_portal_id=portal_id,
                )
                db.add(tender)
                count += 1

        db.commit()
        print(f"[OK] AO importés: {count}")
    else:
        print(f"[WARN] Fichier AO non trouvé: {AO_CSV_PATH}")

    existing_ats = (
        db.query(KeywordProfile)
        .filter(KeywordProfile.name == "ATS")
        .first()
    )
    if not existing_ats:
        ats = KeywordProfile(
            name="ATS",
            description="Appels d'offres liés aux ATS / recrutement",
            active=True,
        )
        db.add(ats)
        db.flush()

        default_terms = [
            "ATS",
            "applicant tracking system",
            "système de suivi des candidatures",
            "logiciel de recrutement",
            "talent acquisition",
            "plateforme de recrutement",
        ]
        for t in default_terms:
            db.add(KeywordTerm(profile_id=ats.id, term=t))

    db.commit()
    db.close()
    print("[OK] Base initialisée.")


if __name__ == "__main__":
    init_db()
