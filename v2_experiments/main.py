import csv
import io
import os
import re
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from dateutil import parser as dateparser
from urllib.parse import urlparse, parse_qs, unquote

# =========================
# Config
# =========================

TZ = "America/Toronto"
DATE_WINDOW_DAYS = 30
AO_MUST_TERMS_MODE = "ENABLED"  # "ENABLED" ou "DISABLED"

OUTPUT_TENDERS = "tenders_v2.csv"
RUN_LOG = "run_log_v2.csv"

SOURCES_CSV = "sources_v2.csv"    # facultatif (RSS)
KEYWORDS_CSV = "keywords_v2.csv"  # facultatif (must/exclude)

DEFAULT_WHITELIST_DOMAINS = [
    "seao.gouv.qc.ca",
    "canadabuys.canada.ca",
]

HEADERS_HTTP = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en,fr;q=0.9",
}

# =========================
# Helpers génériques
# =========================

def fetch_text(url):
    r = requests.get(url, headers=HEADERS_HTTP, timeout=60)
    r.raise_for_status()
    return r.text

def fetch_json(url):
    r = requests.get(url, headers=HEADERS_HTTP, timeout=60)
    r.raise_for_status()
    return r.json()

def parse_date_safe(s):
    if not s:
        return None
    try:
        dt = dateparser.parse(str(s))
        if not dt:
            return None
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def normalize_iso_or_blank(s):
    dt = parse_date_safe(s)
    if not dt:
        return ""
    return dt.astimezone(timezone.utc).isoformat()

def is_in_window(pub_str, days):
    dt = parse_date_safe(pub_str)
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    return (now - dt).days <= days

def extract_domain(url):
    if not url:
        return ""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""

def resolve_google_news(url):
    if not url or "news.google.com" not in url:
        return url
    try:
        qs = parse_qs(urlparse(url).query)
        if "url" in qs and qs["url"]:
            return unquote(qs["url"][0])
    except Exception:
        pass
    return url

def score_confidence(domain, whitelist):
    if not domain:
        return 40
    if any(w in domain for w in whitelist):
        return 100
    return 70

# =========================
# Config: settings / sources / keywords
# =========================

def load_settings():
    return {
        "DATE_WINDOW_DAYS": DATE_WINDOW_DAYS,
        "AO_MUST_TERMS": AO_MUST_TERMS_MODE,
        "WHITELIST_DOMAINS": DEFAULT_WHITELIST_DOMAINS,
    }

def load_sources():
    """
    sources_v2.csv (optionnel):
    ID,Nom du portail,Format (RSS/API/HTML),RSS,API,Actif (Oui/Non),Pays (code),Région
    """
    out = []
    if not os.path.isfile(SOURCES_CSV):
        return out
    with open(SOURCES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Nom du portail") or row.get("name") or "").strip()
            if not name:
                continue
            row["_active"] = (row.get("Actif (Oui/Non)", "").strip().lower() == "oui")
            row["_format"] = (row.get("Format (RSS/API/HTML)") or "").upper()
            out.append(row)
    return out

def load_keywords():
    """
    keywords_v2.csv (optionnel):
    secteur (code),must_terms,exclude_terms
    """
    out = []
    if not os.path.isfile(KEYWORDS_CSV):
        return out
    with open(KEYWORDS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            must_terms = [
                s.strip().lower()
                for s in (row.get("must_terms") or "").split("|")
                if s.strip()
            ]
            excl_terms = [
                s.strip().lower()
                for s in (row.get("exclude_terms") or "").split("|")
                if s.strip()
            ]
            out.append({
                "sector": (row.get("secteur (code)") or "GEN").strip(),
                "must": must_terms,
                "excl": excl_terms,
            })
    return out

# =========================
# Must / Exclude terms
# =========================

def passes_must_terms(title, summary, keywords, settings):
    mode = (settings.get("AO_MUST_TERMS") or "ENABLED").upper()
    if mode == "DISABLED":
        return True
    if not keywords:
        return True

    text = (title or "").lower() + " " + (summary or "").lower()
    must_all = set()
    excl_all = set()
    for k in keywords:
        must_all.update(k.get("must", []))
        excl_all.update(k.get("excl", []))

    if must_all and not any(m in text for m in must_all):
        return False
    if excl_all and any(e in text for e in excl_all):
        return False
    return True

def compute_matched_keywords(title, summary, keywords):
    if not keywords:
        return ""
    text = (title or "").lower() + " " + (summary or "").lower()
    matched = set()
    for k in keywords:
        for m in k.get("must", []):
            if m and m in text:
                matched.add(m)
    return "|".join(sorted(matched))

# =========================
# Normalisation (Apps Script style)
# =========================

def normalize_record(rec, source_label):
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

    def g_any(substrs):
        substrs = [s.lower() for s in substrs]
        for k, v in rec.items():
            lk = str(k).lower()
            if any(s in lk for s in substrs):
                if v:
                    if isinstance(v, (dict, list)):
                        v = json.dumps(v, ensure_ascii=False)
                    s = str(v).strip()
                    if s:
                        return s
        return ""

    title = g([
        "titre","title","objet",
        "noticeTitleEn","noticeTitleFr",
        "nomProjet","descriptionCourte",
        "summary","name","notice_title"
    ]) or g_any(["title","titre"])

    description = g([
        "description","desc","descriptionDetaillee",
        "longDescriptionEn","longDescriptionFr",
        "notes","summary"
    ]) or g_any(["description","summary"])

    url = g([
        "url","lienAvis","noticeURL","tenderURL",
        "link","links","notice_url",
        "tenderNoticeUrl-en","tenderNoticeUrl-fr"
    ])

    buyer = g([
        "organisme","organisation","acheteur",
        "buyerName","procuringEntity","procuringEntityEn",
        "organizationName-en","organizationName-fr","agency"
    ])

    status = g(["statut","status","noticeStatus","etat"])

    pub_date = g([
        "datePublication","publicationDate","publishedDate",
        "date_publication","issueDate","published","publication_date"
    ])

    close_date = g([
        "dateLimite","closingDate","bidClosingDate",
        "deadline","date_fermeture","closing_date"
    ])

    refnum = g([
        "numero","noAvis","reference","referenceNumber",
        "solicitationNumber","no_dossier","reference_no",
        "tenderNoticeUuid","tenderNoticeNumber","legacyNoticeId"
    ])

    category = g([
        "categorie","unspsc","unspscCodes","unspscCode",
        "category","naicsCodes","categories"
    ])

    budget = g([
        "montant","budget","estimatedValue","estimatedValueRange","valeurEstimee"
    ])

    notice_type = g([
        "type","noticeType","typeAvis","notice_format",
        "tenderNoticeType-en","tenderNoticeType-fr","tenderNoticeType-code"
    ])

    country = g(["Pays (code)"]) or ""
    region = g(["Région"]) or ""

    raw_summary = description
    source_domain = extract_domain(url)

    return {
        "source": source_label,
        "title": title,
        "url": url,
        "published_at": pub_date,
        "country": country,
        "region": region,
        "portal_name": source_label,
        "matched_keywords": "",
        "raw_summary": raw_summary,
        "source_domain": source_domain,
        "confidence": 0,
    }

# =========================
# SEAO via CKAN
# =========================

def fetch_seao():
    base = "https://www.donneesquebec.ca/recherche/api/3/action"
    dataset_id = "d23b2e02-085d-43e5-9e6e-e1d558ebfdd5"
    js = fetch_json(f"{base}/package_show?id={dataset_id}")
    if not js.get("success"):
        return []
    resources = js["result"].get("resources", [])
    json_res = [
        r for r in resources
        if "json" in (r.get("format","")+r.get("url","")).lower()
    ]
    if not json_res:
        return []
    json_res.sort(key=lambda r: (r.get("last_modified") or r.get("created") or ""), reverse=True)
    url = json_res[0]["url"]
    data = fetch_json(url)

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = []
        for key in ["avis","tenders","notices","records","items","results","data"]:
            if isinstance(data.get(key), list):
                items = data[key]
                break
        if not items:
            items = [data]
    else:
        items = []

    out = []
    for rec in items:
        if isinstance(rec, dict):
            out.append(normalize_record(rec, "SEAO"))
    return out

# =========================
# CanadaBuys via Open Data
# =========================

def fetch_canadabuys():
    base = "https://open.canada.ca/data/api/3/action"
    dataset_id = "6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2"
    try:
        js = fetch_json(f"{base}/package_show?id={dataset_id}")
    except Exception as e:
        print("CanadaBuys CKAN error:", e)
        return []
    if not js.get("success"):
        return []
    resources = js["result"].get("resources", [])

    def score(r):
        name = (r.get("name") or r.get("title") or "").lower()
        url = (r.get("url") or "").lower()
        last = (r.get("last_modified") or r.get("created") or "")
        fmt = (r.get("format") or "").lower()
        hint = 1 if "tender" in name else 0
        csv_json = 1 if ("csv" in fmt or "csv" in url or "json" in fmt or "json" in url) else 0
        return (hint, csv_json, last, name, url)

    resources.sort(key=score, reverse=True)

    for res in resources[:5]:
        url = res.get("url")
        if not url:
            continue
        try:
            text = fetch_text(url)
            lower = url.lower()
            rows = []
            if ".csv" in lower and ".json" not in lower:
                reader = csv.DictReader(io.StringIO(text))
                for row in reader:
                    if any((v or "").strip() for v in row.values()):
                        rows.append(normalize_record(row, "CanadaBuys"))
            else:
                try:
                    js_data = json.loads(text)
                except Exception:
                    continue
                if isinstance(js_data, list):
                    items = js_data
                elif isinstance(js_data, dict):
                    items = (
                        js_data.get("results")
                        or js_data.get("data")
                        or js_data.get("notices")
                        or js_data.get("items")
                        or []
                    )
                else:
                    items = []
                for rec in items:
                    if isinstance(rec, dict):
                        rows.append(normalize_record(rec, "CanadaBuys"))
            if rows:
                return rows
        except Exception as e:
            print("CanadaBuys error on", url, ":", e)
    return []

# =========================
# RSS (optionnel, via sources_v2.csv)
# =========================

def fetch_rss_items(rss_url, src_name):
    try:
        xml_text = fetch_text(rss_url)
        root = ET.fromstring(xml_text)
    except Exception as e:
        print("RSS error", rss_url, ":", e)
        return []
    out = []
    for item in root.iter():
        if item.tag.lower().endswith("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "") or (item.findtext("published") or "")
            desc = (item.findtext("description") or "") or (item.findtext("summary") or "")
            out.append({
                "source": src_name,
                "title": title,
                "url": link,
                "published_at": pub,
                "country": "",
                "region": "",
                "portal_name": src_name,
                "matched_keywords": "",
                "raw_summary": desc,
                "source_domain": extract_domain(link),
                "confidence": 0,
            })
    return out

def collect_rss_from_sources(sources):
    out = []
    for src in sources:
        if not src.get("_active"):
            continue
        fmt = src.get("_format","")
        if "RSS" not in fmt:
            continue
        rss = (src.get("RSS") or "").strip()
        if not rss:
            continue
        name = (src.get("Nom du portail") or src.get("name") or "").strip() or "RSS"
        out.extend(fetch_rss_items(rss, name))
    return out

# =========================
# Enrichissement + filtres
# =========================

def enrich_and_filter(row, keywords, settings):
    title = row.get("title","") or ""
    summary = row.get("raw_summary","") or ""
    url = resolve_google_news(row.get("url","") or "")
    pub = row.get("published_at","") or ""

    if not passes_must_terms(title, summary, keywords, settings):
        return None
    if not is_in_window(pub, settings["DATE_WINDOW_DAYS"]):
        return None

    matched = compute_matched_keywords(title, summary, keywords)
    domain = extract_domain(url)
    confidence = score_confidence(domain, settings["WHITELIST_DOMAINS"])

    out = dict(row)
    out["url"] = url
    out["published_at"] = normalize_iso_or_blank(pub)
    out["matched_keywords"] = matched
    out["source_domain"] = domain
    out["confidence"] = confidence
    return out

# =========================
# Run log
# =========================

def append_run_log(action, rows_in, rows_out, errors=0):
    new = not os.path.isfile(RUN_LOG)
    if new:
        run_id = 1
    else:
        with open(RUN_LOG, encoding="utf-8") as f:
            run_id = sum(1 for _ in f)
    with open(RUN_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["run_id","datetime_utc","action","rows_in","rows_out","errors"])
        w.writerow([run_id, datetime.utcnow().isoformat(), action, rows_in, rows_out, errors])

# =========================
# Main
# =========================

def main():
    settings = load_settings()
    keywords = load_keywords()
    sources = load_sources()

    rows = []

    # 1) RSS (optionnel)
    rows.extend(collect_rss_from_sources(sources))

    # 2) SEAO
    rows.extend(fetch_seao())

    # 3) CanadaBuys
    rows.extend(fetch_canadabuys())

    rows_in = len(rows)

    enriched = []
    seen = set()
    for r in rows:
        e = enrich_and_filter(r, keywords, settings)
        if e is None:
            continue
        key = (e.get("title",""), e.get("url",""))
        if key in seen:
            continue
        seen.add(key)
        enriched.append(e)

    headers = [
        "source","title","url","published_at","country","region",
        "portal_name","matched_keywords","raw_summary","source_domain","confidence"
    ]

    with open(OUTPUT_TENDERS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in enriched:
            w.writerow({h: r.get(h,"") for h in headers})

    append_run_log("V2_full_run", rows_in, len(enriched), 0)
    print(f"V2: {len(enriched)} lignes retenues sur {rows_in}, exportées dans {OUTPUT_TENDERS}")

if __name__ == "__main__":
    main()
