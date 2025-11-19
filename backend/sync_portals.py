import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "ao.db"

# Catalogue de base : grands portails publics & multi-pays.
# Tu pourras en ajouter/switcher is_active=0/1 selon ce que ton collector gère vraiment.
PORTALS = [
    # --- CANADA / QUÉBEC ---
    {
        "code": "SEAO",
        "name": "Système électronique d’appel d’offres (Québec)",
        "country": "CA",
        "region": "QC",
        "base_url": "https://www.seao.ca",
        "api_type": "open_data_ocds",
        "is_active": 1,
        "notes": "Source officielle Québec. Intégrée via Données Québec (JSON hebdo/mensuel).",
    },
    {
        "code": "CANADABUYS",
        "name": "CanadaBuys / AchatsCanada",
        "country": "CA",
        "region": "FED",
        "base_url": "https://canadabuys.canada.ca",
        "api_type": "open_data_csv",
        "is_active": 1,
        "notes": "Portail fédéral. Intégration CSV/API à stabiliser (403 possible selon environnement).",
    },
    {
        "code": "MERX",
        "name": "MERX (Canada)",
        "country": "CA",
        "region": "MULTI",
        "base_url": "https://www.merx.com",
        "api_type": "portal_web",
        "is_active": 0,
        "notes": "Agrégateur public/privé. Intégration potentielle via scraping contrôlé.",
    },
    {
        "code": "BIDDINGO",
        "name": "Biddingo",
        "country": "CA",
        "region": "MULTI",
        "base_url": "https://www.biddingo.com",
        "api_type": "portal_web",
        "is_active": 0,
        "notes": "Plateforme utilisée par certaines villes/organismes.",
    },
    {
        "code": "BCBID",
        "name": "BC Bid",
        "country": "CA",
        "region": "BC",
        "base_url": "https://www.bcbid.gov.bc.ca",
        "api_type": "portal_web",
        "is_active": 0,
        "notes": "Portail Colombie-Britannique.",
    },
    {
        "code": "ATS_ON",
        "name": "Ontario Tenders Portal",
        "country": "CA",
        "region": "ON",
        "base_url": "https://www.ontariotenders.app",
        "api_type": "portal_web",
        "is_active": 0,
        "notes": "Portail Ontario, solution Merx/Ariba-like.",
    },

    # --- ÉTATS-UNIS ---
    {
        "code": "SAM_USA",
        "name": "SAM.gov Contract Opportunities",
        "country": "US",
        "region": "FED",
        "base_url": "https://sam.gov",
        "api_type": "portal_api",
        "is_active": 0,
        "notes": "Portail fédéral US. API officielle disponible.",
    },
    {
        "code": "US_STATE_CA",
        "name": "California State Contracts",
        "country": "US",
        "region": "CA",
        "base_url": "https://caleprocure.ca.gov",
        "api_type": "portal_web",
        "is_active": 0,
        "notes": "Exemple de portail étatique.",
    },

    # --- EUROPE / INTERNATIONAL ---
    {
        "code": "TED_EU",
        "name": "Tenders Electronic Daily (EU)",
        "country": "EU",
        "region": "EU",
        "base_url": "https://ted.europa.eu",
        "api_type": "portal_api",
        "is_active": 0,
        "notes": "Journal officiel des marchés publics de l’UE.",
    },
    {
        "code": "E_PROC_IT",
        "name": "Acquisti in Rete (Italie)",
        "country": "IT",
        "region": "IT",
        "base_url": "https://www.acquistinretepa.it",
        "api_type": "portal_web",
        "is_active": 0,
        "notes": "Portail national Italie.",
    },
    {
        "code": "DGMarket",
        "name": "DGMarket",
        "country": "INTL",
        "region": "GLOBAL",
        "base_url": "https://www.dgmarket.com",
        "api_type": "aggregator",
        "is_active": 0,
        "notes": "Agrégateur multi-pays, accès/licence à valider.",
    },

    # --- ORGANISMES INTERNATIONAUX / IFI ---
    {
        "code": "UNGM",
        "name": "United Nations Global Marketplace",
        "country": "INTL",
        "region": "UN",
        "base_url": "https://www.ungm.org",
        "api_type": "portal_web",
        "is_active": 0,
        "notes": "Marchés des agences ONU.",
    },
    {
        "code": "WB_ECONSULT",
        "name": "World Bank eConsultant/eTendering",
        "country": "INTL",
        "region": "WB",
        "base_url": "https://www.worldbank.org",
        "api_type": "portal_web",
        "is_active": 0,
        "notes": "Projets financés par Banque mondiale.",
    },
    {
        "code": "AFDB",
        "name": "African Development Bank eProcurement",
        "country": "INTL",
        "region": "AFDB",
        "base_url": "https://www.afdb.org",
        "api_type": "portal_web",
        "is_active": 0,
        "notes": "Appels d’offres financés BAD.",
    },
    {
        "code": "ADB",
        "name": "Asian Development Bank eProcurement",
        "country": "INTL",
        "region": "ADB",
        "base_url": "https://www.adb.org",
        "api_type": "portal_web",
        "is_active": 0,
        "notes": "Appels d’offres financés BAD (Asie).",
    },

    # --- MOYEN-ORIENT / GOLFE (exemples à activer si besoin) ---
    {
        "code": "SAU_ETIMAD",
        "name": "Etimad Platform (Arabie Saoudite)",
        "country": "SA",
        "region": "SA",
        "base_url": "https://www.etimad.sa",
        "api_type": "portal_web",
        "is_active": 0,
        "notes": "Plateforme de marchés publics KSA.",
    },
    {
        "code": "UAE_TENDERS",
        "name": "UAE Tenders (Agrégateur)",
        "country": "AE",
        "region": "AE",
        "base_url": "https://www.uaetenders.com",
        "api_type": "aggregator",
        "is_active": 0,
        "notes": "Agrégateur privé. À valider selon stratégie.",
    },

    # --- AFRIQUE (exemples) ---
    {
        "code": "MAR_MarchesPublics",
        "name": "Marchés Publics Maroc",
        "country": "MA",
        "region": "MA",
        "base_url": "https://www.marchespublics.gov.ma",
        "api_type": "portal_web",
        "is_active": 0,
        "notes": "Portail national Maroc.",
    },
    {
        "code": "TN_TUNEPS",
        "name": "TUNEPS (Tunisie)",
        "country": "TN",
        "region": "TN",
        "base_url": "https://www.tuneps.tn",
        "api_type": "portal_web",
        "is_active": 0,
        "notes": "Plateforme e-proc Tunisie.",
    },
]


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Base SQLite introuvable: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # On repart propre sur la table source_portals
    cur.execute("DROP TABLE IF EXISTS source_portals;")

    cur.execute(
        """
        CREATE TABLE source_portals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT,
            country TEXT,
            region TEXT,
            base_url TEXT,
            api_type TEXT,
            is_active INTEGER DEFAULT 1,
            notes TEXT
        );
        """
    )

    for p in PORTALS:
        cur.execute(
            """
            INSERT INTO source_portals
            (code, name, country, region, base_url, api_type, is_active, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p["code"],
                p["name"],
                p["country"],
                p["region"],
                p["base_url"],
                p["api_type"],
                p["is_active"],
                p["notes"],
            ),
        )

    conn.commit()
    conn.close()

    print(f"Synchronisé {len(PORTALS)} portails dans source_portals.")


if __name__ == "__main__":
    main()
