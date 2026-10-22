"""Convert downloaded SEC HTML filings to Markdown with Docling."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = DATA_DIR / "downloads"
MARKDOWN_DIR = DATA_DIR / "markdown"
MANIFEST_PATH = DOWNLOADS_DIR / "manifest.json"


def main() -> None:
    if not MANIFEST_PATH.is_file():
        raise SystemExit(f"Missing downloads manifest: {MANIFEST_PATH}")

    source_manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source_filings = {
        Path(filing["local_path"].replace("\\", "/")).as_posix(): filing
        for filing in source_manifest.get("filings", [])
    }
    html_files = sorted(
        path
        for path in DOWNLOADS_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in {".htm", ".html"}
    )
    if not html_files:
        raise SystemExit(f"No HTML files found under {DOWNLOADS_DIR}")

    print("Loading Docling converter...", flush=True)
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    markdown_filings = []
    for index, source_path in enumerate(html_files, start=1):
        relative_path = source_path.relative_to(DOWNLOADS_DIR)
        markdown_path = MARKDOWN_DIR / relative_path.with_suffix(".md")
        markdown_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Converting {index}/{len(html_files)}: {relative_path}", flush=True)
        document = converter.convert(source_path).document
        markdown_path.write_text(document.export_to_markdown(), encoding="utf-8")

        manifest_entry = dict(source_filings.get(relative_path.as_posix(), {}))
        manifest_entry["source_local_path"] = relative_path.as_posix()
        manifest_entry["local_path"] = markdown_path.relative_to(MARKDOWN_DIR).as_posix()
        markdown_filings.append(manifest_entry)

    markdown_manifest = dict(source_manifest)
    markdown_manifest["filings"] = markdown_filings
    markdown_manifest["converted_count"] = len(markdown_filings)
    (MARKDOWN_DIR / "manifest.json").write_text(
        json.dumps(markdown_manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Converted {len(markdown_filings)} HTML file(s) to {MARKDOWN_DIR}")


if __name__ == "__main__":
    main()
