from typing import List
import datetime as dt

import requests

from .base import BaseConnector, Tender


SEAO_PACKAGE_ID = "systeme-electronique-dappel-doffres-seao"

SEAO_PACKAGE_URL = (
    "https://www.donneesquebec.ca/recherche/api/3/action/package_show"
)


class SEAOConnector(BaseConnector):
    name = "SEAO"

    def get_resources(self):
        try:
            resp = requests.get(
                SEAO_PACKAGE_URL,
                params={"id": SEAO_PACKAGE_ID},
                timeout=30,
            )

            resp.raise_for_status()

            data = resp.json()

            return data.get(
                "result",
                {},
            ).get("resources", [])

        except Exception as e:
            print(
                f"[SEAO] ERROR loading resources: {e}"
            )
            return []

    def parse_date(self, value: str):

        if not value:
            return None

        value = value.strip()

        for fmt in (
            "%Y-%m-%d",
            "%Y/%m/%d",
        ):
            try:
                return dt.datetime.strptime(
                    value[:10],
                    fmt,
                ).date()

            except ValueError:
                pass

        try:
            return dt.datetime.fromisoformat(
                value.replace("Z", "")
            ).date()

        except Exception:
            return None

    def normalize_release(
        self,
        release: dict,
    ):

        tender = release.get(
            "tender",
            {},
        ) or {}

        title = (
            tender.get("title")
            or release.get("title")
            or ""
        )

        buyer_name = ""

        buyer = release.get("buyer") or {}

        buyer_name = buyer.get("name") or ""

        if not buyer_name:

            for p in release.get("parties") or []:

                roles = p.get("roles") or []

                if any(
                    r.lower() == "buyer"
                    for r in roles
                ):
                    buyer_name = (
                        p.get("name") or ""
                    )
                    break

        date_str = (
            release.get("date")
            or (
                tender.get("tenderPeriod")
                or {}
            ).get("startDate")
        )

        pub_date = self.parse_date(date_str)

        url = ""
        documents_url = ""

        documents = (
            tender.get("documents") or []
        )

        for doc in documents:

            if doc.get("url"):

                if not url:
                    url = doc["url"]

                documents_url = doc["url"]

                break

        category = (
            tender.get(
                "mainProcurementCategory"
            )
            or ""
        )

        procurement_method = (
            tender.get(
                "procurementMethodDetails"
            )
            or tender.get(
                "procurementMethod"
            )
            or ""
        )

        summary = ""

        items = (
            tender.get("items") or []
        )

        if items:
            summary = (
                items[0].get("description")
                or ""
            )

        return Tender(
            source="SEAO",

            portal_name="SEAO",

            title=title.strip(),

            url=url.strip(),

            buyer=buyer_name.strip(),

            published_at=str(pub_date or ""),

            country="CA",

            region="QC",

            summary=summary.strip(),

            confidence=0.95,

            ocid=release.get(
                "ocid",
                "",
            ),

            category=category.strip(),

            procurement_method=(
                procurement_method.strip()
            ),

            documents_url=(
                documents_url.strip()
            ),
        )

    def fetch(self) -> List[Tender]:

        print("[SEAO] Fetch starting...")

        resources = self.get_resources()

        tenders: List[Tender] = []

        json_resources = [
            r for r in resources
            if (
                r.get("format") or ""
            ).lower() == "json"
        ]

        for r in json_resources[:2]:

            resource_url = r.get("url")

            if not resource_url:
                continue

            print(
                f"[SEAO] Loading resource: "
                f"{resource_url}"
            )

            try:
                resp = requests.get(
                    resource_url,
                    timeout=120,
                )

                resp.raise_for_status()

                data = resp.json()

                releases = data.get(
                    "releases",
                    [],
                )

                for release in releases[:20]:

                    try:
                        tender = (
                            self.normalize_release(
                                release
                            )
                        )

                        if (
                            tender
                            and tender.title
                        ):
                            tenders.append(
                                tender
                            )

                    except Exception as e:
                        print(
                            f"[SEAO] "
                            f"normalize error: {e}"
                        )

            except Exception as e:
                print(
                    f"[SEAO] "
                    f"resource load error: {e}"
                )

        print(
            f"[SEAO] Loaded "
            f"{len(tenders)} tenders"
        )

        return tenders