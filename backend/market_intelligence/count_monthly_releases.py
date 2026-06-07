from backend.connectors.seao_connector import SEAOConnector
import requests


def main():

    resources = SEAOConnector().get_resources()

    monthly = {}

    for r in resources:

        name = r.get("name") or ""

        if not name.startswith("mensuel_"):
            continue

        monthly[name] = r

    print(
        f"[INFO] Mensuels uniques : {len(monthly)}"
    )

    total_releases = 0

    for name in sorted(monthly.keys()):

        resource = monthly[name]

        url = resource.get("url")

        try:

            data = requests.get(
                url,
                timeout=120,
            ).json()

            releases = data.get(
                "releases",
                [],
            )

            count = len(releases)

            total_releases += count

            print(
                f"{name} : {count}"
            )

        except Exception as e:

            print(
                f"[ERROR] {name} : {e}"
            )

    print()
    print(
        f"TOTAL RELEASES : {total_releases}"
    )


if __name__ == "__main__":
    main()