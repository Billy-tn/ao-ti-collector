from backend.connectors.seao_connector import SEAOConnector
import requests
from pathlib import Path
import sqlite3

MAX_MONTHS = 58

ROOT_DIR = Path(__file__).resolve().parents[2]

DB_PATH = ROOT_DIR / "database" / "ao_collector.db"


def get_or_create_org(
    conn,
    source,
    org_id,
    name,
    org_type,
    address=None,
):

    if not org_id:
        return None

    address = address or {}

    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO organizations
        (
            source,
            org_id,
            name,
            org_type,
            street_address,
            city,
            region,
            postal_code,
            country
        )
        VALUES
        (
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            source,
            org_id,
            name or "",
            org_type,
            address.get("streetAddress"),
            address.get("locality"),
            address.get("region"),
            address.get("postalCode"),
            address.get("countryName"),
        ),
    )

    cur.execute(
        """
        UPDATE organizations
        SET
            street_address = COALESCE(
                street_address,
                ?
            ),
            city = COALESCE(
                city,
                ?
            ),
            region = COALESCE(
                region,
                ?
            ),
            postal_code = COALESCE(
                postal_code,
                ?
            ),
            country = COALESCE(
                country,
                ?
            )
        WHERE source = ?
          AND org_id = ?
        """,
        (
            address.get("streetAddress"),
            address.get("locality"),
            address.get("region"),
            address.get("postalCode"),
            address.get("countryName"),
            source,
            org_id,
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

        cur = conn.cursor()

        resources = SEAOConnector().get_resources()

        monthly = {}

        for r in resources:

            name = r.get("name") or ""

            if not name.startswith("mensuel_"):
                continue

            monthly[name] = r

        months = sorted(monthly.keys())

        print(
            f"[INFO] Mensuels uniques : {len(months)}"
        )

        selected = months[:MAX_MONTHS]

        print(
            f"[INFO] Mois à traiter : {len(selected)}"
        )

        total_releases = 0

        for month_name in selected:

            resource = monthly[month_name]

            print(
                f"\n[INFO] Traitement : {month_name}"
            )

            data = requests.get(
                resource["url"],
                timeout=120,
            ).json()

            releases = data.get(
                "releases",
                [],
            )

            count = len(releases)

            total_releases += count

            print(
                f"[INFO] Releases : {count}"
            )

            for release in releases:
                # -------------------------
                # PARTIES
                # -------------------------

                for party in release.get(
                    "parties",
                    [],
                ):

                    roles = party.get(
                        "roles",
                        [],
                    )

                    org_type = (
                        roles[0]
                        if roles
                        else "unknown"
                    )

                    get_or_create_org(
                        conn,
                        "SEAO",
                        party.get("id"),
                        party.get("name"),
                        org_type,
                        party.get("address"),
                    )
                # -------------------------
                # BUYER
                # -------------------------

                buyer = release.get(
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

                # -------------------------
                # TENDER
                # -------------------------

                tender = release.get(
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
                        tender_end_date,
                        procurement_method,
                        procurement_method_details,
                        main_procurement_category,
                        number_of_tenderers,
                        url
                )
                VALUES
                (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                    """,
                    (
                        "SEAO",
                        release.get("ocid"),
                        tender.get("title")
                        or "Sans titre",
                        tender.get("status"),
                        buyer_org_id,
                        release.get("date"),
                        tender_period.get("startDate"),
                        tender_period.get("endDate"),
                        tender.get("procurementMethod"),
                        tender.get("procurementMethodDetails"),
                        tender.get("mainProcurementCategory"),
                        tender.get("numberOfTenderers"),
                        (
                            tender.get("documents", [{}])[0]
                            .get("url")
                            if tender.get("documents")
                            else None
                        ),
)
                )

                cur.execute(
                    """
                    SELECT id
                    FROM tenders_mi
                    WHERE ocid = ?
                    """,
                    (
                        release.get("ocid"),
                    ),
                )

                row = cur.fetchone()

                if not row:
                    continue

                tender_id = row[0]

                supplier_org_id = None

                # -------------------------
                # AWARDS
                # -------------------------

                awards = release.get(
                    "awards",
                    [],
                )

                for award in awards:

                    suppliers = award.get(
                        "suppliers",
                        [],
                    )

                    if suppliers:

                        supplier = suppliers[0]

                        supplier_org_id = (
                            get_or_create_org(
                                conn,
                                "SEAO",
                                supplier.get("id"),
                                supplier.get("name"),
                                "supplier",
                            )
                        )

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
                        VALUES
                        (
                            ?, ?, ?, ?, ?, ?
                        )
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

                # -------------------------
                # CONTRACTS
                # -------------------------

                contracts = release.get(
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
                # -------------------------
                # TENDER PARTICIPANTS
                # -------------------------

                for tenderer in tender.get(
                    "tenderers",
                    [],
                ):

                    org_id = get_or_create_org(
                        conn,
                        "SEAO",
                        tenderer.get("id"),
                        tenderer.get("name"),
                        "supplier",
                    )

                    if org_id:

                        cur.execute(
                            """
                            INSERT OR IGNORE
                            INTO tender_participants
                            (
                                tender_id,
                                organization_id,
                                role
                            )
                            VALUES
                            (
                                ?, ?, ?
                            )
                            """,
                            (
                                tender_id,
                                org_id,
                                "tenderer",
                            ),
                        )
                # -------------------------
                # CLASSIFICATIONS
                # -------------------------

                for item in tender.get(
                    "items",
                    [],
                ):

                    classification = item.get(
                        "classification",
                        {},
                    )

                    if classification:

                        cur.execute(
                            """
                            INSERT OR IGNORE
                            INTO tender_classifications
                            (
                                tender_id,
                                classification_type,
                                code,
                                description,
                                is_primary
                            )
                            VALUES
                            (
                                ?, ?, ?, ?, ?
                            )
                            """,
                            (
                                tender_id,
                                classification.get(
                                    "scheme"
                                ),
                                classification.get(
                                    "id"
                                ),
                                classification.get(
                                    "description"
                                ),
                                1,
                            ),
                        )

                    for extra in item.get(
                        "additionalClassifications",
                        [],
                    ):

                        cur.execute(
                            """
                            INSERT OR IGNORE
                            INTO tender_classifications
                            (
                                tender_id,
                                classification_type,
                                code,
                                description,
                                is_primary
                            )
                            VALUES
                            (
                                ?, ?, ?, ?, ?
                            )
                            """,
                            (
                                tender_id,
                                extra.get(
                                    "scheme"
                                ),
                                extra.get(
                                    "id"
                                ),
                                extra.get(
                                    "description"
                                ),
                                0,
                            ),
                        )        
                # -------------------------
                # DOCUMENTS
                # -------------------------

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
                        VALUES
                        (
                            ?, ?, ?
                        )
                        """,
                        (
                            tender_id,
                            doc.get("url"),
                            doc.get("documentType"),
                        ),
                    )

                # -------------------------
                # RELATED PROCESSES
                # -------------------------

                related_processes = release.get(
                    "relatedProcesses",
                    [],
                )

                for rp in related_processes:

                    relationship = None

                    rel = rp.get(
                        "relationship",
                        [],
                    )

                    if rel:
                        relationship = ",".join(rel)

                    cur.execute(
                        """
                        INSERT INTO related_processes
                        (
                            tender_id,
                            relationship,
                            identifier,
                            title
                        )
                        VALUES
                        (
                            ?, ?, ?, ?
                        )
                        """,
                        (
                            tender_id,
                            relationship,
                            rp.get("identifier"),
                            rp.get("title"),
                        ),
                    )

                # -------------------------
                # BIDS
                # -------------------------

                bids = release.get(
                    "bids",
                    [],
                )

                for bid in bids:

                    cur.execute(
                        """
                        INSERT INTO bids
                        (
                            tender_id,
                            organization_id,
                            bid_reference,
                            amount,
                            currency,
                            lot_reference
                        )
                        VALUES
                        (
                            ?, ?, ?, ?, ?, ?
                        )
                        """,
                        (
                            tender_id,
                            None,
                            bid.get("id"),
                            bid.get("value"),
                            None,
                            bid.get("valueUnit"),
                        ),
                    )
        conn.commit()

        print()

        print(
            f"[INFO] Total releases : "
            f"{total_releases}"
        )

    finally:

        conn.close()


if __name__ == "__main__":
    main()