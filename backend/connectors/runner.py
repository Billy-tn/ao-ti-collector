from .seao_connector import SEAOConnector
from .canadabuys_connector import CanadaBuysConnector
from .samgov_connector import SAMGovConnector
from .washington_connector import WashingtonConnector

from .storage import save_tenders


def run_all():
    connectors = [
        SEAOConnector(),
        CanadaBuysConnector(),
        SAMGovConnector(),
        WashingtonConnector(),
    ]

    all_tenders = []

    for connector in connectors:
        print(f"\n=== Running {connector.name} ===")

        try:
            results = connector.fetch()

            print(
                f"[{connector.name}] returned {len(results)} tenders"
            )

            all_tenders.extend(results)

        except Exception as e:
            print(f"[{connector.name}] FAILED: {e}")

    print(f"\nTOTAL TENDERS: {len(all_tenders)}")

    save_tenders(all_tenders)

    return all_tenders


if __name__ == "__main__":
    run_all()