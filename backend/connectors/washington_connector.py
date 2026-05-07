from typing import List

import requests
from bs4 import BeautifulSoup

from .base import BaseConnector, Tender


WASHINGTON_URL = (
    "https://pr-webs-vendor.des.wa.gov/BidCalendar.aspx"
)


class WashingtonConnector(BaseConnector):
    name = "Washington WEBS"

    def fetch(self) -> List[Tender]:
        print("[Washington WEBS] Fetch starting...")

        tenders: List[Tender] = []

        try:
            r = requests.get(
                WASHINGTON_URL,
                timeout=60,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            r.raise_for_status()

            soup = BeautifulSoup(r.text, "html.parser")

            rows = soup.find_all("tr")

            for row in rows:

                text = row.get_text(
                    " ",
                    strip=True
                )

                if not text:
                    continue

                if "Ref #:" not in text:
                    continue

                if len(text) < 20:
                    continue

                title = text

                link = row.find("a")

                url = WASHINGTON_URL

                if link and link.get("href"):
                    href = link.get("href")

                    if href.startswith("http"):
                        url = href
                    else:
                        url = (
                            "https://pr-webs-vendor.des.wa.gov/"
                            + href.lstrip("/")
                        )

                tenders.append(
                    Tender(
                        source="Washington WEBS",
                        portal_name="Washington WEBS",
                        title=title[:300],
                        url=url,
                        buyer="Washington State",
                        published_at="",
                        country="US",
                        region="WA",
                        summary=text[:500],
                        confidence=0.90,
                    )
                )

                if len(tenders) >= 20:
                    break

            print(
                f"[Washington WEBS] Loaded {len(tenders)} tenders"
            )

        except Exception as e:
            print(f"[Washington WEBS] ERROR: {e}")

        return tenders