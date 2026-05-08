from pathlib import Path
from urllib.parse import urlparse

import requests


DOCS_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "documents"
)

DOCS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def safe_filename(value: str):

    keep = []

    for c in value:

        if c.isalnum():
            keep.append(c)

        elif c in ("-", "_"):
            keep.append(c)

    cleaned = "".join(keep)

    return cleaned[:120]


def download_file(
    url: str,
    source: str,
    ocid: str = "",
):

    if not url:
        return None

    try:

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        r = requests.get(
            url,
            timeout=120,
            headers=headers,
            allow_redirects=True,
        )

        if r.status_code != 200:

            print(
                f"[documents] bad status "
                f"{r.status_code}"
            )

            return None

        content_type = (
            r.headers.get(
                "Content-Type",
                ""
            ).lower()
        )

        ext = ".bin"

        if "pdf" in content_type:
            ext = ".pdf"

        elif "html" in content_type:
            ext = ".html"

        elif "json" in content_type:
            ext = ".json"

        name = safe_filename(
            f"{source}_{ocid}"
        )

        if not name:
            name = "document"

        filepath = (
            DOCS_DIR / f"{name}{ext}"
        )

        with open(filepath, "wb") as f:
            f.write(r.content)

        print(
            f"[documents] saved "
            f"{filepath.name}"
        )

        return str(filepath)

    except Exception as e:

        print(
            f"[documents] download error: {e}"
        )

        return None