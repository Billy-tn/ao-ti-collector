from pathlib import Path
import requests


BASE_DIR = (
    Path(__file__).resolve().parent.parent.parent
)

DOCS_DIR = (
    BASE_DIR / "data" / "documents"
)

DOCS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def download_pdf(
    url: str,
    filename: str,
):

    try:

        response = requests.get(
            url,
            timeout=120,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
        )

        response.raise_for_status()

        path = DOCS_DIR / filename

        path.write_bytes(
            response.content
        )

        print(
            f"[pdf] saved {filename}"
        )

        return str(path)

    except Exception as e:

        print(
            f"[pdf] failed: {e}"
        )

        return None