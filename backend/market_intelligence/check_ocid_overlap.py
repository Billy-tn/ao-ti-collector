from backend.connectors.seao_connector import SEAOConnector
import requests


def load_ocids(resource):

    url = resource.get("url")

    print(f"[INFO] Chargement : {resource.get('name')}")

    data = requests.get(
        url,
        timeout=120,
    ).json()

    releases = data.get(
        "releases",
        [],
    )

    return {
        release.get("ocid")
        for release in releases
        if release.get("ocid")
    }


def main():

    resources = (
        SEAOConnector()
        .get_resources()
    )

    monthly = None
    weekly = None

    for r in resources:

        name = (
            r.get("name")
            or ""
        )

        if (
            name
            == "mensuel_20260501_20260531.json"
        ):
            monthly = r

        if (
            name
            == "hebdo_20260525_20260531.json"
        ):
            weekly = r

    if not monthly:
        print(
            "[ERROR] Mensuel introuvable"
        )
        return

    if not weekly:
        print(
            "[ERROR] Hebdo introuvable"
        )
        return

    monthly_ocids = load_ocids(
        monthly
    )

    weekly_ocids = load_ocids(
        weekly
    )

    overlap = (
        monthly_ocids
        & weekly_ocids
    )

    print()

    print(
        f"Mensuel : {len(monthly_ocids)}"
    )

    print(
        f"Hebdo   : {len(weekly_ocids)}"
    )

    print(
        f"Commun  : {len(overlap)}"
    )

    if weekly_ocids:

        pct = (
            len(overlap)
            / len(weekly_ocids)
            * 100
        )

        print(
            f"Overlap hebdo : "
            f"{pct:.2f}%"
        )


if __name__ == "__main__":
    main()