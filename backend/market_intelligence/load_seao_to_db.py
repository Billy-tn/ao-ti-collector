from pathlib import Path
import sqlite3
import requests

from backend.connectors.seao_connector import SEAOConnector


ROOT_DIR = Path(__file__).resolve().parents[2]

DB_PATH = ROOT_DIR / "database" / "ao_collector.db"


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
            f"[INFO] Releases : {len(releases)}"
        )

        first = releases[0]

        buyer = first.get(
            "buyer",
            {},
        )

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
                "SEAO",
                buyer.get("id"),
                buyer.get("name"),
                "buyer",
            ),
        )

        conn.commit()

        print("[OK] Buyer inséré")

        cur.execute(
            """
            SELECT id
            FROM organizations
            WHERE source = ?
              AND org_id = ?
            """,
            (
                "SEAO",
                buyer.get("id"),
            ),
        )

        buyer_org_id = cur.fetchone()[0]

        print(
            f"[INFO] buyer_org_id = {buyer_org_id}"
        )

        tender = first.get(
            "tender",
            {},
        )

        print("\n=== TENDER DETAILS ===")

        print(
            "status:",
            tender.get("status")
        )

        print(
            "tenderPeriod:",
            tender.get("tenderPeriod")
        )

        print(
            "procurementMethod:",
            tender.get("procurementMethod")
        )

        print(
            "procurementMethodDetails:",
            tender.get("procurementMethodDetails")
        )

        print(
            "mainProcurementCategory:",
            tender.get("mainProcurementCategory")
        )

        print(
            "numberOfTenderers:",
            tender.get("numberOfTenderers")
        )

        print(
            "documents:",
            len(
                tender.get(
                    "documents",
                    []
                )
            )
        )

        print("\n=== RELEASE KEYS ===")

        for key in first.keys():
            print(key)

        print(
            "\nrelatedProcesses:",
            len(
                first.get(
                    "relatedProcesses",
                    []
                )
            )
        )

        print(
            "awards:",
            len(
                first.get(
                    "awards",
                    []
                )
            )
        )

        print(
            "contracts:",
            len(
                first.get(
                    "contracts",
                    []
                )
            )
        )

        print("\n=== FIRST AWARD ===")

        awards = first.get(
            "awards",
            []
        )

        if awards:
            print(awards[0])

        print("\n=== FIRST DOCUMENT ===")

        documents = tender.get(
            "documents",
            []
        )

        if documents:
            print(documents[0])

    finally:

        conn.close()


if __name__ == "__main__":
    main()