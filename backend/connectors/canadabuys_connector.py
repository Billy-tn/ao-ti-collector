from typing import List
import csv
import io

import requests

from .base import BaseConnector, Tender
from .pdf_downloader import download_pdf


CANADABUYS_CSV_URL = (
    "https://canadabuys.canada.ca/opendata/pub/newTenderNotice-nouvelAvisAppelOffres.csv"
)


class CanadaBuysConnector(BaseConnector):

    name = "CanadaBuys"

    def fetch(self) -> List[Tender]:

        print(
            "[CanadaBuys] Fetch starting..."
        )

        tenders: List[Tender] = []

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/122.0.0.0 "
                "Safari/537.36"
            ),
            "Accept": (
                "text/csv,"
                "application/octet-stream,*/*"
            ),
            "Accept-Language": (
                "en-US,en;q=0.9"
            ),
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

            reader = csv.DictReader(
                io.StringIO(content)
            )

            print(
                "[CanadaBuys] CSV columns loaded"
            )

            for row_index, row in enumerate(
                list(reader)[:50]
            ):

                title = (
                    row.get(
                        "title-titre-eng"
                    )
                    or row.get(
                        "title-titre-fra"
                    )
                    or ""
                )

                url = (
                    row.get(
                        "noticeURL-URLavis-eng"
                    )
                    or row.get(
                        "noticeURL-URLavis-fra"
                    )
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
                    row.get(
                        "publicationDate-datePublication"
                    )
                    or ""
                )

                summary = (
                    row.get(
                        "tenderDescription-descriptionAppelOffres-eng"
                    )
                    or row.get(
                        "tenderDescription-descriptionAppelOffres-fra"
                    )
                    or ""
                )

                category = (
                    row.get(
                        "procurementCategory-categorieApprovisionnement"
                    )
                    or ""
                )

                procurement_method = (
                    row.get(
                        "procurementMethod-methodeApprovisionnement-eng"
                    )
                    or row.get(
                        "procurementMethod-methodeApprovisionnement-fra"
                    )
                    or ""
                )

                documents_url = (
                    row.get(
                        "attachment-piecesJointes-eng"
                    )
                    or row.get(
                        "attachment-piecesJointes-fra"
                    )
                    or ""
                )

                # --------------------------------------------------
                # PDF DOWNLOADS
                # --------------------------------------------------

                if documents_url:

                    print(
                        "\n[CanadaBuys attachment]"
                    )

                    print(
                        documents_url[:500]
                    )

                    urls = documents_url.split(",")

                    for idx, pdf_url in enumerate(urls):

                        pdf_url = (
                            pdf_url.strip()
                        )

                        if (
                            ".pdf"
                            not in pdf_url.lower()
                        ):
                            continue

                        filename = (
                            f"canadabuys_"
                            f"{row_index}_"
                            f"{idx}.pdf"
                        )

                        download_pdf(
                            pdf_url,
                            filename,
                        )

                contact_name = (
                    row.get(
                        "contactInfoName-informationsContactNom"
                    )
                    or ""
                )

                contact_email = (
                    row.get(
                        "contactInfoEmail-informationsContactCourriel"
                    )
                    or ""
                )

                unspsc = (
                    row.get("unspsc")
                    or ""
                )

                notice_type = (
                    row.get(
                        "noticeType-avisType-eng"
                    )
                    or row.get(
                        "noticeType-avisType-fra"
                    )
                    or ""
                )

                delivery_region = (
                    row.get(
                        "regionsOfDelivery-regionsLivraison-eng"
                    )
                    or row.get(
                        "regionsOfDelivery-regionsLivraison-fra"
                    )
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

                        published_at=(
                            published_at.strip()
                        ),

                        country="CA",

                        region="FED",

                        summary=summary.strip(),

                        confidence=0.95,

                        category=(
                            category.strip()
                        ),

                        procurement_method=(
                            procurement_method.strip()
                        ),

                        documents_url=(
                            documents_url.strip()
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
                f"[CanadaBuys] Loaded "
                f"{len(tenders)} tenders"
            )

        except Exception as e:

            print(
                f"[CanadaBuys] ERROR: {e}"
            )

        return tenders