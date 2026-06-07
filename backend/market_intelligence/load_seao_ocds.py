from backend.connectors.seao_connector import SEAOConnector
import requests

connector = SEAOConnector()

resources = connector.get_resources()

print(f"[INFO] Resources trouvées : {len(resources)}")

resource = resources[0]

url = resource.get("url")

print(f"[INFO] Chargement : {url}")

resp = requests.get(url, timeout=120)

data = resp.json()

releases = data.get("releases", [])

print(f"[INFO] Releases trouvées : {len(releases)}")

if releases:

    first = releases[0]

    print("[INFO] OCID :", first.get("ocid"))

    buyer = first.get("buyer", {})

    print("\n=== BUYER ===")
    print(buyer)

    tender = first.get("tender", {})

    print("\n=== TENDER ===")
    print("OCID:", first.get("ocid"))
    print("Title:", tender.get("title"))
    print("Status:", tender.get("status"))

    contracts = first.get("contracts", [])

    print(f"\n[INFO] Contracts trouvés : {len(contracts)}")

    if contracts:

        contract = contracts[0]

        print(contract)

        print(
            "[INFO] End date :",
            contract.get("period", {}).get("endDate")
        )

contracts_total = 0
contracts_with_end_date = 0

for release in releases:

    for contract in release.get("contracts", []):

        contracts_total += 1

        if contract.get("period", {}).get("endDate"):
            contracts_with_end_date += 1

print(f"\n[INFO] Contracts total : {contracts_total}")

print(
    f"[INFO] Contracts avec endDate : "
    f"{contracts_with_end_date}"
)