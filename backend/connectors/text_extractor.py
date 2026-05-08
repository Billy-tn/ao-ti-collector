import fitz

from pathlib import Path

from bs4 import BeautifulSoup


BASE_DIR = (
    Path(__file__).resolve().parent.parent.parent
)

DOCS_DIR = (
    BASE_DIR / "data" / "documents"
)

EXTRACTED_DIR = (
    BASE_DIR / "data" / "extracted"
)

EXTRACTED_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def extract_html_text(
    file_path: Path,
):

    try:

        html = file_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        text = soup.get_text(
            separator="\n",
            strip=True,
        )

        return text

    except Exception as e:

        print(
            f"[extract] html error: {e}"
        )

        return ""


def extract_pdf_text(
    file_path: Path,
):

    try:

        doc = fitz.open(file_path)

        all_text = []

        for page in doc:

            text = page.get_text()

            if text:

                all_text.append(text)

        doc.close()

        return "\n".join(all_text)

    except Exception as e:

        print(
            f"[extract] pdf error: {e}"
        )

        return ""


def save_text(
    source_file: Path,
    text: str,
):

    output_name = (
        source_file.stem + ".txt"
    )

    output_path = (
        EXTRACTED_DIR / output_name
    )

    output_path.write_text(
        text,
        encoding="utf-8",
    )

    print(
        f"[extract] saved "
        f"{output_name}"
    )


def process_documents():

    files = list(
        DOCS_DIR.glob("*")
    )

    print(
        f"[extract] processing "
        f"{len(files)} files"
    )

    for file_path in files:

        suffix = (
            file_path.suffix.lower()
        )

        text = ""

        if suffix == ".html":

            text = extract_html_text(
                file_path
            )

        elif suffix == ".pdf":

            text = extract_pdf_text(
                file_path
            )

        if text:

            save_text(
                file_path,
                text,
            )


if __name__ == "__main__":

    process_documents()