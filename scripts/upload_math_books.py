#!/usr/bin/env python3
"""
Batch upload math textbooks to Ragie for skill generation.
Handles PDFs and EPUBs. Warns about DJVUs (need conversion).

Usage:
    uv run python scripts/upload_math_books.py
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load .env from project root, then fallback to global
load_dotenv()
load_dotenv(Path.home() / ".claude" / ".env")

BOOKS_DIR = Path("/Users/cosimo/Downloads/Books")
PARTITION = "math-textbooks"
SUPPORTED_EXTENSIONS = {".pdf", ".epub"}


def upload_file(file_path: Path, api_key: str) -> dict:
    """Upload a single file to Ragie."""
    url = "https://api.ragie.ai/documents"
    headers = {"Authorization": f"Bearer {api_key}"}

    # Determine mime type
    ext = file_path.suffix.lower()
    mime_types = {
        ".pdf": "application/pdf",
        ".epub": "application/epub+zip",
    }
    mime_type = mime_types.get(ext, "application/octet-stream")

    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, mime_type)}
        data = {
            "partition": PARTITION,
        }

        response = httpx.post(url, headers=headers, files=files, data=data, timeout=300.0)
        response.raise_for_status()
        return response.json()


def main():
    api_key = os.environ.get("RAGIE_API_KEY")
    if not api_key:
        print("Error: RAGIE_API_KEY not found in .env or ~/.claude/.env", file=sys.stderr)
        sys.exit(1)

    if not BOOKS_DIR.exists():
        print(f"Error: {BOOKS_DIR} does not exist", file=sys.stderr)
        sys.exit(1)

    # Categorize files
    all_files = list(BOOKS_DIR.iterdir())
    to_upload = [f for f in all_files if f.suffix.lower() in SUPPORTED_EXTENSIONS]
    djvu_files = [f for f in all_files if f.suffix.lower() == ".djvu"]

    print(f"Found {len(to_upload)} uploadable files (PDF/EPUB)")
    print(f"Found {len(djvu_files)} DJVU files (need conversion - skipping)")

    if djvu_files:
        print("\nDJVU files skipped (convert to PDF first):")
        for f in djvu_files:
            print(f"  - {f.name}")

    print(f"\nUploading to partition: {PARTITION}")
    print("-" * 60)

    results = {"success": [], "failed": []}

    for i, file_path in enumerate(to_upload, 1):
        print(f"[{i}/{len(to_upload)}] {file_path.name[:60]}...", end=" ", flush=True)
        try:
            result = upload_file(file_path, api_key)
            doc_id = result.get("id", "unknown")
            print(f"✓ {doc_id}")
            results["success"].append({"file": file_path.name, "id": doc_id})
        except httpx.HTTPStatusError as e:
            print(f"✗ HTTP {e.response.status_code}")
            results["failed"].append({"file": file_path.name, "error": str(e)})
        except Exception as e:
            print(f"✗ {e}")
            results["failed"].append({"file": file_path.name, "error": str(e)})

    print("-" * 60)
    print(f"Done: {len(results['success'])} uploaded, {len(results['failed'])} failed")

    # Save results
    results_file = Path("math_books_upload_results.json")
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {results_file}")


if __name__ == "__main__":
    main()
