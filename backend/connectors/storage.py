import sqlite3
from pathlib import Path
from typing import List

from .base import Tender


DB_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "ao.db"
)


def get_conn():

    conn = sqlite3.connect(DB_PATH)

    return conn


def ensure_table():

    conn = get_conn()

    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tenders_v2 (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            source TEXT,
            portal_name TEXT,

            title TEXT,
            url TEXT UNIQUE,

            buyer TEXT,
            published_at TEXT,

            country TEXT,
            region TEXT,

            summary TEXT,
            source_domain TEXT,

            confidence REAL,

            ocid TEXT,

            category TEXT,
            procurement_method TEXT,

            documents_url TEXT,

            supplier_name TEXT,

            award_amount REAL,
            award_currency TEXT,

            contact_name TEXT,
            contact_email TEXT,

            unspsc TEXT,

            notice_type TEXT,

            delivery_region TEXT,

            award_status TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    existing_cols = [

        row[1]

        for row in cur.execute(
            "PRAGMA table_info(tenders_v2)"
        ).fetchall()
    ]

    migrations = {

        "category": "TEXT",

        "procurement_method": "TEXT",

        "documents_url": "TEXT",

        "supplier_name": "TEXT",

        "award_amount": "REAL",

        "award_currency": "TEXT",

        "contact_name": "TEXT",

        "contact_email": "TEXT",

        "unspsc": "TEXT",

        "notice_type": "TEXT",

        "delivery_region": "TEXT",

        "award_status": "TEXT",
    }

    for col, sql_type in migrations.items():

        if col not in existing_cols:

            cur.execute(
                f"""
                ALTER TABLE tenders_v2
                ADD COLUMN {col} {sql_type}
                """
            )

            print(
                f"[storage] added column: {col}"
            )

    conn.commit()

    conn.close()


def save_tenders(
    tenders: List[Tender]
):

    ensure_table()

    conn = get_conn()

    cur = conn.cursor()

    inserted = 0

    for t in tenders:

        try:

            cur.execute(
                """
                INSERT OR IGNORE INTO tenders_v2 (

                    source,
                    portal_name,

                    title,
                    url,

                    buyer,
                    published_at,

                    country,
                    region,

                    summary,
                    source_domain,

                    confidence,

                    ocid,

                    category,
                    procurement_method,

                    documents_url,

                    supplier_name,

                    award_amount,
                    award_currency,

                    contact_name,
                    contact_email,

                    unspsc,

                    notice_type,

                    delivery_region,

                    award_status
                )

                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    t.source,
                    t.portal_name,

                    t.title,
                    t.url,

                    t.buyer,
                    t.published_at,

                    t.country,
                    t.region,

                    t.summary,
                    t.source_domain,

                    t.confidence,

                    t.ocid,

                    t.category,
                    t.procurement_method,

                    t.documents_url,

                    t.supplier_name,

                    t.award_amount,
                    t.award_currency,

                    t.contact_name,
                    t.contact_email,

                    t.unspsc,

                    t.notice_type,

                    t.delivery_region,

                    t.award_status,
                ),
            )

            inserted += cur.rowcount

        except Exception as e:

            print(
                f"[storage] insert error: {e}"
            )

    conn.commit()

    conn.close()

    print(
        f"[storage] inserted "
        f"{inserted} tenders"
    )