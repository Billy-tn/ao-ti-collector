from pathlib import Path
import sqlite3

ROOT_DIR = Path(__file__).resolve().parents[2]

SOURCE_DB = ROOT_DIR / "ao.db"
TARGET_DB = ROOT_DIR / "database" / "ao_collector.db"

# None = toutes les lignes
# 100, 1000, 10000, 50000 pour les tests
LIMIT = None


def get_or_create_organization(conn, name, org_type):
    if not name:
        return None

    cur = conn.cursor()

    cur.execute(
        """
        SELECT id
        FROM organizations
        WHERE source = ?
          AND org_id = ?
        """,
        ("SEAO", name),
    )

    row = cur.fetchone()

    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO organizations
        (
            source,
            org_id,
            name,
            org_type
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            "SEAO",
            name,
            name,
            org_type,
        ),
    )

    return cur.lastrowid


def main():
    source_conn = sqlite3.connect(SOURCE_DB)
    target_conn = sqlite3.connect(TARGET_DB)

    try:
        source_cur = source_conn.cursor()

        query = """
        SELECT
            ocid,
            title,
            buyer,
            published_at,
            procurement_method,
            category,
            url,
            supplier_name,
            award_amount,
            award_currency,
            award_status,
            unspsc
        FROM tenders_v2
        """

        if LIMIT is not None:
            query += f"\nLIMIT {LIMIT}"

        source_cur.execute(query)

        rows = source_cur.fetchall()

        print(f"[INFO] LIMIT = {LIMIT}")
        print(f"[INFO] Lignes trouvées : {len(rows)}")

        inserted_tenders = 0
        inserted_awards = 0

        for row in rows:
            (
                ocid,
                title,
                buyer,
                published_at,
                procurement_method,
                category,
                url,
                supplier_name,
                award_amount,
                award_currency,
                award_status,
                unspsc,
            ) = row

            buyer_org_id = get_or_create_organization(
                target_conn,
                buyer,
                "buyer",
            )

            supplier_org_id = get_or_create_organization(
                target_conn,
                supplier_name,
                "supplier",
            )

            cur = target_conn.cursor()

            cur.execute(
                """
                INSERT OR IGNORE INTO tenders_mi
                (
                    source,
                    ocid,
                    title,
                    buyer_org_id,
                    published_at,
                    procurement_method,
                    main_procurement_category,
                    url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "SEAO",
                    ocid,
                    title,
                    buyer_org_id,
                    published_at,
                    procurement_method,
                    category,
                    url,
                ),
            )

            cur.execute(
                """
                SELECT id
                FROM tenders_mi
                WHERE ocid = ?
                """,
                (ocid,),
            )

            tender_id = cur.fetchone()[0]

            # Participants

            if buyer_org_id:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO tender_participants
                    (
                        tender_id,
                        organization_id,
                        role
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        tender_id,
                        buyer_org_id,
                        "buyer",
                    ),
                )

            if supplier_org_id:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO tender_participants
                    (
                        tender_id,
                        organization_id,
                        role
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        tender_id,
                        supplier_org_id,
                        "supplier",
                    ),
                )

            # Classifications

            if category:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO tender_classifications
                    (
                        tender_id,
                        classification_type,
                        code
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        tender_id,
                        "CATEGORY",
                        category,
                    ),
                )

            if unspsc:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO tender_classifications
                    (
                        tender_id,
                        classification_type,
                        code
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        tender_id,
                        "UNSPSC",
                        unspsc,
                    ),
                )

            inserted_tenders += 1

            if supplier_org_id:
                cur.execute(
                    """
                    INSERT INTO awards
                    (
                        tender_id,
                        organization_id,
                        award_status,
                        amount,
                        currency
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        tender_id,
                        supplier_org_id,
                        award_status,
                        award_amount,
                        award_currency,
                    ),
                )

                inserted_awards += 1

        target_conn.commit()

        print(f"[OK] Tenders chargés : {inserted_tenders}")
        print(f"[OK] Awards chargés : {inserted_awards}")

    finally:
        source_conn.close()
        target_conn.close()


if __name__ == "__main__":
    main()