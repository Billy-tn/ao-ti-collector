import csv
import io
import re
import json
import requests
from dateutil import parser as dateparser  # gardé si tu veux parser/normaliser les dates plus tard

# =========================
# Config
# =========================

SEAO_DATASET_ID = "d23b2e02-085d-43e5-9e6e-e1d558ebfdd5"
CANADABUYS_TENDERS_ID = "6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en,fr;q=0.9",
    # On se présente comme venant de la page officielle open data CanadaBuys
    "Referer": "https://canadabuys.canada.ca/en/procurement-and-contracting-data",
}

KEYWORD_RE = re.compile(
    r"(\bATS\b|syst(?:è|e)me de suivi des candidatures|suivi des candidatures|"
    r"logiciel de recrutement|acquisition de talents?|solution de recrutement|"
    r"plateforme de recrutement|\bapplicant tracking system\b|"
    r"\brecruit(?:ment)? software\b|\btalent acquisition\b|"
    r"\brecruiting platform\b)",
    re.IGNORECASE,
)

# =========================
# HTTP utils
# =========================

def fetch_json(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_text(url):
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.text

# =========================
# CKAN utils
# =========================

def ckan_package_show(base, dataset_id):
    url = f"{base}/package_show?id={dataset_id}"
    js = fetch_json(url)
    if not js.get("success"):
        raise RuntimeError(f"CKAN failed for {url}")
    return js["result"]

def is_json_resource(res):
    fmt = (res.get("format") or "").lower()
    url = (res.get("url") or "").lower()
    return "json" in fmt or "json" in url

def pick_latest_resources(resources, hint=None):
    def score(r):
        name = (r.get("name") or r.get("title") or "").lower()
        url = (r.get("url") or "").lower()
        last = (r.get("last_modified") or r.get("created") or "")
        fmt = (r.get("format") or "").lower()
        hint_boost = 1 if (hint and hint in name) else 0
        fmt_boost = 1 if any(x in fmt or x in url for x in ["json", "csv"]) else 0
        return (hint_boost, fmt_boost, last, name, url)
    return sorted(resources, key=score, reverse=True)

# =========================
# Normalisation générique
# =========================

def normalize_record(rec, source):
    """Mappe un enregistrement brut (SEAO ou CanadaBuys) vers notre modèle commun."""

    def g(keys):
        for k in keys:
            if k in rec and rec[k]:
                v = rec[k]
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, ensure_ascii=False)
                s = str(v).strip()
                if s:
                    return s
        return ""

    def g_pattern(any_parts=None, all_parts=None):
        any_parts = [p.lower() for p in (any_parts or [])]
        all_parts = [p.lower() for p in (all_parts or [])]
        for k, v in rec.items():
            lk = k.lower()
            if any_parts and not any(p in lk for p in any_parts):
                continue
            if all_parts and not all(p in lk for p in all_parts):
                continue
            if v:
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, ensure_ascii=False)
                s = str(v).strip()
                if s:
                    return s
        return ""

    def g_smart(exact_keys=None, any_parts=None, all_parts=None):
        v = g(exact_keys or [])
        if v:
            return v
        return g_pattern(any_parts, all_parts)

    # Titre
    title = g_smart(
        [
            "tenderNoticeTitle-en","tenderNoticeTitle-fr",
            "tenderTitle-en","tenderTitle-fr",
            "titre","title","objet","noticeTitleEn","noticeTitleFr",
            "nomProjet","descriptionCourte","summary","name"
        ],
        any_parts=["title","titre"]
    )

    # Description
    description = g_smart(
        [
            "tenderNoticeDescription-en","tenderNoticeDescription-fr",
            "tenderDescription-en","tenderDescription-fr",
            "description","desc","descriptionDetaillee",
            "longDescriptionEn","longDescriptionFr","notes"
        ],
        any_parts=["description"]
    )

    # Acheteur
    buyer = g_smart(
        [
            "buyerName","procuringEntity-en","procuringEntity-fr",
            "organizationName-en","organizationName-fr",
            "organisme","organisation","acheteur","agency"
        ],
        any_parts=["buyer","organisme","organisation","agency"]
    )

    # Statut
    status = g_smart(
        [
            "tenderNoticeStatus-en","tenderNoticeStatus-fr","tenderNoticeStatus-code",
            "status","statut","noticeStatus","etat"
        ],
        any_parts=["status","statut"]
    )

    # Date publication
    pub_date = g_smart(
        [
            "tenderNoticePublishedDate","tenderPublicationDate","tenderNoticePublicationDate",
            "datePublication","publicationDate","publishedDate",
            "date_publication","issueDate"
        ],
        any_parts=["publish","publication","issue","date"]
    )

    # Date clôture
    close_date = g_smart(
        [
            "tenderNoticeClosingDate","tenderClosingDate",
            "dateLimite","closingDate","bidClosingDate",
            "deadline","date_fermeture"
        ],
        any_parts=["closing","clôture","deadline"]
    )

    # Référence
    refnum = g_smart(
        [
            "tenderNoticeNumber","tenderNoticeUuid","legacyNoticeId",
            "numero","noAvis","reference","referenceNumber",
            "solicitationNumber","no_dossier","reference_no"
        ],
        all_parts=["tender","number"]
    ) or g_pattern(all_parts=["reference"])

    # Lien
    link = g_smart(
        [
            "tenderNoticeUrl-en","tenderNoticeUrl-fr","tenderNoticeUrl",
            "url","lienAvis","noticeURL","tenderURL","link","links"
        ],
        any_parts=["url","http"]
    )

    # Catégorie
    category = g_smart(
        [
            "unspscCodes","unspscCode",
            "categorie","unspsc","category","naicsCodes","categories"
        ],
        any_parts=["unspsc","category","naics"]
    )

    # Budget
    budget = g_smart(
        [
            "estimatedValue","estimatedValueRange",
            "montant","budget","valeurEstimee"
        ],
        any_parts=["value","budget","montant"]
    )

    # Type d'avis
    notice_type = g_smart(
        [
            "tenderNoticeType-en","tenderNoticeType-fr","tenderNoticeType-code",
            "type","noticeType","typeAvis","notice_format"
        ],
        any_parts=["type"]
    )

    # Fuseau
    timezone = g_smart(
        [
            "closingTimeZone","timezone","fuseau"
        ],
        any_parts=["timezone","fuseau"]
    )

    # Langue
    language = g_smart(
        [
            "tenderNoticeLanguage","languageCode",
            "language","langue","lang"
        ],
        any_parts=["lang"]
    )

    combined = " ".join(
        x for x in [title, description, category, notice_type, buyer, refnum] if x
    )

    return {
        "Plateforme": source,
        "Référence": refnum,
        "Acheteur": buyer,
        "Titre": title,
        "Type": notice_type,
        "Statut": status,
        "Date de publication": pub_date,
        "Date de clôture": close_date,
        "Fuseau horaire": timezone,
        "Catégories/UNSPSC": category,
        "Budget (si publié)": budget,
        "Lien": link,
        "Langue": language,
        "Mots-clés détectés ?": "Oui" if KEYWORD_RE.search(combined) else "Non",
        "Extrait recherche": combined[:300],
    }

# =========================
# CanadaBuys CSV
# =========================

def parse_canadabuys_csv(text):
    reader = csv.DictReader(io.StringIO(text))
    out = []
    for row in reader:
        if not any((v or "").strip() for v in row.values()):
            continue
        out.append(normalize_record(row, "CanadaBuys"))
    return out

# =========================
# Fetch SEAO
# =========================

def fetch_seao():
    base = "https://www.donneesquebec.ca/recherche/api/3/action"
    pack = ckan_package_show(base, SEAO_DATASET_ID)
    resources = pack.get("resources", [])
    candidates = [r for r in resources if is_json_resource(r)]
    candidates = pick_latest_resources(candidates)
    if not candidates:
        return []

    url = candidates[0]["url"]
    js = fetch_json(url)

    items = []
    if isinstance(js, list):
        items = js
    elif isinstance(js, dict):
        for k in ["avis", "tenders", "notices", "records", "items", "results", "data"]:
            if isinstance(js.get(k), list):
                items = js[k]
                break
        if not items:
            items = [js]

    rows = [
        normalize_record(rec, "SEAO")
        for rec in items
        if isinstance(rec, dict)
    ]
    return rows

# =========================
# Fetch CanadaBuys
# =========================

def fetch_canadabuys():
    base = "https://open.canada.ca/data/api/3/action"
    try:
        pack = ckan_package_show(base, CANADABUYS_TENDERS_ID)
    except Exception as e:
        print("CanadaBuys CKAN error:", e)
        return []

    resources = pack.get("resources", [])
    candidates = pick_latest_resources(resources, hint="tender")

    for res in candidates[:5]:
        url = res.get("url")
        if not url:
            continue
        try:
            text = fetch_text(url)
            url_lower = url.lower()

            if url_lower.endswith(".csv"):
                rows = parse_canadabuys_csv(text)
            else:
                try:
                    js = json.loads(text)
                except Exception:
                    continue

                if isinstance(js, list):
                    items = js
                elif isinstance(js, dict):
                    items = (
                        js.get("results")
                        or js.get("data")
                        or js.get("notices")
                        or js.get("items")
                        or []
                    )
                else:
                    items = []

                rows = [
                    normalize_record(rec, "CanadaBuys")
                    for rec in items
                    if isinstance(rec, dict)
                ]

            if rows:
                return rows

        except requests.HTTPError as e:
            # On log, mais on ne tue pas le script
            print(f"CanadaBuys HTTP error on {url}:", e)
        except Exception as e:
            print(f"CanadaBuys error on {url}:", e)

    return []

# =========================
# Flags & export
# =========================

def add_ats_flag(row):
    text = f"{row.get('Titre','')} {row.get('Extrait recherche','')}"
    row["Est ATS ?"] = "Oui" if KEYWORD_RE.search(text) else "Non"
    return row

def main():
    seao_rows = fetch_seao()
    cbuys_rows = fetch_canadabuys()
    all_rows = [add_ats_flag(r) for r in (seao_rows + cbuys_rows)]

    headers = [
        "Plateforme","Référence","Acheteur","Titre","Type","Statut",
        "Date de publication","Date de clôture","Fuseau horaire",
        "Catégories/UNSPSC","Budget (si publié)","Lien","Langue",
        "Mots-clés détectés ?","Extrait recherche","Est ATS ?"
    ]

    with open("ao_output_v1.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in all_rows:
            w.writerow({h: r.get(h, "") for h in headers})

    print(f"Exporté {len(all_rows)} lignes dans ao_output_v1.csv")

if __name__ == "__main__":
    main()
