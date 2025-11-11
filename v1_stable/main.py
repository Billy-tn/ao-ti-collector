import csv
import datetime as dt
import io
import sys
from typing import Dict, List, Optional, Tuple

import requests

# =========================
# CONFIG
# =========================

# Fenêtre en jours pour filtrer les AO (SEAO + CanadaBuys)
WINDOW_DAYS = 60

# Fichiers de sortie
OUTPUT_ALL = "ao_output_v1.csv"
OUTPUT_FOCUS = "ao_output_v1_ats_only.csv"

# Jeu de données SEAO (Données Québec)
SEAO_PACKAGE_ID = "systeme-electronique-dappel-doffres-seao"
SEAO_PACKAGE_URL = (
    "https://www.donneesquebec.ca/recherche/api/3/action/package_show"
)

# CanadaBuys (tenders fédéraux)
CANADABUYS_CSV_URL = (
    "https://canadabuys.canada.ca/opendata/pub/newTenderNotice-nouvelAvisAppelOffres.csv"
)

# Mots-clés stratégiques (fichier FOCUS)
# - ATS / recrutement
# - CRM / gestion de la relation client
# - Solutions TI structurantes (ERP / Odoo / ServiceNow / etc.)
KEYWORDS_FOCUS = [
    # ATS / recrutement
    "ats",
    "applicant tracking",
    "talent acquisition",
    "recrutement",
    "recruitment",
    "gestion des candidatures",
    # CRM
    "crm",
    "customer relationship management",
    "gestion de la relation client",
    "relation client",
    "salesforce",
    "microsoft dynamics",
    "hubspot",
    # ERP / plateformes
    "erp",
    "oracle",
    "sap",
    "odoo",
    "workday",
    "dynamics 365",
    # it / plateforme service / itsm
    "servicenow",
    "itsm",
    "ticketing",
    "support client",
    "portail client",
    # nuage / infra / data (souvent liés aux projets structurants)
    "cloud",
    "infonuagique",
    "azure",
    "aws",
    "gcp",
    "datawarehouse",
    " entrepôt de données",
]

# =========================
# OUTILS
# =========================


def log(msg: str) -> None:
    print(msg, file=sys.stdout, flush=True)


def parse_date(value: str) -> Optional[dt.date]:
    """Parse une date en provenance des différentes sources."""
    if not value:
        return None

    value = value.strip()

    # Formats fréquents : 2025-11-10, 2025-11-10T13:45:00Z, 2025/11/10
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(value[:10], fmt).date()
        except ValueError:
            pass

    # ISO-like
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "")).date()
    except Exception:
        return None


def match_focus_keywords(text: str, keywords: List[str]) -> List[str]:
    text_l = (text or "").lower()
    matched = [kw for kw in keywords if kw.lower() in text_l]
    # dédoublonner proprement
    return sorted(set(matched))


# =========================
# SEAO - RÉCUP / NORMALISATION
# =========================


def get_seao_resources() -> List[Tuple[str, str]]:
    """
    Récupère via l'API CKAN la liste des ressources JSON (hebdo_*.json, mensuel_*.json)
    et renvoie [(name, url), ...].

    On ne charge pas ici, on filtre ensuite par fenêtre de dates.
    """
    try:
        resp = requests.get(
            SEAO_PACKAGE_URL,
            params={"id": SEAO_PACKAGE_ID},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        resources = data.get("result", {}).get("resources", [])
    except Exception as e:
        log(f"ERREUR: impossible de charger la liste des ressources SEAO ({e})")
        return []

    results: List[Tuple[str, str]] = []
    for r in resources:
        fmt = (r.get("format") or "").lower()
        name = (r.get("name") or "").lower()
        url = r.get("url") or ""
        if fmt == "json" and url and (
            name.startswith("hebdo_") or name.startswith("mensuel_")
        ):
            results.append((name, url))

    # dédoublonnage par URL
    unique: Dict[str, str] = {}
    for name, url in results:
        unique[url] = name

    out = [(name, url) for url, name in unique.items()]
    return out


def extract_period_from_name(name: str) -> Tuple[Optional[dt.date], Optional[dt.date]]:
    """
    Extrait (date_debut, date_fin) à partir d'un nom du type:
    hebdo_YYYYMMDD_YYYYMMDD.json ou mensuel_YYYYMMDD_YYYYMMDD.json
    """
    base = name.replace(".json", "")
    parts = base.split("_")
    if len(parts) < 3:
        return None, None
    try:
        start = dt.datetime.strptime(parts[1], "%Y%m%d").date()
        end = dt.datetime.strptime(parts[2], "%Y%m%d").date()
        return start, end
    except Exception:
        return None, None


def normalize_seao_release(release: dict) -> Optional[dict]:
    tender = release.get("tender", {}) or {}
    buyer_name = ""

    # buyer direct
    buyer = release.get("buyer") or {}
    buyer_name = buyer.get("name") or ""

    # sinon, tenter parties
    if not buyer_name:
        for p in release.get("parties") or []:
            roles = p.get("roles") or []
            if any(r.lower() == "buyer" for r in roles):
                buyer_name = p.get("name") or ""
                break

    title = tender.get("title") or release.get("title") or ""
    description = tender.get("description") or ""

    # date : release.date prioritaire, sinon tenderPeriod
    date_str = (
        release.get("date")
        or (tender.get("tenderPeriod") or {}).get("startDate")
        or (tender.get("tenderPeriod") or {}).get("endDate")
    )
    pub_date = parse_date(date_str)
    if not pub_date:
        return None

    # URL : on reste conservateur -> on prend la première URL de document si dispo
    url = ""
    for doc in tender.get("documents") or []:
        if doc.get("url"):
            url = doc["url"]
            break

    ocid = (
        release.get("ocid")
        or release.get("id")
        or tender.get("id")
        or ""
    )

    return {
        "source": "SEAO",
        "title": title.strip(),
        "url": url.strip(),
        "published_at": pub_date,
        "country": "CA",
        "region": "QC",
        "portal_name": "SEAO",
        "matched_keywords": "",
        "raw_summary": description.strip(),
        "source_domain": "seao.gouv.qc.ca",
        "confidence": 0.9,
        "ocid": ocid,
        "buyer": buyer_name.strip(),
    }


def load_seao(window_start: dt.date, window_end: dt.date) -> List[dict]:
    resources = get_seao_resources()
    if not resources:
        log("SEAO -> aucune ressource trouvée via l'API Données Québec.")
        return []

    selected: List[Tuple[str, str]] = []
    for name, url in resources:
        start, end = extract_period_from_name(name)
        if not start or not end:
            continue
        # on ne garde que les fichiers qui intersectent la fenêtre
        if end < window_start or start > window_end:
            continue
        selected.append((name, url))

    # tri pour un affichage plus stable
    selected.sort(key=lambda x: x[0])

    all_rows: List[dict] = []
    total_releases = 0

    for name, url in selected:
        try:
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log(f"SEAO fichier {name} -> ERREUR chargement ({e})")
            continue

        releases = data.get("releases") or []
        total_releases += len(releases)
        log(f"SEAO fichier {name} -> {len(releases)} enregistrements (releases)")

        for rel in releases:
            row = normalize_seao_release(rel)
            if not row:
                continue
            pub_date = row["published_at"]
            if window_start <= pub_date <= window_end:
                all_rows.append(row)

    log(f"SEAO brut total -> {total_releases} enregistrements scannés")
    log(f"SEAO -> {len(all_rows)} lignes retenues dans la fenêtre")
    return all_rows


# =========================
# CANADABUYS - RÉCUP / NORMALISATION
# =========================


def load_canadabuys(window_start: dt.date, window_end: dt.date) -> List[dict]:
    try:
        resp = requests.get(CANADABUYS_CSV_URL, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        log(f"CanadaBuys -> ERREUR chargement CSV ({e})")
        return []

    content = resp.content.decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(io.StringIO(content))

    rows: List[dict] = []
    for r in reader:
        title = (r.get("Tender Notice Title") or "").strip()
        if not title:
            continue

        date_str = (
            r.get("Publication Date")
            or r.get("PublicationDate")
            or r.get("Date de publication")
            or ""
        )
        pub_date = parse_date(date_str)
        if not pub_date:
            continue
        if not (window_start <= pub_date <= window_end):
            continue

        buyer = (
            r.get("Organization Name")
            or r.get("Procuring Organization")
            or r.get("Organization")
            or ""
        ).strip()

        url = (
            r.get("Tender Notice Link")
            or r.get("URL du préavis d'appel d'offres")
            or r.get("URL")
            or ""
        ).strip()

        summary = (r.get("Description") or r.get("Summary") or "").strip()

        row = {
            "source": "CanadaBuys",
            "title": title,
            "url": url,
            "published_at": pub_date,
            "country": "CA",
            "region": "CA-FED",
            "portal_name": "CanadaBuys",
            "matched_keywords": "",
            "raw_summary": summary,
            "source_domain": "canadabuys.canada.ca",
            "confidence": 0.9,
            "ocid": (r.get("Notice ID") or r.get("Reference Number") or "").strip(),
            "buyer": buyer,
        }
        rows.append(row)

    log(f"CanadaBuys -> {len(rows)} lignes retenues via {CANADABUYS_CSV_URL}")
    return rows


# =========================
# ÉCRITURE CSV
# =========================


FIELDNAMES = [
    "source",
    "title",
    "url",
    "published_at",
    "country",
    "region",
    "portal_name",
    "matched_keywords",
    "raw_summary",
    "source_domain",
    "confidence",
    "ocid",
    "buyer",
]


def write_csv(path: str, rows: List[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            row_out = dict(row)
            # normaliser date -> ISO
            if isinstance(row_out.get("published_at"), dt.date):
                row_out["published_at"] = row_out["published_at"].isoformat()
            writer.writerow(row_out)


# =========================
# MAIN
# =========================


def main() -> None:
    today = dt.date.today()
    window_start = today - dt.timedelta(days=WINDOW_DAYS)

    log(f"Fenêtre de collecte : {window_start.isoformat()} -> {today.isoformat()}")

    # 1) Charger SEAO
    seao_rows = load_seao(window_start, today)

    # 2) Charger CanadaBuys
    cb_rows = load_canadabuys(window_start, today)

    # 3) Fusionner (SEAO + CanadaBuys)
    all_rows = seao_rows + cb_rows

    # 4) Construire le fichier FOCUS (ATS / CRM / etc.)
    focus_rows: List[dict] = []
    for row in all_rows:
        text = " ".join(
            [
                str(row.get("title", "")),
                str(row.get("raw_summary", "")),
                str(row.get("buyer", "")),
            ]
        )
        matched = match_focus_keywords(text, KEYWORDS_FOCUS)
        if matched:
            r = dict(row)
            r["matched_keywords"] = ",".join(matched)
            focus_rows.append(r)

    # 5) Export
    write_csv(OUTPUT_ALL, all_rows)
    write_csv(OUTPUT_FOCUS, focus_rows)

    log(f"Exporté {len(all_rows)} lignes dans {OUTPUT_ALL} (tous AO)")
    log(
        f"Exporté {len(focus_rows)} lignes dans {OUTPUT_FOCUS} "
        f"(AO filtrés par mots-clés stratégiques: ATS/CRM/ERP/etc.)"
    )

    log(
        "\nNOTE: Les AO publiés aujourd'hui sur SEAO n'apparaissent ici "
        "que lorsqu'ils sont intégrés dans les fichiers hebdo/mensuel officiels "
        "sur Données Québec. Si un AO du jour manque, vérifier directement sur SEAO."
    )


if __name__ == "__main__":
    main()
