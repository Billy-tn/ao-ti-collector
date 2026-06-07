from pathlib import Path
import sqlite3
import requests

from backend.connectors.seao_connector import SEAOConnector


ROOT_DIR = Path(__file__).resolve().parents[2]

DB_PATH = ROOT_DIR / "database" / "ao_collector.db"


def get_or_create_org(
    conn,
    source,
    org_id,
    name,
    org_type,
):

    if not org_id:
        return None

    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO organizations
        (
            source,
            org_id,
            name,
            org_type
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            source,
            org_id,
            name or "",
            org_type,
        ),
    )

    cur.execute(
        """
        SELECT id
        FROM organizations
        WHERE source = ?
          AND org_id = ?
        """,
        (
            source,
            org_id,
        ),
    )

    row = cur.fetchone()

    return row[0] if row else None


def main():

    conn = sqlite3.connect(DB_PATH)

    try:

        connector = SEAOConnector()

        resources = connector.get_resources()

        resource = resources[0]

        url = resource.get("url")

        print(f"[INFO] Chargement : {url}")

        data = requests.get(
            url,
            timeout=120,
        ).json()

        releases = data.get(
            "releases",
            [],
        )

        print(
            f"[INFO] Releases trouvées : {len(releases)}"
        )

        processed = 0

        for first in releases:

            cur = conn.cursor()

            # ---------------- BUYER ----------------

            buyer = first.get(
                "buyer",
                {},
            )

            buyer_org_id = get_or_create_org(
                conn,
                "SEAO",
                buyer.get("id"),
                buyer.get("name"),
                "buyer",
            )

            # ---------------- SUPPLIER ----------------

            supplier_org_id = None

            awards = first.get(
                "awards",
                [],
            )

            if awards:

                suppliers = awards[0].get(
                    "suppliers",
                    [],
                )

                if suppliers:

                    supplier = suppliers[0]

                    supplier_org_id = get_or_create_org(
                        conn,
                        "SEAO",
                        supplier.get("id"),
                        supplier.get("name"),
                        "supplier",
                    )

            # ---------------- TENDER ----------------

            tender = first.get(
                "tender",
                {},
            )

            tender_period = tender.get(
                "tenderPeriod",
                {},
            )

            cur.execute(
                """
                INSERT OR IGNORE INTO tenders_mi
                (
                    source,
                    ocid,
                    title,
                    status,
                    buyer_org_id,
                    published_at,
                    tender_start_date,
                    procurement_method,
                    procurement_method_details,
                    main_procurement_category,
                    number_of_tenderers
                )
                VALUES
                (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    "SEAO",
                    first.get("ocid"),
                    tender.get("title"),
                    tender.get("status"),
                    buyer_org_id,
                    first.get("date"),
                    tender_period.get("startDate"),
                    tender.get("procurementMethod"),
                    tender.get("procurementMethodDetails"),
                    tender.get("mainProcurementCategory"),
                    tender.get("numberOfTenderers"),
                ),
            )

            cur.execute(
                """
                SELECT id
                FROM tenders_mi
                WHERE ocid = ?
                """,
                (
                    first.get("ocid"),
                ),
            )

            row = cur.fetchone()

            if not row:
                continue

            tender_id = row[0]

            # ---------------- AWARDS ----------------

            for award in awards:

                value = award.get(
                    "value",
                    {},
                )

                cur.execute(
                    """
                    INSERT INTO awards
                    (
                        tender_id,
                        organization_id,
                        award_status,
                        award_date,
                        amount,
                        currency
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tender_id,
                        supplier_org_id,
                        award.get("status"),
                        award.get("date"),
                        value.get("amount"),
                        value.get("currency"),
                    ),
                )

            # ---------------- CONTRACTS ----------------

            contracts = first.get(
                "contracts",
                [],
            )

            for contract in contracts:

                value = contract.get(
                    "value",
                    {},
                )

                period = contract.get(
                    "period",
                    {},
                )

                cur.execute(
                    """
                    INSERT INTO contracts
                    (
                        tender_id,
                        organization_id,
                        contract_status,
                        amount,
                        currency,
                        date_signed,
                        start_date,
                        end_date
                    )
                    VALUES
                    (
                        ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        tender_id,
                        supplier_org_id,
                        contract.get("status"),
                        value.get("amount"),
                        value.get("currency"),
                        contract.get("dateSigned"),
                        period.get("startDate"),
                        period.get("endDate"),
                    ),
                )

            # ---------------- DOCUMENTS ----------------

            documents = tender.get(
                "documents",
                [],
            )

            for doc in documents:

                cur.execute(
                    """
                    INSERT INTO documents
                    (
                        tender_id,
                        document_url,
                        document_type
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        tender_id,
                        doc.get("url"),
                        doc.get("documentType"),
                    ),
                )

            processed += 1

        conn.commit()

        print(
            f"[OK] Releases traités : {processed}"
        )

    finally:

        conn.close()


if __name__ == "__main__":
    main()