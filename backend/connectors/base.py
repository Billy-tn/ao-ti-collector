from dataclasses import dataclass
from typing import List


@dataclass
class Tender:
    source: str
    portal_name: str

    title: str
    url: str

    buyer: str = ""
    published_at: str = ""

    country: str = ""
    region: str = ""

    summary: str = ""
    source_domain: str = ""

    confidence: float = 0.0

    ocid: str = ""

    category: str = ""
    procurement_method: str = ""

    documents_url: str = ""

    supplier_name: str = ""

    award_amount: float = 0.0
    award_currency: str = ""

    contact_name: str = ""
    contact_email: str = ""

    unspsc: str = ""

    notice_type: str = ""

    delivery_region: str = ""

    award_status: str = ""


class BaseConnector:
    name = "base"

    def fetch(self) -> List[Tender]:
        raise NotImplementedError(
            "Connector must implement fetch()"
        )