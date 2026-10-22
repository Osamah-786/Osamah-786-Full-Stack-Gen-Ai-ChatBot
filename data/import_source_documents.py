"""Upsert converted SEC filings into Supabase source_documents."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent
BACKEND_DIR = DATA_DIR.parent / "backend"
MARKDOWN_DIR = DATA_DIR / "markdown"
MANIFEST_PATH = MARKDOWN_DIR / "manifest.json"
sys.path.insert(0, str(BACKEND_DIR))

from app.database.supabase import get_service_role_client  # noqa: E402


COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
}


def load_documents() -> list[dict]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    markdown_root = MARKDOWN_DIR.resolve()
    documents = []

    for filing in manifest["filings"]:
        relative_path = Path(filing["local_path"].replace("\\", "/"))
        markdown_path = (MARKDOWN_DIR / relative_path).resolve()
        if not markdown_path.is_relative_to(markdown_root):
            raise ValueError(f"Manifest path is outside markdown folder: {relative_path}")
        if not markdown_path.is_file():
            raise FileNotFoundError(f"Missing Markdown file: {relative_path}")

        ticker = filing["ticker"]
        if ticker not in COMPANY_NAMES:
            raise ValueError(f"No company name configured for ticker {ticker}")
        filing_date = date.fromisoformat(filing["filing_date"])
        fiscal_date = filing.get("report_date") or filing["filing_date"]
        content = markdown_path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"Markdown file is empty: {relative_path}")

        documents.append(
            {
                "ticker": ticker,
                "company_name": COMPANY_NAMES[ticker],
                "filing_type": filing["form"],
                "filing_date": filing_date.isoformat(),
                "fiscal_year": int(fiscal_date[:4]),
                "accession_number": filing["accession_number"],
                "source_url": filing["source_url"],
                "content_markdown": content,
            }
        )

    return documents


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="validate inputs and report DB matches without writing")
    args = parser.parse_args()

    if not MANIFEST_PATH.is_file():
        raise SystemExit(f"Missing Markdown manifest: {MANIFEST_PATH}")

    documents = load_documents()
    client = get_service_role_client()
    accession_numbers = [document["accession_number"] for document in documents]
    response = (
        client.table("source_documents")
        .select("accession_number")
        .in_("accession_number", accession_numbers)
        .execute()
    )
    existing = {row["accession_number"] for row in response.data}
    print(
        f"Prepared {len(documents)} document(s); {len(existing)} already exist; "
        f"{len(documents)} will be upserted."
    )

    if args.dry_run:
        return

    for index, document in enumerate(documents, start=1):
        client.table("source_documents").upsert(
            document, on_conflict="accession_number"
        ).execute()
        print(f"Upserted {index}/{len(documents)}: {document['accession_number']}")

    verified = (
        client.table("source_documents")
        .select("accession_number")
        .in_("accession_number", accession_numbers)
        .execute()
    )
    stored = {row["accession_number"] for row in verified.data}
    if stored != set(accession_numbers):
        raise SystemExit(f"Verification failed: expected {len(documents)}, found {len(stored)}")
    print(f"Verified {len(stored)} source document(s) in Supabase.")


if __name__ == "__main__":
    main()
