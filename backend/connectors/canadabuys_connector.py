from typing import List
import csv
import io

import requests

from .base import BaseConnector, Tender


CANADABUYS_CSV_URL = (
    "https://canadabuys.canada.ca/opendata/pub/newTenderNotice-nouvelAvisAppelOffres.csv"
)


class CanadaBuysConnector(BaseConnector):
    name = "CanadaBuys"

    def fetch(self) -> List[Tender]:
        print("[CanadaBuys] Fetch starting...")

        tenders: List[Tender] = []

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/csv,application/octet-stream,*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            resp = requests.get(
                CANADABUYS_CSV_URL,
                headers=headers,
                timeout=120,
            )

            resp.raise_for_status()

            content = resp.content.decode(
                "utf-8",
                errors="ignore",
            )

            reader = csv.DictReader(io.StringIO(content))

            print("[CanadaBuys] CSV columns loaded")

            for row in list(reader)[:50]:

                title = (
                    row.get("title-titre-eng")
                    or row.get("title-titre-fra")
                    or ""
                )

                url = (
                    row.get("noticeURL-URLavis-eng")
                    or row.get("noticeURL-URLavis-fra")
                    or ""
                )

                buyer = (
                    row.get(
                        "contractingEntityName-nomEntitContractante-eng"
                    )
                    or row.get(
                        "contractingEntityName-nomEntitContractante-fra"
                    )
                    or ""
                )

                published_at = (
                    row.get("publicationDate-datePublication")
                    or ""
                )

                if not title:
                    continue

                tenders.append(
                    Tender(
                        source="CanadaBuys",
                        portal_name="CanadaBuys",
                        title=title.strip(),
                        url=url.strip(),
                        buyer=buyer.strip(),
                        published_at=published_at.strip(),
                        country="CA",
                        region="FED",
                        confidence=0.95,
                    )
                )

            print(f"[CanadaBuys] Loaded {len(tenders)} tenders")

        except Exception as e:
            print(f"[CanadaBuys] ERROR: {e}")

        return tenders