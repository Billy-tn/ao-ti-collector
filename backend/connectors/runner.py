from .seao_connector import SEAOConnector
from .canadabuys_connector import CanadaBuysConnector
from .samgov_connector import SAMGovConnector
from .washington_connector import WashingtonConnector

from .storage import save_tenders

from .document_downloader import download_file


def run_all():

    connectors = [

        SEAOConnector(),

        CanadaBuysConnector(),

        SAMGovConnector(),

        WashingtonConnector(),
    ]

    all_tenders = []

    for connector in connectors:

        print(
            f"\n=== Running {connector.name} ==="
        )

        try:

            results = connector.fetch()

            print(
                f"[{connector.name}] "
                f"returned {len(results)} tenders"
            )

            all_tenders.extend(results)

        except Exception as e:

            print(
                f"[{connector.name}] FAILED: {e}"
            )

    print(
        f"\nTOTAL TENDERS: {len(all_tenders)}"
    )

    # -----------------------------------------
    # Save tenders
    # -----------------------------------------

    save_tenders(all_tenders)

    # -----------------------------------------
    # Download documents
    # -----------------------------------------

    print("\n=== Downloading documents ===")

    downloaded = 0

    for t in all_tenders[:10]:

        doc_url = (
            t.documents_url
            or t.url
        )

        if not doc_url:
            continue

        result = download_file(
            url=doc_url,
            source=t.source,
            ocid=t.ocid or t.title,
        )

        if result:
            downloaded += 1

    print(
        f"\nDOCUMENTS DOWNLOADED: "
        f"{downloaded}"
    )

    return all_tenders


if __name__ == "__main__":

    run_all()