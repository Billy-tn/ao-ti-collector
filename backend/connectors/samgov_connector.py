from typing import List
from datetime import date, timedelta

import requests

from .base import BaseConnector, Tender


SAM_API_URL = (
    "https://api.sam.gov/opportunities/v2/search"
)

API_KEY = (
    "SAM-23195f2e-8aaf-4e06-a9ac-17640b0948f9"
)


class SAMGovConnector(BaseConnector):

    name = "SAM.gov"

    def fetch(self) -> List[Tender]:

        print("[SAM.gov] Fetch starting...")

        tenders: List[Tender] = []

        today = date.today()

        week_ago = (
            today - timedelta(days=7)
        )

        params = {

            "api_key": API_KEY,

            "limit": 20,

            "postedFrom": (
                week_ago.strftime("%m/%d/%Y")
            ),

            "postedTo": (
                today.strftime("%m/%d/%Y")
            ),
        }

        try:

            r = requests.get(
                SAM_API_URL,
                params=params,
                timeout=60,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            r.raise_for_status()

            data = r.json()

            opportunities = data.get(
                "opportunitiesData",
                []
            )

            for opp in opportunities:

                title = (
                    opp.get("title")
                    or ""
                )

                buyer = (
                    opp.get(
                        "fullParentPathName"
                    )
                    or ""
                )

                published_at = (
                    opp.get(
                        "postedDate"
                    )
                    or ""
                )

                url = (
                    opp.get("uiLink")
                    or ""
                )

                summary = (
                    opp.get("description")
                    or opp.get("type")
                    or ""
                )

                category = (
                    opp.get(
                        "classificationCode"
                    )
                    or ""
                )

                notice_type = (
                    opp.get("type")
                    or ""
                )

                unspsc = (
                    opp.get("naicsCode")
                    or ""
                )

                ocid = (
                    opp.get("noticeId")
                    or ""
                )

                # -------------------------
                # Award
                # -------------------------

                supplier_name = ""

                award_amount = 0.0

                award_currency = "USD"

                award = (
                    opp.get("award")
                    or {}
                )

                if award:

                    award_amount = float(
                        award.get(
                            "amount"
                        )
                        or 0.0
                    )

                    awardee = (
                        award.get(
                            "awardee"
                        )
                        or {}
                    )

                    supplier_name = (
                        awardee.get("name")
                        or ""
                    )

                # -------------------------
                # Contact
                # -------------------------

                contact_name = ""

                contact_email = ""

                poc = (
                    opp.get(
                        "pointOfContact"
                    )
                    or []
                )

                if poc:

                    first_contact = poc[0]

                    contact_name = (
                        first_contact.get(
                            "fullName"
                        )
                        or ""
                    )

                    contact_email = (
                        first_contact.get(
                            "email"
                        )
                        or ""
                    )

                # -------------------------
                # Region
                # -------------------------

                delivery_region = ""

                office = (
                    opp.get(
                        "officeAddress"
                    )
                    or {}
                )

                if office:

                    city = (
                        office.get("city")
                        or ""
                    )

                    state = (
                        office.get("state")
                        or ""
                    )

                    delivery_region = (
                        f"{city}, {state}"
                    ).strip(", ")

                if not title:
                    continue

                tenders.append(
                    Tender(
                        source="SAM.gov",

                        portal_name="SAM.gov",

                        title=title.strip(),

                        url=url.strip(),

                        buyer=buyer.strip(),

                        published_at=(
                            published_at.strip()
                        ),

                        country="US",

                        region="FED",

                        summary=summary.strip(),

                        confidence=0.95,

                        ocid=ocid.strip(),

                        category=(
                            category.strip()
                        ),

                        supplier_name=(
                            supplier_name.strip()
                        ),

                        award_amount=(
                            award_amount
                        ),

                        award_currency=(
                            award_currency
                        ),

                        contact_name=(
                            contact_name.strip()
                        ),

                        contact_email=(
                            contact_email.strip()
                        ),

                        unspsc=(
                            unspsc.strip()
                        ),

                        notice_type=(
                            notice_type.strip()
                        ),

                        delivery_region=(
                            delivery_region.strip()
                        ),
                    )
                )

            print(
                f"[SAM.gov] Loaded "
                f"{len(tenders)} tenders"
            )

        except Exception as e:

            print(
                f"[SAM.gov] ERROR: {e}"
            )

        return tenders